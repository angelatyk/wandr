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
