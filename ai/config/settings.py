"""Application settings loaded from environment variables (and .env).

All API key resolution and backwards-compatibility aliasing happens here so
every other module can import `settings` and read clean, canonical values.
"""

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
    gcs_signed_url_ttl_seconds: int = 604800
    # When true, always return inline data URLs (best for local dev without GCS).
    tts_prefer_inline: bool = True
    model_name: str = "gemini-2.5-flash"
    model_fallbacks: str = "gemini-2.5-flash-lite,gemini-2.0-flash"
    # Comma-separated origins for CORS — tighten before production deploy
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Abuse / cost controls
    rate_limit_enabled: bool = True
    plan_rate_limit_max: int = 10
    plan_rate_limit_window_seconds: int = 60
    autocomplete_rate_limit_max: int = 60
    autocomplete_rate_limit_window_seconds: int = 60
    max_concurrent_pipelines_per_user: int = 1
    max_concurrent_pipelines_global: int = 8

    # Per-agent Gemini output caps (input caps live in ai/models/input_limits.py).
    gemini_max_output_tokens_profiler: int = 1024
    gemini_max_output_tokens_itinerary: int = 8192
    gemini_max_output_tokens_stop_research: int = 2048
    gemini_max_output_tokens_narrator: int = 2048

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# ---------------------------------------------------------------------------
# Backwards-compatible key resolution — normalises older env naming schemes
# so callers never need to know which env var was actually set.
# ---------------------------------------------------------------------------
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
