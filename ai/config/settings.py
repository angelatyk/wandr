import os

from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    gemini_api_key: str | None = None
    google_application_credentials: str | None = None
    google_cloud_api_key: str = "mock-google-cloud-key"
    gcs_bucket_name: str = "mock-bucket"
    gcs_signed_url_ttl_seconds: int = 3600
    model_name: str = "gemini-2.5-flash"
    # Comma-separated origins for CORS — tighten before production deploy
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

if settings.gemini_api_key:
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
