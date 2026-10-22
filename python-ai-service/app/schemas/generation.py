"""Request and response models for caption and hashtag generation.

This is the contract between the Spring Boot backend and this service. No AI
calls happen here: these models only describe the data and validate it.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Limits live in one place so the models and the tests always agree.
MAX_TOPIC_LENGTH = 500
MAX_TONE_LENGTH = 50
MAX_LANGUAGE_LENGTH = 50
MAX_KEYWORDS = 10
MAX_KEYWORD_LENGTH = 50

MAX_CAPTIONS = 10
MAX_CAPTION_LENGTH = 2200  # Instagram's caption limit, the strictest common one
MAX_HASHTAGS = 30  # Instagram's hashtag limit
MAX_HASHTAG_LENGTH = 100

DEFAULT_TONE = "engaging"
DEFAULT_LANGUAGE = "English"

Keyword = Annotated[str, Field(min_length=1, max_length=MAX_KEYWORD_LENGTH)]
Caption = Annotated[str, Field(min_length=1, max_length=MAX_CAPTION_LENGTH)]
Hashtag = Annotated[str, Field(min_length=1, max_length=MAX_HASHTAG_LENGTH)]


class GenerationRequest(BaseModel):
    """What the backend sends when it wants captions and hashtags for a video."""

    # Trim spaces around every string (including each keyword) before checking
    # lengths, so "   " counts as empty. Unknown fields are errors, not ignored.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    video_topic: str = Field(
        min_length=1,
        max_length=MAX_TOPIC_LENGTH,
        description="What the video is about.",
    )
    tone: str = Field(
        default=DEFAULT_TONE,
        min_length=1,
        max_length=MAX_TONE_LENGTH,
        description="Voice of the text, for example 'funny' or 'professional'.",
    )
    keywords: list[Keyword] = Field(
        default_factory=list,
        max_length=MAX_KEYWORDS,
        description="Words or phrases the result should try to work in.",
    )
    language: str = Field(
        default=DEFAULT_LANGUAGE,
        min_length=1,
        max_length=MAX_LANGUAGE_LENGTH,
        description="Language the captions should be written in.",
    )


class GenerationResponse(BaseModel):
    """What this service returns: ready-to-use captions and hashtags."""

    model_config = ConfigDict(str_strip_whitespace=True)

    captions: list[Caption] = Field(min_length=1, max_length=MAX_CAPTIONS)
    hashtags: list[Hashtag] = Field(min_length=1, max_length=MAX_HASHTAGS)
