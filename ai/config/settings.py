import os

from pydantic_settings import BaseSettings


_MOCK_MAPS_KEY = "mock-maps-key"


class Settings(BaseSettings):
    gemini_api_key: str | None = None
    google_application_credentials: str | None = None
    google_places_api_key: str = "mock-places-key"
    google_maps_api_key: str = "mock-maps-key"
    google_js_api_key: str | None = None
    vite_google_maps_api_key: str | None = None
    google_directions_api_key: str | None = None
    ggogle_direction_api_key: str | None = None
    google_routes_api_key: str | None = None
    google_tts_api_key: str = "mock-tts-key"
    gcs_bucket_name: str = "mock-bucket"
    gcs_signed_url_ttl_seconds: int = 3600
    model_name: str = "gemini-2.5-flash"
    # Comma-separated origins for CORS — tighten before production deploy
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

if settings.google_maps_api_key == _MOCK_MAPS_KEY:
    fallback_maps_key = (
        settings.google_directions_api_key
        or settings.ggogle_direction_api_key
        or settings.google_routes_api_key
        or settings.google_js_api_key
        or settings.vite_google_maps_api_key
    )
    if fallback_maps_key:
        settings.google_maps_api_key = fallback_maps_key

if settings.gemini_api_key:
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
