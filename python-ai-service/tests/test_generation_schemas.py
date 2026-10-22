import pytest
from pydantic import ValidationError

from app.schemas.generation import (
    DEFAULT_LANGUAGE,
    DEFAULT_TONE,
    MAX_CAPTION_LENGTH,
    MAX_CAPTIONS,
    MAX_HASHTAG_LENGTH,
    MAX_HASHTAGS,
    MAX_KEYWORD_LENGTH,
    MAX_KEYWORDS,
    MAX_LANGUAGE_LENGTH,
    MAX_TONE_LENGTH,
    MAX_TOPIC_LENGTH,
    GenerationRequest,
    GenerationResponse,
)


def error_locations(exc_info: pytest.ExceptionInfo[ValidationError]) -> set[tuple]:
    """Which fields failed, e.g. {("video_topic",), ("keywords", 1)}."""
    return {error["loc"] for error in exc_info.value.errors()}


# --- GenerationRequest: valid input -----------------------------------------


def test_request_accepts_all_fields():
    request = GenerationRequest(
        video_topic="Sunrise hike in the Alps",
        tone="inspiring",
        keywords=["hiking", "alps"],
        language="German",
    )

    assert request.video_topic == "Sunrise hike in the Alps"
    assert request.tone == "inspiring"
    assert request.keywords == ["hiking", "alps"]
    assert request.language == "German"


def test_request_works_with_only_a_topic_and_applies_defaults():
    request = GenerationRequest(video_topic="Sunrise hike")

    assert request.tone == DEFAULT_TONE
    assert request.language == DEFAULT_LANGUAGE
    assert request.keywords == []


def test_request_keywords_default_is_not_shared_between_instances():
    first = GenerationRequest(video_topic="one")
    second = GenerationRequest(video_topic="two")

    first.keywords.append("leaked")

    assert second.keywords == []


def test_request_trims_spaces_around_text():
    request = GenerationRequest(
        video_topic="  Sunrise hike  ",
        tone=" calm ",
        keywords=["  hiking "],
        language=" French ",
    )

    assert request.video_topic == "Sunrise hike"
    assert request.tone == "calm"
    assert request.keywords == ["hiking"]
    assert request.language == "French"


def test_request_accepts_values_exactly_at_the_limits():
    request = GenerationRequest(
        video_topic="a" * MAX_TOPIC_LENGTH,
        tone="a" * MAX_TONE_LENGTH,
        language="a" * MAX_LANGUAGE_LENGTH,
        keywords=["a" * MAX_KEYWORD_LENGTH] * MAX_KEYWORDS,
    )

    assert len(request.video_topic) == MAX_TOPIC_LENGTH
    assert len(request.keywords) == MAX_KEYWORDS


# --- GenerationRequest: invalid input ---------------------------------------


def test_request_rejects_missing_topic():
    with pytest.raises(ValidationError) as exc_info:
        GenerationRequest()

    assert error_locations(exc_info) == {("video_topic",)}
    assert exc_info.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize("topic", ["", "   ", "\t\n"])
def test_request_rejects_empty_or_blank_topic(topic):
    with pytest.raises(ValidationError) as exc_info:
        GenerationRequest(video_topic=topic)

    assert error_locations(exc_info) == {("video_topic",)}


def test_request_rejects_a_topic_that_is_not_text():
    with pytest.raises(ValidationError):
        GenerationRequest(video_topic=123)


def test_request_rejects_too_long_topic():
    with pytest.raises(ValidationError) as exc_info:
        GenerationRequest(video_topic="a" * (MAX_TOPIC_LENGTH + 1))

    assert error_locations(exc_info) == {("video_topic",)}


@pytest.mark.parametrize(
    ("field", "max_length"),
    [("tone", MAX_TONE_LENGTH), ("language", MAX_LANGUAGE_LENGTH)],
)
def test_request_rejects_blank_or_too_long_tone_and_language(field, max_length):
    for bad_value in ("   ", "a" * (max_length + 1)):
        with pytest.raises(ValidationError) as exc_info:
            GenerationRequest(video_topic="Sunrise hike", **{field: bad_value})

        assert error_locations(exc_info) == {(field,)}


def test_request_rejects_too_many_keywords():
    with pytest.raises(ValidationError) as exc_info:
        GenerationRequest(video_topic="Sunrise hike", keywords=["tag"] * (MAX_KEYWORDS + 1))

    assert error_locations(exc_info) == {("keywords",)}


def test_request_rejects_blank_or_too_long_keyword_and_points_at_it():
    with pytest.raises(ValidationError) as exc_info:
        GenerationRequest(
            video_topic="Sunrise hike",
            keywords=["ok", "   ", "a" * (MAX_KEYWORD_LENGTH + 1)],
        )

    assert error_locations(exc_info) == {("keywords", 1), ("keywords", 2)}


def test_request_rejects_keywords_sent_as_one_string():
    with pytest.raises(ValidationError) as exc_info:
        GenerationRequest(video_topic="Sunrise hike", keywords="hiking, alps")

    assert error_locations(exc_info) == {("keywords",)}


def test_request_rejects_unknown_fields():
    with pytest.raises(ValidationError) as exc_info:
        GenerationRequest(video_topic="Sunrise hike", keyword=["typo"])

    assert error_locations(exc_info) == {("keyword",)}
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


# --- GenerationResponse -----------------------------------------------------


def test_response_accepts_captions_and_hashtags():
    response = GenerationResponse(
        captions=["Chasing sunrises.", "Up before the sun."],
        hashtags=["#hiking", "#alps"],
    )

    assert response.captions == ["Chasing sunrises.", "Up before the sun."]
    assert response.hashtags == ["#hiking", "#alps"]


def test_response_dumps_to_the_expected_json_shape():
    response = GenerationResponse(captions=["Hello"], hashtags=["#hi"])

    assert response.model_dump() == {"captions": ["Hello"], "hashtags": ["#hi"]}


def test_response_can_be_rebuilt_from_its_own_json():
    original = GenerationResponse(captions=["Hello"], hashtags=["#hi"])

    rebuilt = GenerationResponse.model_validate_json(original.model_dump_json())

    assert rebuilt == original


def test_response_trims_spaces_around_items():
    response = GenerationResponse(captions=["  Hello  "], hashtags=[" #hi "])

    assert response.captions == ["Hello"]
    assert response.hashtags == ["#hi"]


@pytest.mark.parametrize("missing", ["captions", "hashtags"])
def test_response_rejects_a_missing_field(missing):
    data = {"captions": ["Hello"], "hashtags": ["#hi"]}
    del data[missing]

    with pytest.raises(ValidationError) as exc_info:
        GenerationResponse(**data)

    assert error_locations(exc_info) == {(missing,)}


@pytest.mark.parametrize("field", ["captions", "hashtags"])
def test_response_rejects_an_empty_list(field):
    data = {"captions": ["Hello"], "hashtags": ["#hi"], field: []}

    with pytest.raises(ValidationError) as exc_info:
        GenerationResponse(**data)

    assert error_locations(exc_info) == {(field,)}


@pytest.mark.parametrize("field", ["captions", "hashtags"])
def test_response_rejects_blank_items(field):
    data = {"captions": ["Hello"], "hashtags": ["#hi"], field: ["fine", "   "]}

    with pytest.raises(ValidationError) as exc_info:
        GenerationResponse(**data)

    assert error_locations(exc_info) == {(field, 1)}


def test_response_rejects_too_many_or_too_long_items():
    too_many_captions = ["caption"] * (MAX_CAPTIONS + 1)
    too_many_hashtags = ["#tag"] * (MAX_HASHTAGS + 1)
    too_long_caption = "a" * (MAX_CAPTION_LENGTH + 1)
    too_long_hashtag = "#" + "a" * MAX_HASHTAG_LENGTH

    for data in (
        {"captions": too_many_captions, "hashtags": ["#hi"]},
        {"captions": ["Hello"], "hashtags": too_many_hashtags},
        {"captions": [too_long_caption], "hashtags": ["#hi"]},
        {"captions": ["Hello"], "hashtags": [too_long_hashtag]},
    ):
        with pytest.raises(ValidationError):
            GenerationResponse(**data)
