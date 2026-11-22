"""Tests for POST /api/v1/publish/thumbnails.

These use a small app that holds only the thumbnail route, so they do not depend
on the rest of the service. One test at the end checks the real app serves the
route. Magic Hour is never called: the service is a stand-in, or the real one
pointed at a local fake (see magic_hour_fake.py).
"""

from unittest.mock import MagicMock

import pytest
from botocore import exceptions as boto_errors
from fastapi import FastAPI
from fastapi.testclient import TestClient
from magic_hour import Client
from pydantic import SecretStr

from app.api.routes import thumbnails
from app.core.config import Settings, get_settings
from app.schemas.thumbnail import ThumbnailImage, ThumbnailRequest, ThumbnailResponse
from app.services.b2_storage_service import B2StorageService
from app.services import thumbnail_generation_service as service_module
from app.services.errors import (
    ImageGeneratedButNotStoredError,
    ImageNotCreatedError,
    ImageNotSavedError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    StorageAuthError,
    StorageFileError,
    StorageNotConfiguredError,
    StorageRequestError,
    StorageTimeoutError,
    StorageUnavailableError,
)
from app.services.thumbnail_generation_service import (
    ThumbnailGenerationService,
    get_thumbnail_generation_service,
)
from b2_fake import BUCKET, FakeB2Client, client_error
from magic_hour_fake import FakeMagicHour

URL = "/api/v1/publish/thumbnails"
HEADER = "X-Internal-Service-Token"
# Fake values made for these tests only. Nothing here is a real secret.
SECRET = "unit-test-shared-secret"
KEY = "mh-SUPER-SECRET-key-123"
BODY = {
    "workspace_id": 12,
    "video_topic": "Sunrise hike in the Alps",
    "heading": "ALPS AT DAWN",
    "subtitle": "You will not believe this view",
    "visual_style": "cinematic, golden light",
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
        "image": {
            "reference": "abc123.png",
            "width": 640,
            "height": 360,
            "format": "png",
            "asset_id": "abc123",
            "object_key": "workspaces/12/generated/abc123.png",
            "content_type": "image/png",
            "size_bytes": 1234,
        },
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


@pytest.mark.parametrize("missing", ["workspace_id", "video_topic", "heading"])
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


def test_the_creative_prompt_is_optional_but_not_empty_when_given(client, service):
    without_prompt = {key: value for key, value in BODY.items() if key != "visual_style"}

    assert post(client, without_prompt).status_code == 200
    assert service.generate.call_args.args[0].visual_style is None
    assert post(client, {**BODY, "visual_style": "  "}).status_code == 422  # given, but blank


def test_the_request_has_no_field_for_a_number_of_pictures():
    assert set(ThumbnailRequest.model_fields) == {
        "workspace_id",
        "video_topic",
        "heading",
        "subtitle",
        "visual_style",
    }


@pytest.mark.parametrize("field", ["image_count", "count", "variations", "num_images", "number_of_images"])
def test_a_request_cannot_ask_for_more_than_one_picture(client, service, field):
    response = post(client, {**BODY, field: 3})

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
def b2():
    return FakeB2Client()


@pytest.fixture
def real_service(fake, b2, tmp_path):
    client = Client(token=KEY, base_url=fake.url, timeout=5)
    real = ThumbnailGenerationService(
        client, "z-image-turbo", "640px", tmp_path / "thumbs", 5.0, 0.01, storage=B2StorageService(b2, BUCKET)
    )
    app.dependency_overrides[thumbnails.get_thumbnail_service] = lambda: real
    return real


def test_a_full_run_asks_magic_hour_once_and_answers_with_one_picture(client, fake, b2, real_service):
    response = post(client)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["image"], dict)  # one picture, not a list
    assert "images" not in body
    assert len(fake.creates()) == 1
    assert fake.creates()[0]["body"]["image_count"] == 1
    assert len(b2.puts) == 1


def test_the_global_prompt_travels_from_the_request_to_magic_hour(client, fake, real_service):
    prompt = "Create a bold, cinematic YouTube thumbnail. Leave space for a short headline."

    response = post(client, {**BODY, "visual_style": prompt})

    assert response.status_code == 200
    (create,) = fake.creates()
    sent = create["body"]["style"]["prompt"]
    assert prompt in sent
    assert BODY["video_topic"] in sent and BODY["heading"] in sent


def test_a_request_without_a_prompt_still_reaches_magic_hour(client, fake, real_service):
    without_prompt = {key: value for key, value in BODY.items() if key != "visual_style"}

    assert post(client, without_prompt).status_code == 200
    (create,) = fake.creates()
    assert "Creative direction" not in create["body"]["style"]["prompt"]


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
    from app.main import app

    assert "post" in app.openapi()["paths"][URL]


# --- the workspace id ---------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [0, -1, "12", "abc", 12.5, 12.0, True, False, None, [12], {"id": 12}, 2**63],
    ids=repr,
)
def test_a_bad_workspace_id_is_rejected_before_the_service(client, service, value):
    response = post(client, {**BODY, "workspace_id": value})

    assert response.status_code == 422
    service.generate.assert_not_called()


@pytest.mark.parametrize("value", [1, 12, 2**63 - 1])
def test_a_good_workspace_id_reaches_the_service_as_a_whole_number(client, service, value):
    assert post(client, {**BODY, "workspace_id": value}).status_code == 200

    sent = service.generate.call_args.args[0].workspace_id
    assert sent == value and type(sent) is int


def test_the_workspace_id_is_only_read_from_the_body(client, service):
    without = {key: value for key, value in BODY.items() if key != "workspace_id"}

    response = client.post(
        f"{URL}?workspace_id=5", json=without, headers={HEADER: SECRET, "X-Workspace-Id": "5"}
    )

    assert response.status_code == 422
    service.generate.assert_not_called()


def test_the_workspace_id_does_not_replace_the_token_check(client, service):
    assert post(client, token=None).status_code == 401
    assert post(client, token="wrong-secret").status_code == 401
    service.generate.assert_not_called()


# --- storage failures become their own answers -------------------------------------------


def generated_but_not_stored(cause=None) -> ImageGeneratedButNotStoredError:
    error = ImageGeneratedButNotStoredError()
    error.__cause__ = cause
    return error


@pytest.mark.parametrize(
    "error, status",
    [
        (StorageNotConfiguredError(), 503),
        (StorageAuthError(), 503),
        (StorageUnavailableError(), 503),
        (StorageTimeoutError(), 503),
        (StorageRequestError(), 502),
        (StorageFileError(), 500),
        (generated_but_not_stored(StorageUnavailableError()), 503),
        (generated_but_not_stored(StorageTimeoutError()), 503),
        (generated_but_not_stored(StorageAuthError()), 503),
        (generated_but_not_stored(StorageRequestError()), 502),
        (generated_but_not_stored(StorageFileError()), 500),
        (generated_but_not_stored(), 503),  # cause unknown
    ],
    ids=lambda value: (
        type(value).__name__ + (f"<-{type(value.__cause__).__name__}" if value.__cause__ else "")
        if isinstance(value, Exception)
        else str(value)
    ),
)
def test_each_storage_error_has_its_own_status_and_safe_text(client, service, error, status):
    service.generate.side_effect = error

    response = post(client)

    assert response.status_code == status
    assert response.json() == {"detail": str(error)}


def test_a_generated_but_not_stored_answer_says_so_and_the_others_do_not(client, service):
    texts = {}
    for name, error in {
        "generation": ProviderRateLimitError(),
        "preflight": StorageUnavailableError(),
        "after": generated_but_not_stored(StorageUnavailableError()),
    }.items():
        service.generate.side_effect = error
        texts[name] = post(client).json()["detail"]

    assert "generated, but it could not be stored" in texts["after"]
    assert "kept on the server" in texts["after"]
    assert "generated" not in texts["generation"] and "generated" not in texts["preflight"]
    assert len(set(texts.values())) == 3  # a caller can tell the three apart


# --- missing B2 settings -----------------------------------------------------------------


@pytest.fixture
def storage_not_configured(monkeypatch):
    monkeypatch.setattr(service_module, "get_settings", lambda: Settings(_env_file=None, magic_hour_api_key=SecretStr(KEY)))

    def refuse():
        raise StorageNotConfiguredError()

    monkeypatch.setattr(service_module, "get_b2_storage_service", refuse)
    get_thumbnail_generation_service.cache_clear()


def test_unconfigured_storage_is_a_safe_503_before_anything_is_built(client, storage_not_configured):
    response = post(client)  # the real service builder runs, and refuses

    assert response.status_code == 503
    assert response.json() == {"detail": "File storage is not configured correctly."}
    assert "B2_" not in response.text and KEY not in response.text


def test_a_caller_without_the_token_learns_nothing_about_the_storage_setup(client, storage_not_configured):
    assert post(client, token=None).status_code == 401


# --- the whole stack with B2 -----------------------------------------------------------------


def test_a_full_run_stores_the_picture_and_answers_with_its_key(client, fake, b2, real_service, tmp_path):
    response = post(client, {**BODY, "workspace_id": 31})

    assert response.status_code == 200
    image = response.json()["image"]
    assert image["object_key"] == f"workspaces/31/generated/{image['asset_id']}.png"
    assert image["content_type"] == "image/png"
    local = tmp_path / "thumbs" / image["reference"]
    assert image["size_bytes"] == local.stat().st_size
    (put,) = b2.puts
    assert (put["key"], put["body"]) == (image["object_key"], local.read_bytes())
    # The bucket stays private: no bucket name, no endpoint, no link, no path.
    assert BUCKET not in response.text and "http" not in response.text and str(tmp_path) not in response.text


def test_storage_down_means_a_503_and_no_paid_job(client, fake, b2, real_service, tmp_path):
    b2.head_error = boto_errors.EndpointConnectionError(endpoint_url="https://s3.example.invalid")

    response = post(client)

    assert response.status_code == 503
    assert response.json() == {"detail": str(StorageUnavailableError())}
    assert fake.requests == []  # Magic Hour was never asked
    assert not (tmp_path / "thumbs").exists()


def test_a_failed_upload_after_generation_is_a_clear_503_and_the_picture_is_kept(client, fake, b2, real_service, tmp_path):
    b2.put_error = boto_errors.ReadTimeoutError(endpoint_url="https://s3.example.invalid")

    response = post(client)

    assert response.status_code == 503
    assert response.json() == {"detail": str(ImageGeneratedButNotStoredError())}
    assert len(fake.creates()) == 1
    kept = sorted(p.suffix for p in (tmp_path / "thumbs").iterdir())
    assert kept == [".json", ".png"]  # the picture and the note for a retry


def test_a_refused_upload_is_a_502(client, fake, b2, real_service):
    b2.put_error = client_error(400, "InvalidRequest")

    response = post(client)

    assert response.status_code == 502
    assert response.json() == {"detail": str(ImageGeneratedButNotStoredError())}


def test_a_magic_hour_failure_is_still_its_own_answer_and_never_touches_storage(client, fake, b2, real_service):
    fake.create_reply = (429, {"message": "provider-private-detail"})

    response = post(client)

    assert response.status_code == 429
    assert response.json() == {"detail": str(ProviderRateLimitError())}
    assert b2.puts == []
