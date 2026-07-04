"""Focused regression checks for TTS Phase 2 storage behavior."""

import unittest
from unittest.mock import AsyncMock, patch

from ai.tools.exceptions import TTSError
from ai.tools import tts


class GenerateAudioPhase2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_inline_audio_when_bucket_is_unconfigured(self) -> None:
        upload_mock = AsyncMock(return_value="https://example.com/audio.mp3")

        with (
            patch.object(tts.settings, "google_tts_api_key", "real-tts-key"),
            patch.object(tts.settings, "gcs_bucket_name", "mock-bucket"),
            patch("ai.tools.tts._synthesize_audio_bytes", new=AsyncMock(return_value=b"mp3-bytes")),
            patch("ai.tools.tts._upload_audio_to_gcs", new=upload_mock),
        ):
            audio_url = await tts.generate_audio("hello world", "warm")

        self.assertTrue(audio_url.startswith("data:audio/mpeg;base64,"))
        upload_mock.assert_not_awaited()

    async def test_returns_signed_url_when_gcs_upload_succeeds(self) -> None:
        upload_mock = AsyncMock(return_value="https://signed.example.com/audio.mp3")

        with (
            patch.object(tts.settings, "google_tts_api_key", "real-tts-key"),
            patch.object(tts.settings, "gcs_bucket_name", "wandr-audio"),
            patch("ai.tools.tts._synthesize_audio_bytes", new=AsyncMock(return_value=b"mp3-bytes")),
            patch("ai.tools.tts._upload_audio_to_gcs", new=upload_mock),
        ):
            audio_url = await tts.generate_audio("hello world", "warm")

        self.assertEqual(audio_url, "https://signed.example.com/audio.mp3")
        upload_mock.assert_awaited_once()

    async def test_falls_back_to_inline_audio_when_gcs_is_unavailable(self) -> None:
        with (
            patch.object(tts.settings, "google_tts_api_key", "real-tts-key"),
            patch.object(tts.settings, "gcs_bucket_name", "wandr-audio"),
            patch("ai.tools.tts._synthesize_audio_bytes", new=AsyncMock(return_value=b"mp3-bytes")),
            patch(
                "ai.tools.tts._upload_audio_to_gcs",
                new=AsyncMock(side_effect=tts._StorageUnavailableError("missing signer")),
            ),
        ):
            audio_url = await tts.generate_audio("hello world", "warm")

        self.assertTrue(audio_url.startswith("data:audio/mpeg;base64,"))

    async def test_rejects_blank_scripts(self) -> None:
        with self.assertRaises(TTSError):
            await tts.generate_audio("   ", "warm")


if __name__ == "__main__":
    unittest.main(verbosity=2)
