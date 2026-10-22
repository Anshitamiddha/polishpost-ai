
"""Application settings loaded from environment variables or .env."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PublishPro-AI Python AI Service"
    app_version: str = "0.1.0"

    # Gemini API key for image generation
    gemini_api_key: SecretStr | None = None

    # Groq API key for text generation
    groq_api_key: SecretStr | None = None
    # Groq speaks the OpenAI protocol, so we call it through the OpenAI SDK.
    # Model and URL are settings so they can change without a code edit.
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"


@lru_cache
def get_settings() -> Settings:
    """Return the shared application settings."""
    return Settings()
