"""Tests for the Backblaze B2 connection check (HeadBucket only).

boto3's own Stubber stands in for Backblaze, so the real S3 client code runs but
nothing is sent over the network, and no credit or bucket is ever touched.
"""

import socket
from unittest.mock import MagicMock, call

import pytest
from botocore import exceptions as boto_errors
from botocore.stub import Stubber
from pydantic import SecretStr

from app.core.config import Settings
from app.services import b2_client as client_module
from app.services import b2_connection_check as check_module
from app.services.b2_client import B2ConfigurationError, build_b2_client, get_b2_client
from app.services.b2_connection_check import B2ConnectionError, check_b2_connection

# Fake values made for these tests only. Nothing here is a real secret.
KEY_ID = "test-key-id-0001"
APPLICATION_KEY = "test-APPLICATION-key-SECRET"
BUCKET = "PublishProAI"
ENDPOINT = "https://s3.us-west-004.backblazeb2.com"
REGION = "us-west-004"


def settings_with(**overrides) -> Settings:
    values = {
        "b2_key_id": SecretStr(KEY_ID),
        "b2_application_key": SecretStr(APPLICATION_KEY),
        "b2_bucket_name": BUCKET,
        "b2_endpoint_url": ENDPOINT,
        "b2_region": REGION,
    }
    values.update(overrides)
    # _env_file=None keeps the developer's real .env out of the test.
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def clean_state():
    get_b2_client.cache_clear()
    yield
    get_b2_client.cache_clear()


@pytest.fixture
def client():
    """A real boto3 S3 client, built the way the service builds it."""
    return build_b2_client(settings_with())


def fake_client() -> MagicMock:
    """A stand-in for a client that fails in ways a Stubber cannot imitate."""
    stand_in = MagicMock()
    stand_in.meta.endpoint_url = ENDPOINT
    stand_in.meta.region_name = REGION
    return stand_in


# --- a good check -------------------------------------------------------------


def test_a_reachable_bucket_passes_with_one_head_bucket_call(client):
    with Stubber(client) as stubber:
        stubber.add_response("head_bucket", {}, {"Bucket": BUCKET})

        check_b2_connection(client, BUCKET)

        stubber.assert_no_pending_responses()


def test_head_bucket_is_the_only_operation_ever_called():
    stand_in = fake_client()

    check_b2_connection(stand_in, BUCKET)

    assert stand_in.mock_calls == [call.head_bucket(Bucket=BUCKET)]


# --- Backblaze says no --------------------------------------------------------


@pytest.mark.parametrize(
    "status, kind",
    [
        (401, "access_denied"),
        (403, "access_denied"),
        (404, "bucket_not_found"),
        (301, "endpoint_or_region"),
        (307, "endpoint_or_region"),
        (400, "endpoint_or_region"),
        (500, "unexpected"),
        (503, "unexpected"),
    ],
)
def test_each_refusal_becomes_its_own_kind_of_error(client, status, kind):
    with Stubber(client) as stubber:
        stubber.add_client_error(
            "head_bucket",
            service_error_code=str(status),
            service_message="private provider text",
            http_status_code=status,
            expected_params={"Bucket": BUCKET},
        )

        with pytest.raises(B2ConnectionError) as caught:
            check_b2_connection(client, BUCKET)

    assert caught.value.kind == kind
    assert "private provider text" not in str(caught.value)
    if kind != "unexpected":
        assert BUCKET in str(caught.value)
    else:
        assert str(status) in str(caught.value)


def test_a_refusal_is_not_retried_by_the_check():
    stand_in = fake_client()
    stand_in.head_bucket.side_effect = boto_errors.ClientError(
        {"Error": {"Code": "403"}, "ResponseMetadata": {"HTTPStatusCode": 403}}, "HeadBucket"
    )

    with pytest.raises(B2ConnectionError):
        check_b2_connection(stand_in, BUCKET)

    assert stand_in.head_bucket.call_count == 1


# --- the network fails --------------------------------------------------------


@pytest.mark.parametrize(
    "failure, kind",
    [
        (boto_errors.ConnectTimeoutError(endpoint_url=ENDPOINT), "timeout"),
        (boto_errors.ReadTimeoutError(endpoint_url=ENDPOINT, error="timed out"), "timeout"),
        (boto_errors.EndpointConnectionError(endpoint_url=ENDPOINT), "unreachable"),
        (boto_errors.ConnectionClosedError(endpoint_url=ENDPOINT), "unreachable"),
        (boto_errors.SSLError(endpoint_url=ENDPOINT, error="bad certificate"), "unreachable"),
        (boto_errors.NoCredentialsError(), "unexpected"),
    ],
    ids=["connect-timeout", "read-timeout", "cannot-connect", "connection-closed", "tls-problem", "other-boto-error"],
)
def test_a_network_failure_becomes_a_clear_error(failure, kind):
    stand_in = fake_client()
    stand_in.head_bucket.side_effect = failure

    with pytest.raises(B2ConnectionError) as caught:
        check_b2_connection(stand_in, BUCKET)

    assert caught.value.kind == kind
    assert "bad certificate" not in str(caught.value)  # the library's own text is not passed on
    if kind == "unreachable":
        assert ENDPOINT in str(caught.value)


def test_an_invalid_bucket_name_is_a_configuration_error_not_a_connection_error():
    stand_in = fake_client()
    stand_in.head_bucket.side_effect = boto_errors.ParamValidationError(report="Invalid bucket name")

    with pytest.raises(B2ConfigurationError, match="B2_BUCKET_NAME"):
        check_b2_connection(stand_in, "not a valid name!")


def test_a_real_client_rejects_an_invalid_bucket_name_before_any_network_call(client, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("the network was used for a bucket name that is not valid")

    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)

    with pytest.raises(B2ConfigurationError, match="B2_BUCKET_NAME"):
        check_b2_connection(client, "not a valid name!")


# --- the diagnostic command ---------------------------------------------------


@pytest.fixture
def wired(monkeypatch, client):
    """Point the command at fake settings and the real client."""
    monkeypatch.setattr(check_module, "get_settings", lambda: settings_with())
    monkeypatch.setattr(check_module, "get_b2_client", lambda: client)
    return client


def assert_no_secrets(captured) -> None:
    for stream in (captured.out, captured.err):
        assert KEY_ID not in stream
        assert APPLICATION_KEY not in stream


def test_the_command_prints_pass_and_the_non_secret_details(wired, capsys):
    with Stubber(wired) as stubber:
        stubber.add_response("head_bucket", {}, {"Bucket": BUCKET})

        code = check_module.main()

    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert BUCKET in captured.out and ENDPOINT in captured.out and REGION in captured.out
    assert captured.err == ""
    assert_no_secrets(captured)


@pytest.mark.parametrize("status", [403, 404, 400, 500])
def test_the_command_prints_fail_and_exits_1_without_secrets(wired, capsys, status):
    with Stubber(wired) as stubber:
        stubber.add_client_error(
            "head_bucket", service_error_code=str(status), http_status_code=status, expected_params={"Bucket": BUCKET}
        )

        code = check_module.main()

    captured = capsys.readouterr()
    assert code == 1
    assert "FAIL" in captured.err and "PASS" not in captured.out
    assert_no_secrets(captured)


def test_missing_settings_fail_clearly_without_building_a_client_or_calling_anything(monkeypatch, capsys):
    nothing = settings_with(b2_key_id=None, b2_application_key=None, b2_bucket_name=None, b2_endpoint_url=None, b2_region=None)
    monkeypatch.setattr(client_module, "get_settings", lambda: nothing)
    monkeypatch.setattr(check_module, "get_settings", lambda: nothing)
    monkeypatch.setattr(client_module.boto3, "client", lambda *a, **k: pytest.fail("a client was built"))

    code = check_module.main()

    captured = capsys.readouterr()
    assert code == 1
    for name in ("B2_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME", "B2_ENDPOINT_URL", "B2_REGION"):
        assert name in captured.err


def test_a_wrong_region_fails_the_command_before_any_network_call(monkeypatch, capsys):
    wrong = settings_with(b2_region="eu-central-003")  # the endpoint says us-west-004
    monkeypatch.setattr(client_module, "get_settings", lambda: wrong)
    monkeypatch.setattr(check_module, "get_settings", lambda: wrong)
    monkeypatch.setattr(client_module.boto3, "client", lambda *a, **k: pytest.fail("a client was built"))

    code = check_module.main()

    captured = capsys.readouterr()
    assert code == 1
    assert "eu-central-003" in captured.err and "us-west-004" in captured.err
    assert_no_secrets(captured)


# --- scope: no storage API was added ------------------------------------------


def test_the_app_exposes_no_storage_route():
    from app.main import app

    paths = " ".join(app.openapi()["paths"]).lower()

    for word in ("b2", "storage", "bucket", "upload", "download", "presign"):
        assert word not in paths
