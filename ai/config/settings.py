import os

from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    gemini_api_key: str | None = None
    google_application_credentials: str | None = None
    google_cloud_api_key: str = "mock-google-cloud-key"
    google_cloud_api: str | None = None
    google_places_api_key: str | None = None
    google_routes_api_key: str | None = None
    google_directions_api_key: str | None = None
    ggogle_direction_api_key: str | None = None
    google_tts_api_key: str | None = None
    gcs_bucket_name: str = "mock-bucket"
    gcs_signed_url_ttl_seconds: int = 3600
    # When true, always return inline data URLs (best for local dev without GCS).
    tts_prefer_inline: bool = True
    model_name: str = "gemini-2.5-flash"
    model_fallbacks: str = "gemini-2.5-flash-lite,gemini-2.0-flash"
    # Comma-separated origins for CORS — tighten before production deploy
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # -------------------------------
    # Auth / sessions
    # -------------------------------
    # Google OAuth client ID used to verify "Sign in with Google" ID tokens.
    google_oauth_client_id: str | None = None
    # HMAC key used to sign session cookies. MUST be set to a long random value
    # in production — a weak/empty key means forgeable sessions.
    session_secret_key: str | None = None
    session_cookie_name: str = "wandr_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days
    # Set true behind HTTPS in production so the cookie is not sent over http.
    session_cookie_secure: bool = False
    # Local-only convenience login. Fails closed in production: the dev-login
    # endpoint is refused whenever the cookie is marked secure (i.e. HTTPS/prod).
    dev_auth_enabled: bool = True

    # -------------------------------
    # Abuse / cost controls
    # -------------------------------
    # Master switch — disable only for load tests, never in production.
    rate_limit_enabled: bool = True
    # Expensive planning endpoints (create/reply/select) launch Gemini + Places +
    # TTS work, so they get a tight per-user budget over a rolling window.
    plan_rate_limit_max: int = 10
    plan_rate_limit_window_seconds: int = 60
    # Places autocomplete is billed per keystroke — allow more, but still cap it.
    autocomplete_rate_limit_max: int = 60
    autocomplete_rate_limit_window_seconds: int = 60
    # Unauthenticated auth endpoints are keyed by client IP to slow brute force.
    auth_rate_limit_max: int = 20
    auth_rate_limit_window_seconds: int = 60
    # A single user may only have this many pipelines running at once; anything
    # more is rejected so a loop can't spawn unbounded background tasks.
    max_concurrent_pipelines_per_user: int = 1
    # Hard ceiling across all users, protecting total Google API spend/CPU.
    max_concurrent_pipelines_global: int = 8

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Backwards compatibility for older env naming.
if settings.google_cloud_api_key in {"", "mock-google-cloud-key", "your-google-cloud-api-key"}:
    if settings.google_cloud_api:
        settings.google_cloud_api_key = settings.google_cloud_api

if not settings.google_places_api_key:
    settings.google_places_api_key = settings.google_cloud_api_key

if not settings.google_routes_api_key:
    settings.google_routes_api_key = (
        settings.google_directions_api_key
        or settings.ggogle_direction_api_key
        or settings.google_cloud_api_key
    )

if not settings.google_tts_api_key:
    settings.google_tts_api_key = settings.google_cloud_api_key

if settings.gemini_api_key:
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
