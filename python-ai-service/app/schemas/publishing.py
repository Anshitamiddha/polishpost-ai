"""HTTP contracts for the creator text workflow."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublishingTextRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title_or_topic: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=10, max_length=6000)
    target_audience: str = Field(min_length=2, max_length=300)
    tone: str = Field(min_length=2, max_length=100)
    language: str = Field(min_length=2, max_length=80)
    keywords: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("keywords")
    @classmethod
    def unique_keywords(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))


class SeoKeywords(BaseModel):
    primary: list[str] = Field(min_length=1, max_length=5)
    secondary: list[str] = Field(min_length=1, max_length=15)


class PublishingTextResponse(BaseModel):
    captions: list[str] = Field(min_length=2, max_length=5)
    hashtags: list[str] = Field(min_length=3, max_length=20)
    seo_keywords: SeoKeywords
