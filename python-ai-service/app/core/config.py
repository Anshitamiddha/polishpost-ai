
"""Application settings loaded from environment variables or .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PublishPro-AI Python AI Service"
    app_version: str = "0.1.0"

    # Thumbnail pictures come from Magic Hour.
    magic_hour_api_key: SecretStr | None = None
    # Model and resolution are settings so they can change without a code edit.
    # The SDK lists the values it accepts; "640px" is the smallest, and the cheapest to test with.
    magic_hour_image_model: str = "z-image-turbo"
    magic_hour_image_resolution: str = "640px"
    # The longest we wait for one picture. The SDK's own wait has no limit.
    magic_hour_timeout_seconds: float = Field(default=120.0, gt=0)

    # Where finished thumbnails are saved. The default sits inside this project
    # whatever folder the service is started from.
    thumbnail_output_dir: Path = Path(__file__).resolve().parents[2] / "generated" / "thumbnails"

    # Backblaze B2, reached through its S3-compatible API. For now this is only the
    # connection setup. All five are optional so the app starts without them; the B2
    # client refuses to build until every one is set.
    b2_key_id: SecretStr | None = None
    b2_application_key: SecretStr | None = None
    b2_bucket_name: str | None = None
    # The S3 endpoint Backblaze shows for the bucket, such as https://s3.<region>.backblazeb2.com
    b2_endpoint_url: str | None = None
    b2_region: str | None = None

    # Shared secret that Spring Boot sends in X-Internal-Service-Token.
    # Optional here so the app can still start; the thumbnail endpoint answers
    # 503 until it is set.
    ai_service_shared_secret: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the shared application settings."""
    return Settings()
