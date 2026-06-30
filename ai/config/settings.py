import os
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    gemini_api_key: str | None = None
    model_name: str = "gemini-2.5-flash"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

if settings.gemini_api_key:
    os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
