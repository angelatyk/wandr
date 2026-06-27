from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_places_api_key: str = "mock-places-key"
    google_maps_api_key: str = "mock-maps-key"
    google_tts_api_key: str = "mock-tts-key"
    gcs_bucket_name: str = "mock-bucket"
    model_name: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
