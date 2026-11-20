"""Tests that the text service talks to Gemini correctly, end to end.

The real Gemini SDK runs here, built by the real factory and pointed at a local
fake server. These check what would go over the wire and that the SDK's own
retries do not pile on top of ours. Nothing leaves this computer.
"""

import json

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.generation import GenerationRequest
from app.services import content_generation_service as service_module
from app.services.content_generation_service import (
    MAX_ATTEMPTS,
    get_content_generation_service,
)
from app.services.errors import (
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

KEY = "AIza-SUPER-SECRET-key-123"
MODEL = "gemini-wiring-test"
REQUEST = GenerationRequest(video_topic="Sunrise hike in the Alps", tone="funny", keywords=["alps"])


def good_reply(status="completed", text=None) -> tuple[int, dict]:
    """The smallest answer the SDK accepts as a finished interaction."""
    text = text or json.dumps({"captions": ["Boots on, phone off."], "hashtags": ["#alps"]})
    return 200, {
        "id": "interaction-1",
        "status": status,
        "model": MODEL,
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}],
    }


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    # Skips the pauses between retries, both ours and the SDK's.
    monkeypatch.setattr(service_module.time, "sleep", lambda seconds: None)


@pytest.fixture
def service_for(fake_server, monkeypatch):
    """Build the real service against a fake Gemini that gives these replies."""
    services = []

    def build(*replies):
        server = fake_server(list(replies))
        monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", server.url)
        monkeypatch.setattr(
            service_module,
            "get_settings",
            lambda: Settings(_env_file=None, gemini_api_key=SecretStr(KEY), gemini_text_model=MODEL),
        )
        get_content_generation_service.cache_clear()
        service = get_content_generation_service()
        services.append(service)
        return service, server

    yield build

    for service in services:
        service.close()
    get_content_generation_service.cache_clear()


# --- the request on the wire ------------------------------------------------


def test_a_request_reaches_gemini_in_the_shape_we_intend(service_for):
    service, server = service_for(good_reply())

    result = service.generate(REQUEST)

    assert result.hashtags == ["#alps"]
    (request,) = server.requests
    body = request["body"]
    assert request["path"] == "/v1beta/interactions"
    assert body["model"] == MODEL
    assert body["store"] is False
    assert body["generation_config"]["thinking_level"] == "low"
    assert body["response_format"]["mime_type"] == "application/json"
    assert "captions and hashtags" in body["system_instruction"]
    assert json.loads(body["input"])["video_topic"] == "Sunrise hike in the Alps"


def test_the_key_travels_in_a_header_and_nowhere_else(service_for):
    service, server = service_for(good_reply())

    service.generate(REQUEST)

    request = server.requests[0]
    assert request["headers"]["x-goog-api-key"] == KEY
    assert KEY not in request["path"]
    assert KEY not in json.dumps(request["body"])


def test_the_only_model_asked_for_is_the_configured_text_model(service_for):
    service, server = service_for(good_reply())

    service.generate(REQUEST)

    assert server.requests[0]["body"]["model"] == MODEL


# --- retries: ours only, not the SDK's on top -------------------------------


def test_a_busy_gemini_is_tried_exactly_as_often_as_we_decided(service_for):
    busy = (503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    service, server = service_for(busy)

    with pytest.raises(ProviderUnavailableError):
        service.generate(REQUEST)

    # Without the SDK's retries switched off, each of our attempts would be
    # several requests and this would be a multiple of MAX_ATTEMPTS.
    assert len(server.requests) == MAX_ATTEMPTS


def test_a_busy_gemini_followed_by_a_good_answer_still_works(service_for):
    busy = (503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    service, server = service_for(busy, good_reply())

    assert service.generate(REQUEST).captions == ["Boots on, phone off."]
    assert len(server.requests) == 2


def test_a_rate_limit_is_not_retried(service_for):
    limited = (429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    service, server = service_for(limited)

    with pytest.raises(ProviderRateLimitError):
        service.generate(REQUEST)

    assert len(server.requests) == 1


def test_a_wrong_key_is_an_auth_error_and_is_not_retried(service_for):
    # This is what Google really sends for a wrong key: a 400, not a 401.
    wrong_key = (
        400,
        {
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
                "details": [{"reason": "API_KEY_INVALID"}],
            }
        },
    )
    service, server = service_for(wrong_key)

    with pytest.raises(ProviderAuthError):
        service.generate(REQUEST)

    assert len(server.requests) == 1


# --- odd answers ------------------------------------------------------------


def test_an_answer_cut_off_by_the_token_limit_is_refused(service_for):
    service, _ = service_for(good_reply(status="incomplete", text='{"captions":["'))

    with pytest.raises(InvalidModelOutputError):
        service.generate(REQUEST)
