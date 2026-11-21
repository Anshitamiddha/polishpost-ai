"""Tests for the B2 storage service: object keys, uploads and failures.

The real boto3 client is used with botocore's Stubber (which also checks that our
calls have the right shape), or a fake client. Nothing leaves this computer.
"""

import dataclasses
import logging

import pytest
from botocore import exceptions as boto_errors
from botocore.awsrequest import AWSResponse
from botocore.stub import ANY, Stubber
from pydantic import SecretStr

from app.core.config import Settings
from app.services import b2_client as client_module
from app.services import b2_storage_service as storage_module
from app.services.b2_client import build_b2_client, get_b2_client
from app.services.b2_storage_service import (
    B2StorageService,
    StoredObject,
    build_object_key,
    get_b2_storage_service,
)
from app.services.errors import (
    StorageAuthError,
    StorageError,
    StorageFileError,
    StorageNotConfiguredError,
    StorageRequestError,
    StorageTimeoutError,
    StorageUnavailableError,
)
from b2_fake import BUCKET, ENDPOINT, FakeB2Client, client_error
from magic_hour_fake import image_bytes

# Fake values made for these tests only. Nothing here is a real secret.
KEY_ID = "test-key-id-0001"
APPLICATION_KEY = "test-APPLICATION-key-SECRET"
ASSET = "0123456789abcdef0123456789abcdef"


def settings_with(**overrides) -> Settings:
    values = {
        "b2_key_id": SecretStr(KEY_ID),
        "b2_application_key": SecretStr(APPLICATION_KEY),
        "b2_bucket_name": BUCKET,
        "b2_endpoint_url": ENDPOINT,
        "b2_region": "test-001",
    }
    values.update(overrides)
    # _env_file=None keeps the developer's real .env out of the test.
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def clean_state():
    get_b2_client.cache_clear()
    get_b2_storage_service.cache_clear()
    yield
    get_b2_client.cache_clear()
    get_b2_storage_service.cache_clear()


@pytest.fixture
def picture(tmp_path):
    path = tmp_path / f"{ASSET}.png"
    path.write_bytes(image_bytes("PNG"))
    return path


@pytest.fixture
def fake():
    return FakeB2Client()


@pytest.fixture
def service(fake):
    return B2StorageService(fake, BUCKET)


@pytest.fixture
def stubbed():
    """A real boto3 client with a Stubber, so calls are checked against B2's real API shape."""
    client = build_b2_client(settings_with())
    with Stubber(client) as stubber:
        yield B2StorageService(client, BUCKET), stubber


def assert_message_is_safe(error: Exception, text: str = "") -> None:
    for secret in (KEY_ID, APPLICATION_KEY, "private-detail"):
        assert secret not in str(error)
        assert secret not in text


# --- object keys ----------------------------------------------------------------


def test_the_key_has_the_documented_shape():
    assert build_object_key(12, ASSET, "png") == f"workspaces/12/generated/{ASSET}.png"


@pytest.mark.parametrize("extension", ["png", "jpg", "webp"])
def test_each_stored_ending_is_accepted(extension):
    assert build_object_key(1, ASSET, extension).endswith(f".{extension}")


def test_different_workspaces_and_pictures_get_different_keys():
    other = "f" * 32

    keys = {build_object_key(1, ASSET, "png"), build_object_key(2, ASSET, "png"), build_object_key(1, other, "png")}

    assert len(keys) == 3


@pytest.mark.parametrize("workspace_id", [0, -1, True, False, "12", 1.5, None, [1]], ids=repr)
def test_a_bad_workspace_id_is_refused(workspace_id):
    with pytest.raises(ValueError):
        build_object_key(workspace_id, ASSET, "png")


@pytest.mark.parametrize(
    "asset_id",
    ["", "abc", ASSET[:-1], ASSET + "0", ASSET.upper(), "../" + ASSET[:29], ASSET[:31] + "/", ASSET[:31] + ".", None],
    ids=repr,
)
def test_a_bad_asset_id_is_refused(asset_id):
    with pytest.raises(ValueError):
        build_object_key(1, asset_id, "png")


@pytest.mark.parametrize("extension", ["", "gif", "jpeg", "PNG", "png/../x", ".png"])
def test_a_bad_extension_is_refused(extension):
    with pytest.raises(ValueError):
        build_object_key(1, ASSET, extension)


def test_a_key_cannot_climb_out_of_its_folder():
    key = build_object_key(2**63 - 1, ASSET, "png")

    assert key.startswith("workspaces/") and ".." not in key and not key.startswith("/")


# --- a good upload ----------------------------------------------------------------


def test_a_good_upload_sends_the_file_under_the_workspace_key(service, fake, picture):
    stored = service.upload_image(picture, 12, ASSET, "png")

    key = f"workspaces/12/generated/{ASSET}.png"
    assert stored == StoredObject(object_key=key, size_bytes=picture.stat().st_size, content_type="image/png")
    (put,) = fake.puts
    assert put == {"bucket": BUCKET, "key": key, "content_type": "image/png", "body": picture.read_bytes()}


@pytest.mark.parametrize(
    "extension, content_type", [("png", "image/png"), ("jpg", "image/jpeg"), ("webp", "image/webp")]
)
def test_the_content_type_follows_the_file_ending(service, fake, picture, extension, content_type):
    service.upload_image(picture, 1, ASSET, extension)

    assert fake.puts[0]["content_type"] == content_type


def test_the_result_holds_no_link(service, picture):
    stored = service.upload_image(picture, 1, ASSET, "png")

    assert {field.name for field in dataclasses.fields(stored)} == {"object_key", "size_bytes", "content_type"}
    assert "http" not in repr(stored)


def test_an_upload_only_uploads(service, fake, picture):
    service.upload_image(picture, 1, ASSET, "png")

    # No download, no public or presigned link, no listing, no delete.
    assert fake.calls == ["put_object"]


def test_the_local_file_is_left_alone_after_an_upload(service, picture):
    before = picture.read_bytes()

    service.upload_image(picture, 1, ASSET, "png")

    assert picture.read_bytes() == before


def test_the_call_matches_b2s_api_shape(stubbed, picture):
    service, stubber = stubbed
    key = f"workspaces/3/generated/{ASSET}.png"
    stubber.add_response(
        "put_object",
        {"ETag": '"abc"'},
        expected_params={"Bucket": BUCKET, "Key": key, "Body": ANY, "ContentType": "image/png"},
    )

    stored = service.upload_image(picture, 3, ASSET, "png")

    stubber.assert_no_pending_responses()
    assert stored.object_key == key


def test_an_upload_goes_out_as_a_plain_body_not_aws_chunked(picture):
    # With boto3's newer default, uploads carry a trailing checksum (aws-chunked) that
    # Backblaze has rejected. This watches the real request the client builds.
    client = build_b2_client(settings_with())
    sent = {}

    class Raw:
        def stream(self, *args, **kwargs):
            yield b""

        def read(self, *args, **kwargs):
            return b""

    def intercept(request, **kwargs):
        sent["headers"] = {key.lower(): value for key, value in request.headers.items()}
        return AWSResponse(request.url, 200, {"ETag": '"abc"'}, Raw())

    client.meta.events.register("before-send.s3.PutObject", intercept)

    B2StorageService(client, BUCKET).upload_image(picture, 1, ASSET, "png")

    headers = sent["headers"]
    assert "content-encoding" not in headers  # no aws-chunked
    assert "x-amz-trailer" not in headers
    assert "x-amz-sdk-checksum-algorithm" not in headers
    assert int(headers["content-length"]) == picture.stat().st_size


# --- a local file that cannot be uploaded ------------------------------------------


def test_a_missing_file_is_refused_before_any_network_call(service, fake, tmp_path):
    with pytest.raises(StorageFileError) as caught:
        service.upload_image(tmp_path / "ghost.png", 1, ASSET, "png")

    assert fake.calls == []
    assert "ghost" not in str(caught.value) and str(tmp_path) not in str(caught.value)


def test_a_folder_is_not_a_picture(service, fake, tmp_path):
    with pytest.raises(StorageFileError):
        service.upload_image(tmp_path, 1, ASSET, "png")

    assert fake.calls == []


def test_an_empty_file_is_never_uploaded(service, fake, tmp_path):
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")

    with pytest.raises(StorageFileError):
        service.upload_image(empty, 1, ASSET, "png")

    assert fake.calls == []


def test_a_file_over_the_size_limit_is_never_uploaded(service, fake, picture, monkeypatch):
    monkeypatch.setattr(storage_module, "MAX_UPLOAD_BYTES", 100)

    with pytest.raises(StorageFileError):
        service.upload_image(picture, 1, ASSET, "png")

    assert fake.calls == []


def test_a_file_that_cannot_be_opened_is_a_file_error(service, fake, picture, monkeypatch):
    def refuse(self, *args, **kwargs):
        raise PermissionError("access denied: C:/private/place")

    monkeypatch.setattr(storage_module.Path, "open", refuse)

    with pytest.raises(StorageFileError) as caught:
        service.upload_image(picture, 1, ASSET, "png")

    assert fake.calls == []
    assert "private" not in str(caught.value)


def test_a_bad_key_part_is_refused_before_any_network_call(service, fake, picture):
    with pytest.raises(ValueError):
        service.upload_image(picture, 0, ASSET, "png")

    assert fake.calls == []


# --- B2 answers with a failure -------------------------------------------------------


@pytest.mark.parametrize(
    "status, code, expected",
    [
        (403, "AccessDenied", StorageAuthError),
        (403, "SignatureDoesNotMatch", StorageAuthError),
        (401, "InvalidAccessKeyId", StorageAuthError),
        (404, "NoSuchBucket", StorageNotConfiguredError),
        (301, "PermanentRedirect", StorageNotConfiguredError),
        (500, "InternalError", StorageUnavailableError),
        (503, "ServiceUnavailable", StorageUnavailableError),
        (503, "SlowDown", StorageUnavailableError),
        (429, "TooManyRequests", StorageUnavailableError),
        (408, "RequestTimeout", StorageUnavailableError),
        (400, "RequestTimeout", StorageUnavailableError),  # B2 sends this one as a 400
        (400, "InvalidRequest", StorageRequestError),
        (409, "Conflict", StorageRequestError),
        (413, "EntityTooLarge", StorageRequestError),
    ],
)
def test_each_b2_failure_becomes_the_right_error(stubbed, picture, caplog, status, code, expected):
    service, stubber = stubbed
    stubber.add_client_error("put_object", service_error_code=code, service_message="private-detail", http_status_code=status)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(StorageError) as caught:
        service.upload_image(picture, 1, ASSET, "png")

    assert type(caught.value) is expected
    assert isinstance(caught.value.__cause__, boto_errors.ClientError)
    assert_message_is_safe(caught.value, caplog.text)


# --- network trouble -------------------------------------------------------------------


@pytest.mark.parametrize(
    "error, expected",
    [
        (boto_errors.ConnectTimeoutError(endpoint_url=ENDPOINT), StorageTimeoutError),
        (boto_errors.ReadTimeoutError(endpoint_url=ENDPOINT), StorageTimeoutError),
        (boto_errors.EndpointConnectionError(endpoint_url=ENDPOINT), StorageUnavailableError),
        (boto_errors.ConnectionClosedError(endpoint_url=ENDPOINT), StorageUnavailableError),
        (boto_errors.SSLError(endpoint_url=ENDPOINT, error="handshake failed"), StorageUnavailableError),
        (ConnectionResetError("reset by peer"), StorageUnavailableError),
        (boto_errors.ParamValidationError(report="bad parameter"), StorageRequestError),
        (boto_errors.BotoCoreError(), StorageRequestError),
    ],
    ids=["connect-timeout", "read-timeout", "unreachable", "closed", "ssl", "raw-os-error", "bad-params", "other"],
)
def test_network_trouble_becomes_the_right_error(service, fake, picture, error, expected):
    fake.put_error = error

    with pytest.raises(StorageError) as caught:
        service.upload_image(picture, 1, ASSET, "png")

    assert type(caught.value) is expected
    assert caught.value.__cause__ is error


def test_a_timeout_is_a_kind_of_unavailable():
    assert issubclass(StorageTimeoutError, StorageUnavailableError)


# --- a failed upload leaves things as they were -------------------------------------------


@pytest.mark.parametrize(
    "error",
    [client_error(403, "AccessDenied"), boto_errors.ConnectTimeoutError(endpoint_url=ENDPOINT)],
    ids=["refused", "timeout"],
)
def test_a_failed_upload_stores_nothing_and_keeps_the_local_file(service, fake, picture, error):
    before = picture.read_bytes()
    fake.put_error = error

    with pytest.raises(StorageError):
        service.upload_image(picture, 1, ASSET, "png")

    assert fake.puts == []
    assert picture.read_bytes() == before
    assert sorted(p.name for p in picture.parent.iterdir()) == [picture.name]  # no temporary files


def test_the_file_is_closed_after_a_failure(service, fake, picture):
    fake.put_error = client_error(500, "InternalError")

    with pytest.raises(StorageError):
        service.upload_image(picture, 1, ASSET, "png")

    picture.unlink()  # a file still held open could not be deleted on Windows
    assert not picture.exists()


def test_credentials_never_reach_errors_or_logs(picture, caplog):
    client = build_b2_client(settings_with())
    caplog.set_level(logging.DEBUG)

    with Stubber(client) as stubber:
        stubber.add_client_error("put_object", service_error_code="AccessDenied", service_message="private-detail", http_status_code=403)
        with pytest.raises(StorageAuthError) as caught:
            B2StorageService(client, BUCKET).upload_image(picture, 1, ASSET, "png")

    assert_message_is_safe(caught.value, caplog.text)
    assert KEY_ID not in caplog.text and APPLICATION_KEY not in caplog.text


# --- the check before generation ------------------------------------------------------------


def test_a_ready_bucket_passes_the_check(service, fake):
    service.check_ready()

    assert fake.head_calls == [{"Bucket": BUCKET}]
    assert fake.calls == ["head_bucket"]  # it only looks, it uploads nothing


@pytest.mark.parametrize(
    "status, expected",
    [
        (403, StorageAuthError),
        (401, StorageAuthError),
        (404, StorageNotConfiguredError),
        (301, StorageNotConfiguredError),
        (307, StorageNotConfiguredError),
        (400, StorageNotConfiguredError),
        (500, StorageUnavailableError),
    ],
)
def test_a_bucket_that_refuses_us_fails_the_check(stubbed, status, expected):
    service, stubber = stubbed
    stubber.add_client_error("head_bucket", http_status_code=status)

    with pytest.raises(StorageError) as caught:
        service.check_ready()

    assert type(caught.value) is expected
    assert_message_is_safe(caught.value)


@pytest.mark.parametrize(
    "error, expected",
    [
        (boto_errors.ConnectTimeoutError(endpoint_url=ENDPOINT), StorageTimeoutError),
        (boto_errors.ReadTimeoutError(endpoint_url=ENDPOINT), StorageTimeoutError),
        (boto_errors.EndpointConnectionError(endpoint_url=ENDPOINT), StorageUnavailableError),
        (boto_errors.ParamValidationError(report="bad bucket name"), StorageNotConfiguredError),
        (boto_errors.BotoCoreError(), StorageUnavailableError),
    ],
    ids=["connect-timeout", "read-timeout", "unreachable", "bad-bucket-name", "other"],
)
def test_network_trouble_fails_the_check(service, fake, error, expected):
    fake.head_error = error

    with pytest.raises(StorageError) as caught:
        service.check_ready()

    assert type(caught.value) is expected


# --- building the shared service -------------------------------------------------------------


def test_the_shared_service_reuses_the_existing_client_and_the_settings(monkeypatch):
    fake = FakeB2Client()
    monkeypatch.setattr(storage_module, "get_b2_client", lambda: fake)
    monkeypatch.setattr(storage_module, "get_settings", lambda: settings_with(b2_bucket_name="  my-bucket  "))

    service = get_b2_storage_service()

    assert service is get_b2_storage_service()
    assert service._client is fake
    assert service._bucket_name == "my-bucket"


def test_missing_b2_settings_are_a_safe_not_configured_error(monkeypatch, caplog):
    monkeypatch.setattr(client_module, "get_settings", lambda: Settings(_env_file=None))
    caplog.set_level(logging.DEBUG)

    with pytest.raises(StorageNotConfiguredError) as caught:
        get_b2_storage_service()

    assert "B2_KEY_ID" not in str(caught.value)  # the user-facing text names no settings
    assert "B2_KEY_ID" in caplog.text  # the log does, so whoever runs the server can fix it
    assert isinstance(caught.value.__cause__, client_module.B2ConfigurationError)


def test_the_client_config_asks_for_checksums_only_when_required():
    config = build_b2_client(settings_with()).meta.config

    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"


def test_every_storage_error_is_separate_from_generation_errors():
    from app.services.errors import ContentGenerationError, ImageGeneratedButNotStoredError

    for error in (StorageError, StorageFileError, ImageGeneratedButNotStoredError):
        assert not issubclass(error, ContentGenerationError)
    assert issubclass(ImageGeneratedButNotStoredError, StorageError)

