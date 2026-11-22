"""Tests for the X-Internal-Service-Token check. Magic Hour is never called."""

import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.routes.thumbnails import get_thumbnail_service
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.thumbnail import ThumbnailImage, ThumbnailResponse
from app.services import thumbnail_generation_service as service_module
from app.services.errors import ProviderRateLimitError
from app.services.thumbnail_generation_service import (
    ThumbnailGenerationService,
    get_thumbnail_generation_service,
)

URL = "/api/v1/publish/thumbnails"
HEALTH_URL = "/api/v1/health"
HEADER = "X-Internal-Service-Token"
# Fake values made for these tests only. Nothing here is a real secret.
SECRET = "unit-test-shared-secret"
BODY = {
    "workspace_id": 12,
    "video_topic": "Sunrise hike in the Alps",
    "description": "A sunrise hike with a great view",
    "global_prompt": "cinematic, golden light",
}

GOOD_RESULT = ThumbnailResponse(
    status="complete",
    image=ThumbnailImage(
        reference="abc123.png",
        width=640,
        height=360,
        format="png",
        asset_id="abc123",
        object_key="workspaces/12/generated/abc123.png",
        content_type="image/png",
        size_bytes=1234,
    ),
    provider_generation_id="job-1",
    credits_charged=5,
)


# --- helpers ----------------------------------------------------------------


def configure_secret(value: str | None) -> None:
    """Pretend the server was started with this shared secret."""
    # _env_file=None keeps the developer's real .env out of the test.
    settings = Settings(
        _env_file=None,
        ai_service_shared_secret=None if value is None else SecretStr(value),
    )
    app.dependency_overrides[get_settings] = lambda: settings


@pytest.fixture(autouse=True)
def clean_state():
    get_thumbnail_generation_service.cache_clear()
    configure_secret(SECRET)
    yield
    app.dependency_overrides.clear()
    get_thumbnail_generation_service.cache_clear()


@pytest.fixture
def client() -> TestClient:
    # No default token here: each test decides what to send.
    return TestClient(app)


@pytest.fixture
def service() -> MagicMock:
    fake = MagicMock(spec=ThumbnailGenerationService)
    fake.generate.return_value = GOOD_RESULT
    app.dependency_overrides[get_thumbnail_service] = lambda: fake
    return fake


# --- a correct token --------------------------------------------------------


def test_correct_token_lets_the_request_through(client, service):
    response = client.post(URL, json=BODY, headers={HEADER: SECRET})

    assert response.status_code == 200
    assert response.json() == GOOD_RESULT.model_dump()
    service.generate.assert_called_once()


def test_header_name_is_not_case_sensitive(client, service):
    # HTTP header names are case-insensitive, and proxies sometimes lowercase them.
    response = client.post(URL, json=BODY, headers={HEADER.lower(): SECRET})

    assert response.status_code == 200


# --- missing or wrong token -> 401 ------------------------------------------


def test_missing_token_is_401(client, service):
    response = client.post(URL, json=BODY)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid service token."}
    service.generate.assert_not_called()


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("wrong-token", id="wrong"),
        pytest.param("", id="empty"),
        pytest.param(SECRET.upper(), id="wrong-case"),
        pytest.param(SECRET[:-1], id="one-char-short"),
        pytest.param(SECRET + "x", id="one-char-long"),
        pytest.param(f"Bearer {SECRET}", id="bearer-prefix"),
    ],
)
def test_wrong_token_is_401(client, service, token):
    response = client.post(URL, json=BODY, headers={HEADER: token})

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid service token."}
    service.generate.assert_not_called()


def test_a_token_with_non_ascii_bytes_is_a_401_not_a_crash(client, service):
    # compare_digest raises on non-ASCII text, so this guards against a 500.
    response = client.post(URL, json=BODY, headers={HEADER: "tökén".encode("latin-1")})

    assert response.status_code == 401
    service.generate.assert_not_called()


def test_the_token_does_not_work_in_the_wrong_place(client, service):
    # Only the header counts, not a query string or the body.
    response = client.post(f"{URL}?token={SECRET}", json={**BODY, "token": SECRET})

    assert response.status_code == 401


def test_unauthorized_caller_never_gets_as_far_as_building_the_service(client, monkeypatch):
    # No service override here, so this goes through the real factory. A caller
    # without the token must be stopped before it, not after.
    build = MagicMock()
    monkeypatch.setattr(service_module, "_build_service", build)

    response = client.post(URL, json=BODY)

    assert response.status_code == 401
    build.assert_not_called()


def test_unauthorized_caller_gets_401_even_when_the_provider_key_is_missing(client, monkeypatch):
    # Otherwise the 503 "provider not configured" answer would tell a stranger
    # something about our setup.
    monkeypatch.setattr(
        service_module, "get_settings", lambda: Settings(_env_file=None, magic_hour_api_key=None)
    )

    assert client.post(URL, json=BODY).status_code == 401


# --- the server has no secret -> 503 ----------------------------------------


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param(None, id="not-set"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank"),
    ],
)
def test_server_without_a_secret_is_503_even_with_a_token(client, service, configured):
    configure_secret(configured)

    response = client.post(URL, json=BODY, headers={HEADER: SECRET})

    assert response.status_code == 503
    assert response.json() == {"detail": "Service authentication is not configured."}
    service.generate.assert_not_called()


def test_server_without_a_secret_is_503_without_a_token(client, service):
    configure_secret(None)

    assert client.post(URL, json=BODY).status_code == 503


def test_an_empty_secret_cannot_be_matched_by_an_empty_header(client, service):
    # The dangerous case: "" == "" would let anyone in if blank counted as set.
    configure_secret("")

    response = client.post(URL, json=BODY, headers={HEADER: ""})

    assert response.status_code == 503
    service.generate.assert_not_called()


# --- the health check stays public ------------------------------------------


def test_health_needs_no_token(client):
    response = client.get(HEALTH_URL)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_works_even_when_no_secret_is_configured(client):
    configure_secret(None)

    assert client.get(HEALTH_URL).status_code == 200


# --- the thumbnail endpoint behaves as before once logged in ----------------


def test_bad_input_is_still_a_422_with_a_valid_token(client, service):
    response = client.post(URL, json={"video_topic": ""}, headers={HEADER: SECRET})

    assert response.status_code == 422
    service.generate.assert_not_called()


def test_provider_errors_are_still_mapped_with_a_valid_token(client, service):
    service.generate.side_effect = ProviderRateLimitError()

    response = client.post(URL, json=BODY, headers={HEADER: SECRET})

    assert response.status_code == 429
    assert response.json() == {"detail": ProviderRateLimitError().default_message}


def test_missing_provider_key_is_still_a_503_with_a_valid_token(client, monkeypatch):
    monkeypatch.setattr(
        service_module, "get_settings", lambda: Settings(_env_file=None, magic_hour_api_key=None)
    )

    response = client.post(URL, json=BODY, headers={HEADER: SECRET})

    assert response.status_code == 503
    assert "authentication" not in response.json()["detail"].lower()


# --- the secret never leaks -------------------------------------------------


@pytest.mark.parametrize("sent", [None, "wrong-token-value"], ids=["no-token", "wrong-token"])
def test_a_401_shows_neither_the_real_secret_nor_the_one_sent(client, service, caplog, sent):
    headers = {} if sent is None else {HEADER: sent}

    with caplog.at_level(logging.DEBUG):
        response = client.post(URL, json=BODY, headers=headers)

    assert SECRET not in response.text
    assert SECRET not in caplog.text
    if sent:
        assert sent not in response.text
        assert sent not in caplog.text


def test_a_503_and_its_log_line_do_not_hold_the_token_that_was_sent(client, service, caplog):
    configure_secret(None)

    with caplog.at_level(logging.DEBUG):
        response = client.post(URL, json=BODY, headers={HEADER: SECRET})

    assert response.status_code == 503
    assert SECRET not in response.text
    assert SECRET not in caplog.text
    # The log does say what is wrong, so whoever runs the server can fix it.
    assert "AI_SERVICE_SHARED_SECRET" in caplog.text


def test_success_logs_do_not_hold_the_secret(client, service, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post(URL, json=BODY, headers={HEADER: SECRET})

    assert SECRET not in caplog.text


def test_settings_hide_the_secret_when_printed():
    settings = Settings(_env_file=None, ai_service_shared_secret=SecretStr(SECRET))

    assert SECRET not in repr(settings)
    assert SECRET not in str(settings)


# --- docs -------------------------------------------------------------------


def test_openapi_lists_the_401_for_the_thumbnail_endpoint(client):
    spec = client.get("/openapi.json").json()

    assert "401" in spec["paths"][URL]["post"]["responses"]
    assert "401" not in spec["paths"][HEALTH_URL]["get"]["responses"]
