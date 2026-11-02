"""Tests for POST /api/v1/content/generate. Groq is never called."""

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx2
import pytest
from fastapi.testclient import TestClient
from openai import AuthenticationError, RateLimitError
from pydantic import SecretStr

from app.api.routes import content as content_module
from app.api.routes.content import get_generation_service
from app.core.config import Settings
from app.main import app
from app.schemas.generation import GenerationRequest, GenerationResponse
from app.services import content_generation_service as service_module
from app.services.content_generation_service import (
    ContentGenerationService,
    get_content_generation_service,
)
from app.services.errors import (
    ContentGenerationError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderUnavailableError,
)

URL = "/api/v1/content/generate"
SECRET = "gsk_SUPER_SECRET_key_123"

GOOD_RESULT = GenerationResponse(
    captions=["Sunrise, boots on, phone off.", "Who else hikes before breakfast?"],
    hashtags=["#hiking", "#sunrise", "#alps"],
)


# --- fixtures ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_state():
    """Undo overrides and the cached service so tests cannot affect each other."""
    get_content_generation_service.cache_clear()
    yield
    app.dependency_overrides.clear()
    get_content_generation_service.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def service() -> MagicMock:
    """A fake service that succeeds, plugged in where the real one would go."""
    fake = MagicMock(spec=ContentGenerationService)
    fake.generate.return_value = GOOD_RESULT
    app.dependency_overrides[get_generation_service] = lambda: fake
    return fake


def use_real_service_with_fake_groq(groq_client: MagicMock) -> None:
    """Run the real Phase 2 service, with only the Groq client faked."""
    real = ContentGenerationService(groq_client, "openai/gpt-oss-20b")
    app.dependency_overrides[get_generation_service] = lambda: real


def groq_reply(data: dict) -> SimpleNamespace:
    message = SimpleNamespace(content=json.dumps(data))
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


def provider_error(error_class, status: int, message: str):
    request = httpx2.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return error_class(message, response=httpx2.Response(status, request=request), body=None)


# --- success ----------------------------------------------------------------


def test_valid_request_returns_captions_and_hashtags(client, service):
    response = client.post(URL, json={"video_topic": "Sunrise hike in the Alps"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "captions": GOOD_RESULT.captions,
        "hashtags": GOOD_RESULT.hashtags,
    }


def test_response_has_exactly_the_documented_fields_and_types(client, service):
    body = client.post(URL, json={"video_topic": "Sunrise hike"}).json()

    assert set(body) == {"captions", "hashtags"}
    assert all(isinstance(item, str) for item in body["captions"] + body["hashtags"])


def test_all_request_fields_reach_the_service(client, service):
    payload = {
        "video_topic": "Sunrise hike in the Alps",
        "tone": "funny",
        "keywords": ["hiking", "alps"],
        "language": "German",
    }

    client.post(URL, json=payload)

    service.generate.assert_called_once_with(GenerationRequest(**payload))


def test_the_service_gets_the_phase_1_defaults_when_only_a_topic_is_sent(client, service):
    client.post(URL, json={"video_topic": "  Sunrise hike  "})

    sent = service.generate.call_args.args[0]
    assert sent == GenerationRequest(video_topic="Sunrise hike")
    assert sent.keywords == []


def test_real_service_output_comes_through_the_endpoint_cleaned_up(client):
    groq = MagicMock()
    groq.chat.completions.create.return_value = groq_reply(
        {"captions": ["One good caption"], "hashtags": ["travel", "#Travel", "#fun"]}
    )
    use_real_service_with_fake_groq(groq)

    response = client.post(URL, json={"video_topic": "A trip"})

    assert response.status_code == 200
    assert response.json() == {"captions": ["One good caption"], "hashtags": ["#travel", "#fun"]}


# --- invalid requests (FastAPI validation -> 422) ---------------------------


def test_missing_topic_is_a_422_that_names_the_field(client, service):
    response = client.post(URL, json={})

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "video_topic"]
    assert error["type"] == "missing"
    service.generate.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"video_topic": ""}, id="empty-topic"),
        pytest.param({"video_topic": "   "}, id="blank-topic"),
        pytest.param({"video_topic": None}, id="null-topic"),
        pytest.param({"video_topic": 123}, id="topic-not-text"),
        pytest.param({"video_topic": "a" * 501}, id="topic-too-long"),
        pytest.param({"video_topic": "x", "tone": ""}, id="empty-tone"),
        pytest.param({"video_topic": "x", "keywords": "hiking, alps"}, id="keywords-as-string"),
        pytest.param({"video_topic": "x", "keywords": ["k"] * 11}, id="too-many-keywords"),
        pytest.param({"video_topic": "x", "keywords": [" "]}, id="blank-keyword"),
        pytest.param({"video_topic": "x", "language": "a" * 51}, id="language-too-long"),
        pytest.param({"video_topic": "x", "keyword": ["typo"]}, id="unknown-field"),
    ],
)
def test_invalid_input_is_a_422_and_never_reaches_the_service(client, service, payload):
    response = client.post(URL, json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    service.generate.assert_not_called()


def test_unknown_field_error_says_so(client, service):
    response = client.post(URL, json={"video_topic": "x", "keyword": ["typo"]})

    error = response.json()["detail"][0]
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ["body", "keyword"]


@pytest.mark.parametrize("body", ["not json", "", "[]"], ids=["garbage", "empty", "list"])
def test_a_body_that_is_not_a_json_object_is_a_422(client, service, body):
    response = client.post(URL, content=body, headers={"content-type": "application/json"})

    assert response.status_code == 422
    service.generate.assert_not_called()


def test_only_post_is_allowed(client, service):
    assert client.get(URL).status_code == 405


# --- service failures -> HTTP errors ----------------------------------------


class UnlistedError(ContentGenerationError):
    """A future error class nobody added to the status table."""

    default_message = "Something new went wrong."


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        pytest.param(ProviderAuthError(), 503, id="credentials"),
        pytest.param(ProviderRateLimitError(), 429, id="rate-limit"),
        pytest.param(ProviderUnavailableError(), 503, id="unavailable"),
        pytest.param(ProviderRequestError(), 502, id="request-refused"),
        pytest.param(InvalidModelOutputError(), 502, id="bad-model-output"),
        pytest.param(UnlistedError(), 500, id="unlisted-error"),
    ],
)
def test_service_errors_become_the_right_status_with_a_safe_message(
    client, service, error, expected_status
):
    service.generate.side_effect = error

    response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


class QuotaExceeded(ProviderRateLimitError):
    """A plausible future refinement of the rate-limit error."""


def test_a_subclass_of_a_listed_error_keeps_its_parents_status(client, service):
    service.generate.side_effect = QuotaExceeded()

    response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 429


def test_a_failure_is_never_a_success_response(client, service):
    service.generate.side_effect = InvalidModelOutputError()

    body = client.post(URL, json={"video_topic": "Sunrise hike"}).json()

    assert "captions" not in body
    assert "hashtags" not in body


def test_provider_detail_stays_out_of_the_response(client, service):
    error = ProviderAuthError()
    error.__cause__ = RuntimeError(f"401 from Groq for key {SECRET}")
    service.generate.side_effect = error

    response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 503
    assert SECRET not in response.text
    assert "Groq" not in response.text


def test_real_service_rate_limit_becomes_a_429_without_retrying(client):
    groq = MagicMock()
    groq.chat.completions.create.side_effect = provider_error(RateLimitError, 429, "slow down")
    use_real_service_with_fake_groq(groq)

    response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 429
    assert groq.chat.completions.create.call_count == 1


def test_real_service_rejected_key_becomes_a_503_and_the_key_is_not_leaked(client):
    groq = MagicMock()
    groq.chat.completions.create.side_effect = provider_error(
        AuthenticationError, 401, f"Invalid API key {SECRET}"
    )
    use_real_service_with_fake_groq(groq)

    response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 503
    assert SECRET not in response.text


def test_real_service_unusable_model_output_becomes_a_502(client):
    groq = MagicMock()
    groq.chat.completions.create.return_value = groq_reply({"captions": [], "hashtags": ["#a"]})
    use_real_service_with_fake_groq(groq)

    response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 502
    assert "captions" not in response.json()


# --- missing credentials and unexpected failures ----------------------------


def test_missing_api_key_is_a_503(client, monkeypatch):
    # No dependency override here: this goes through the real service factory.
    # _env_file=None keeps the developer's real .env out of the test.
    monkeypatch.setattr(
        service_module, "get_settings", lambda: Settings(_env_file=None, groq_api_key=None)
    )

    response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 503
    assert response.json() == {"detail": ProviderAuthError().default_message}


def test_blank_api_key_is_a_503(client, monkeypatch):
    monkeypatch.setattr(
        service_module,
        "get_settings",
        lambda: Settings(_env_file=None, groq_api_key=SecretStr("   ")),
    )

    assert client.post(URL, json={"video_topic": "Sunrise hike"}).status_code == 503


def test_unexpected_service_exception_is_a_generic_500_that_hides_the_details(
    client, service, caplog
):
    service.generate.side_effect = RuntimeError(f"internal detail {SECRET}")

    with caplog.at_level(logging.ERROR):
        response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert SECRET not in response.text
    assert "internal detail" not in response.text
    assert "Traceback" not in response.text
    # The full story is kept for us, in the server log.
    assert "internal detail" in caplog.text


def test_unexpected_failure_while_building_the_service_is_also_a_json_500(
    client, monkeypatch, caplog
):
    def explode():
        raise ValueError(f"bad base url near {SECRET}")

    monkeypatch.setattr(content_module, "get_content_generation_service", explode)

    with caplog.at_level(logging.ERROR):
        response = client.post(URL, json={"video_topic": "Sunrise hike"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert SECRET not in response.text
    assert "bad base url" in caplog.text


# --- the rest of the app still works ----------------------------------------


def test_health_endpoint_still_works_with_the_content_router_registered(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_documents_the_endpoint_and_its_errors(client):
    spec = client.get("/openapi.json").json()

    assert "/api/v1/health" in spec["paths"]
    operation = spec["paths"][URL]
    assert set(operation) == {"post"}
    assert {"200", "422", "429", "500", "502", "503"} <= set(operation["post"]["responses"])
