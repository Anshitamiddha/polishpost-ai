"""Tests for POST /api/v1/publish/thumbnails.

These use a small app that holds only the thumbnail route, so they do not depend
on the rest of the service. One test at the end checks the real app serves the
route. Magic Hour is never called: the service is a stand-in, or the real one
pointed at a local fake (see magic_hour_fake.py).
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from magic_hour import Client
from pydantic import SecretStr

from app.api.routes import thumbnails
from app.core.config import Settings, get_settings
from app.schemas.thumbnail import ThumbnailImage, ThumbnailRequest, ThumbnailResponse
from app.services import thumbnail_generation_service as service_module
from app.services.errors import (
    ImageNotCreatedError,
    ImageNotSavedError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.thumbnail_generation_service import (
    ThumbnailGenerationService,
    get_thumbnail_generation_service,
)
from magic_hour_fake import FakeMagicHour

URL = "/api/v1/publish/thumbnails"
HEADER = "X-Internal-Service-Token"
# Fake values made for these tests only. Nothing here is a real secret.
SECRET = "unit-test-shared-secret"
KEY = "mh-SUPER-SECRET-key-123"
BODY = {
    "video_topic": "Sunrise hike in the Alps",
    "heading": "ALPS AT DAWN",
    "subtitle": "You will not believe this view",
    "visual_style": "cinematic, golden light",
}
GOOD_RESULT = ThumbnailResponse(
    status="complete",
    image=ThumbnailImage(reference="abc123.png", width=640, height=360, format="png"),
    provider_generation_id="job-1",
    credits_charged=5,
)

app = FastAPI()
app.include_router(thumbnails.router, prefix="/api/v1")


# --- helpers ------------------------------------------------------------------


def configure_secret(value: str | None) -> None:
    """Pretend the server was started with this shared secret."""
    # _env_file=None keeps the developer's real .env out of the test.
    settings = Settings(_env_file=None, ai_service_shared_secret=None if value is None else SecretStr(value))
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
    """A stand-in service, so no test here reaches Magic Hour."""
    stand_in = MagicMock(spec=ThumbnailGenerationService)
    stand_in.generate.return_value = GOOD_RESULT
    app.dependency_overrides[thumbnails.get_thumbnail_service] = lambda: stand_in
    return stand_in


def post(client, body=BODY, token=SECRET):
    headers = {} if token is None else {HEADER: token}
    return client.post(URL, json=body, headers=headers)


# --- a good request -----------------------------------------------------------


def test_a_good_request_returns_the_normalized_answer(client, service):
    response = post(client)

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "status": "complete",
        "image": {"reference": "abc123.png", "width": 640, "height": 360, "format": "png"},
        "provider_generation_id": "job-1",
        "credits_charged": 5,
    }
    service.generate.assert_called_once_with(ThumbnailRequest(**BODY))


def test_the_subtitle_is_optional(client, service):
    without_subtitle = {key: value for key, value in BODY.items() if key != "subtitle"}

    assert post(client, without_subtitle).status_code == 200
    assert service.generate.call_args.args[0].subtitle is None


def test_spaces_around_the_text_are_trimmed(client, service):
    post(client, {**BODY, "heading": "   ALPS AT DAWN   "})

    assert service.generate.call_args.args[0].heading == "ALPS AT DAWN"


# --- bad requests ---------------------------------------------------------------


@pytest.mark.parametrize("missing", ["video_topic", "heading", "visual_style"])
def test_each_required_field_is_required(client, service, missing):
    body = {key: value for key, value in BODY.items() if key != missing}

    response = post(client, body)

    assert response.status_code == 422
    service.generate.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"video_topic": "  "},  # blank after trimming
        {"video_topic": "ab"},  # too short
        {"video_topic": "x" * 301},
        {"heading": " "},
        {"heading": "x" * 61},  # a headline must be readable at a glance
        {"subtitle": "  "},  # present but empty
        {"subtitle": "x" * 101},
        {"visual_style": "ab"},
        {"visual_style": "x" * 501},
        {"heading": 123},  # wrong type
        {"unknown_field": "x"},  # unknown fields are errors
    ],
    ids=lambda change: next(iter(change)) + "-" + str(next(iter(change.values())))[:8],
)
def test_bad_values_are_rejected_before_the_service(client, service, change):
    response = post(client, {**BODY, **change})

    assert response.status_code == 422
    service.generate.assert_not_called()


def test_an_empty_body_is_rejected(client, service):
    assert client.post(URL, json={}, headers={HEADER: SECRET}).status_code == 422
    assert client.post(URL, content=b"not json", headers={HEADER: SECRET}).status_code == 422


# --- internal service authentication -------------------------------------------


@pytest.mark.parametrize("token", [None, "", "wrong-secret", SECRET + "x"], ids=["missing", "empty", "wrong", "almost"])
def test_a_request_without_the_right_token_is_refused(client, service, token):
    response = post(client, token=token)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid service token."}
    service.generate.assert_not_called()


def test_the_token_is_checked_before_the_body_and_before_the_service_is_built(client):
    def must_not_be_reached():
        raise AssertionError("the service was built for a caller without the token")

    app.dependency_overrides[thumbnails.get_thumbnail_service] = must_not_be_reached

    assert post(client, body={}, token=None).status_code == 401


def test_without_a_configured_secret_every_request_is_a_503(client, service):
    configure_secret(None)

    response = post(client)

    assert response.status_code == 503
    service.generate.assert_not_called()


# --- missing Magic Hour credentials ----------------------------------------------


@pytest.fixture
def no_magic_hour_key(monkeypatch):
    monkeypatch.setattr(service_module, "get_settings", lambda: Settings(_env_file=None, magic_hour_api_key=None))
    get_thumbnail_generation_service.cache_clear()


def test_a_missing_magic_hour_key_is_a_safe_503(client, no_magic_hour_key):
    response = post(client)  # the real service builder runs, and refuses

    assert response.status_code == 503
    assert response.json() == {"detail": "The AI service is not configured correctly."}
    assert "MAGIC_HOUR" not in response.text


def test_a_caller_without_the_token_learns_nothing_about_the_missing_key(client, no_magic_hour_key):
    assert post(client, token=None).status_code == 401


# --- failures become the right HTTP answers ---------------------------------------


@pytest.mark.parametrize(
    "error, status",
    [
        (ProviderAuthError, 503),
        (ProviderRateLimitError, 429),
        (ProviderUnavailableError, 503),
        (ProviderTimeoutError, 503),
        (ProviderRequestError, 502),
        (InvalidModelOutputError, 502),
        (ImageNotCreatedError, 502),
        (ImageNotSavedError, 500),
    ],
)
def test_each_service_error_has_its_own_status_and_safe_text(client, service, error, status):
    service.generate.side_effect = error()

    response = post(client)

    assert response.status_code == status
    assert response.json() == {"detail": str(error())}


def test_an_unexpected_failure_is_a_bland_500(client, service):
    service.generate.side_effect = RuntimeError(f"disk path C:/secret/place and key {KEY}")

    response = TestClient(app, raise_server_exceptions=False).post(URL, json=BODY, headers={HEADER: SECRET})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert KEY not in response.text and "secret/place" not in response.text


# --- the whole stack: route, service, real SDK, fake Magic Hour, Pillow, disk ---------


@pytest.fixture
def fake():
    server = FakeMagicHour().start()
    yield server
    server.stop()


@pytest.fixture
def real_service(fake, tmp_path):
    client = Client(token=KEY, base_url=fake.url, timeout=5)
    real = ThumbnailGenerationService(client, "z-image-turbo", "640px", tmp_path / "thumbs", 5.0, 0.01)
    app.dependency_overrides[thumbnails.get_thumbnail_service] = lambda: real
    return real


def test_a_full_run_saves_the_picture_and_answers_without_paths(client, fake, real_service, tmp_path):
    response = post(client)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"success", "status", "image", "provider_generation_id", "credits_charged"}
    assert body["success"] is True and body["status"] == "complete"
    assert (body["image"]["width"], body["image"]["height"], body["image"]["format"]) == (640, 360, "png")
    assert (tmp_path / "thumbs" / body["image"]["reference"]).is_file()
    assert str(tmp_path) not in response.text
    assert KEY not in response.text


@pytest.mark.parametrize(
    "provider_status, http_status",
    [(401, 503), (429, 429), (500, 503), (400, 502)],
)
def test_a_provider_refusal_reaches_the_caller_as_a_safe_answer(
    client, fake, real_service, provider_status, http_status
):
    fake.create_reply = (provider_status, {"message": "provider-private-detail"})

    response = post(client)

    assert response.status_code == http_status
    assert "provider-private-detail" not in response.text
    assert KEY not in response.text and "Bearer" not in response.text


def test_a_job_that_fails_at_magic_hour_is_a_502(client, fake, real_service):
    fake.poll_replies = [fake.project("error", error={"code": "x", "message": "private"})]

    response = post(client)

    assert response.status_code == 502
    assert response.json() == {"detail": str(ImageNotCreatedError())}


# --- the real app ----------------------------------------------------------------


def test_the_real_app_serves_the_thumbnail_route():
    # Importing the real app also loads the Gemini text code. If that cannot load
    # in this environment, the check is skipped rather than failing.
    main = pytest.importorskip("app.main")

    assert "post" in main.app.openapi()["paths"][URL]
