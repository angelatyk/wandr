import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import urllib.error
import urllib.request
from uuid import uuid4

import google.auth
from google.auth.exceptions import DefaultCredentialsError, GoogleAuthError
from google.auth.transport.requests import Request

try:
    from google.cloud import storage
except ImportError:
    storage = None

from ai.config.settings import settings
from ai.tools.exceptions import TTSError

logger = logging.getLogger(__name__)

TTS_SYNTH_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
_MOCK_TTS_KEYS = {"", "mock-tts-key", "your-tts-api-key"}
_MOCK_GCS_BUCKETS = {"", "mock-bucket", "your-gcs-bucket-name"}
_GCS_AUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

_VOICE_CONFIGS = {
    "dramatic": {
        "language_code": "en-US",
        "voice_name": "en-US-Wavenet-D",
        "speaking_rate": 0.95,
        "pitch": -2.0,
    },
    "enthusiastic": {
        "language_code": "en-US",
        "voice_name": "en-US-Wavenet-F",
        "speaking_rate": 1.08,
        "pitch": 2.0,
    },
    "contemplative": {
        "language_code": "en-US",
        "voice_name": "en-US-Wavenet-C",
        "speaking_rate": 0.92,
        "pitch": -0.5,
    },
    "energetic": {
        "language_code": "en-US",
        "voice_name": "en-US-Wavenet-B",
        "speaking_rate": 1.12,
        "pitch": 2.5,
    },
    "warm": {
        "language_code": "en-US",
        "voice_name": "en-US-Wavenet-E",
        "speaking_rate": 0.98,
        "pitch": 0.5,
    },
}


def _voice_config(voice_style: str) -> dict[str, object]:
    return _VOICE_CONFIGS.get(voice_style, _VOICE_CONFIGS["warm"])


def _uses_mock_tts() -> bool:
    return settings.google_tts_api_key.strip() in _MOCK_TTS_KEYS


def _uses_gcs_storage() -> bool:
    return settings.gcs_bucket_name.strip() not in _MOCK_GCS_BUCKETS


def _build_tts_payload(script: str, voice_style: str) -> dict[str, object]:
    config = _voice_config(voice_style)
    return {
        "input": {"text": script},
        "voice": {
            "languageCode": config["language_code"],
            "name": config["voice_name"],
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": config["speaking_rate"],
            "pitch": config["pitch"],
        },
    }


async def _synthesize_audio_bytes(script: str, voice_style: str) -> bytes:
    payload = _build_tts_payload(script, voice_style)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_tts_api_key,
    }

    def _post() -> bytes:
        request = urllib.request.Request(
            TTS_SYNTH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode(errors="replace")
            raise TTSError(f"TTS API error {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise TTSError(f"TTS request failed: {exc}") from exc

        audio_content = body.get("audioContent")
        if not audio_content:
            raise TTSError(f"TTS response missing audioContent: {body}")

        try:
            return base64.b64decode(audio_content)
        except Exception as exc:  # noqa: BLE001
            raise TTSError("TTS returned invalid base64 audio content") from exc

    return await asyncio.to_thread(_post)


def _audio_data_url(audio_bytes: bytes) -> str:
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    return f"data:audio/mpeg;base64,{encoded}"


class _StorageUnavailableError(RuntimeError):
    pass


def _gcs_object_name(script: str, voice_style: str) -> str:
    script_hash = hashlib.sha1(script.encode("utf-8")).hexdigest()[:12]
    safe_voice_style = voice_style.strip().lower().replace(" ", "-") or "warm"
    timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    return f"tts/{timestamp}-{safe_voice_style}-{script_hash}-{uuid4().hex[:12]}.mp3"


def _signed_url_ttl() -> timedelta:
    ttl_seconds = settings.gcs_signed_url_ttl_seconds
    if ttl_seconds <= 0:
        raise _StorageUnavailableError("GCS_SIGNED_URL_TTL_SECONDS must be greater than zero")
    return timedelta(seconds=ttl_seconds)


def _generate_signed_blob_url(blob, credentials, expiration: timedelta) -> str:
    try:
        return blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET",
            response_type="audio/mpeg",
            credentials=credentials,
        )
    except AttributeError as exc:
        try:
            request = Request()
            credentials.refresh(request)
        except (GoogleAuthError, OSError, ValueError) as refresh_exc:
            raise _StorageUnavailableError("Credentials cannot sign GCS URLs") from refresh_exc

        service_account_email = getattr(credentials, "service_account_email", None)
        if not service_account_email or not credentials.token:
            raise _StorageUnavailableError("Credentials cannot sign GCS URLs") from exc

        try:
            return blob.generate_signed_url(
                version="v4",
                expiration=expiration,
                method="GET",
                response_type="audio/mpeg",
                service_account_email=service_account_email,
                access_token=credentials.token,
            )
        except (GoogleAuthError, OSError, ValueError) as sign_exc:
            raise _StorageUnavailableError("Credentials cannot sign GCS URLs") from sign_exc
    except (GoogleAuthError, OSError, ValueError) as exc:
        raise _StorageUnavailableError("Credentials cannot sign GCS URLs") from exc


async def _upload_audio_to_gcs(
    script: str,
    voice_style: str,
    audio_bytes: bytes,
) -> str:
    if storage is None:
        raise _StorageUnavailableError("google-cloud-storage is not installed")

    bucket_name = settings.gcs_bucket_name.strip()
    expiration = _signed_url_ttl()

    def _upload() -> str:
        try:
            credentials, project_id = google.auth.default(scopes=[_GCS_AUTH_SCOPE])
        except DefaultCredentialsError as exc:
            raise _StorageUnavailableError("Google Cloud credentials are not available") from exc

        from google.cloud.exceptions import GoogleCloudError

        try:
            client = storage.Client(project=project_id, credentials=credentials)
            blob = client.bucket(bucket_name).blob(_gcs_object_name(script, voice_style))
            blob.cache_control = "private, max-age=0, no-transform"
            signed_url = _generate_signed_blob_url(blob, credentials, expiration)
            blob.upload_from_string(audio_bytes, content_type="audio/mpeg")
        except (GoogleCloudError, GoogleAuthError, OSError, ValueError) as exc:
            raise _StorageUnavailableError("GCS upload failed") from exc

        return signed_url

    return await asyncio.to_thread(_upload)


async def generate_audio(script: str, voice_style: str) -> str:
    """Generate MP3 audio and return a signed GCS URL or inline data URL."""
    if not script or not script.strip():
        raise TTSError("Script is required for audio generation")

    if _uses_mock_tts():
        raise TTSError(
            "GOOGLE_TTS_API_KEY is not configured. Set a real Google Cloud TTS key in .env."
        )

    audio_bytes = await _synthesize_audio_bytes(script, voice_style)
    if _uses_gcs_storage():
        try:
            return await _upload_audio_to_gcs(script, voice_style, audio_bytes)
        except _StorageUnavailableError as exc:
            logger.warning("GCS upload unavailable, falling back to inline audio: %s", exc)

    return _audio_data_url(audio_bytes)
