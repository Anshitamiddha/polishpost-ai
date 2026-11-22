"""Request and response models for thumbnail generation.

This is the contract between the Spring Boot backend and this service. No AI
calls happen here: these models only describe the data and validate it.
"""

from pydantic import BaseModel, ConfigDict, Field

# Limits live in one place so the models and the tests always agree.
MAX_VIDEO_TOPIC_LENGTH = 60  # it is written on the picture, so it has to be read at a glance
MAX_DESCRIPTION_LENGTH = 300
MAX_GLOBAL_PROMPT_LENGTH = 500
MAX_WORKSPACE_ID = 2**63 - 1  # the largest value of the backend's Long workspace id


class ThumbnailRequest(BaseModel):
    """What the backend sends when it wants a thumbnail for a video."""

    # Trim spaces before checking lengths, so "   " counts as empty. Unknown
    # fields are errors, not ignored.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    # Only Spring Boot may set this, and only after it has checked that the user
    # belongs to the workspace. This service has no database to check it against.
    # Strict, so "5", 5.0 and true are refused and nothing odd can reach the storage key.
    workspace_id: int = Field(
        strict=True,
        gt=0,
        le=MAX_WORKSPACE_ID,
        description="The workspace the picture belongs to. Set by the backend, never by the browser.",
    )
    # The video's title as the user typed it. It is also the text written on the picture.
    video_topic: str = Field(
        min_length=3,
        max_length=MAX_VIDEO_TOPIC_LENGTH,
        description="The video's title or topic. It is also the text written on the thumbnail.",
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="What the video is about, in the user's words. Optional.",
    )
    # The user's "global creative prompt". Optional, because the user may clear it,
    # and then the thumbnail simply has no extra direction.
    global_prompt: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_GLOBAL_PROMPT_LENGTH,
        description="The user's own creative direction, for example 'neon cyberpunk city, bold colors'.",
    )


class ThumbnailImage(BaseModel):
    """The saved picture. Nothing here reveals where the file lives, or links to it."""

    reference: str = Field(
        description="File name inside the thumbnail output folder. Not a path, and not a link."
    )
    width: int
    height: int
    format: str = Field(description="The image format found in the file: png, jpeg or webp.")
    asset_id: str = Field(description="Our ID for this picture. It is also the file name in B2.")
    object_key: str = Field(
        description="Where the picture is stored in the private B2 bucket. It is a key, not a link."
    )
    content_type: str = Field(description="The type the file was stored with, such as image/png.")
    size_bytes: int = Field(description="The size of the stored file.")
    preview_data_url: str | None = Field(
        default=None,
        description="The picture itself as a data URL, so the page can show it at once. "
        "The bucket stays private. Empty only if the file could not be read back.",
    )


class ThumbnailResponse(BaseModel):
    """What this service returns once the picture is made and checked."""

    success: bool = True
    status: str = Field(description="The provider's final status for this generation.")
    image: ThumbnailImage
    provider_generation_id: str = Field(description="Magic Hour's ID for this image project.")
    credits_charged: int = Field(description="Credits Magic Hour charged for it, as it reported them.")
