"""Tests for the Backblaze B2 client builder and its settings.

Nothing here touches the network: building a boto3 client only reads settings.
"""

import socket

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services import b2_client as client_module
from app.services import b2_connection_check as check_module
from app.services.b2_client import B2ConfigurationError, build_b2_client, get_b2_client

# Fake values made for these tests only. Nothing here is a real secret.
KEY_ID = "test-key-id-0001"
APPLICATION_KEY = "test-APPLICATION-key-SECRET"
BUCKET = "PublishProAI"
ENDPOINT = "https://s3.us-west-004.backblazeb2.com"
REGION = "us-west-004"
B2_ENV_NAMES = ("B2_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME", "B2_ENDPOINT_URL", "B2_REGION")


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


def assert_message_is_safe(exc: Exception) -> None:
    assert KEY_ID not in str(exc)
    assert APPLICATION_KEY not in str(exc)


@pytest.fixture(autouse=True)
def clean_state():
    get_b2_client.cache_clear()
    yield
    get_b2_client.cache_clear()


# --- a good configuration -----------------------------------------------------


def test_a_complete_configuration_builds_a_real_s3_client_for_the_endpoint():
    client = build_b2_client(settings_with())

    assert client.meta.service_model.service_name == "s3"
    assert client.meta.endpoint_url == ENDPOINT
    assert client.meta.region_name == REGION
    config = client.meta.config
    assert config.signature_version == "s3v4"
    assert config.connect_timeout == 5
    assert config.read_timeout == 10
    # botocore stores "one retry" as two attempts in total: not a pile of repeat calls.
    assert config.retries == {"mode": "standard", "total_max_attempts": 2}


def test_the_credentials_and_endpoint_come_from_the_settings(monkeypatch):
    calls = []
    monkeypatch.setattr(client_module.boto3, "client", lambda *args, **kwargs: calls.append((args, kwargs)) or object())

    build_b2_client(settings_with(b2_endpoint_url="https://s3.example.com", b2_region="example-1"))

    ((args, kwargs),) = calls
    assert args == ("s3",)
    assert kwargs["endpoint_url"] == "https://s3.example.com"
    assert kwargs["region_name"] == "example-1"
    assert kwargs["aws_access_key_id"] == KEY_ID
    assert kwargs["aws_secret_access_key"] == APPLICATION_KEY


def test_surrounding_spaces_in_the_settings_are_ignored():
    client = build_b2_client(settings_with(b2_endpoint_url=f"  {ENDPOINT}/  ", b2_region=f" {REGION} "))

    assert client.meta.endpoint_url == ENDPOINT
    assert client.meta.region_name == REGION


def test_building_the_client_makes_no_network_call(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("the network was used while building the client")

    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)

    assert build_b2_client(settings_with()) is not None


# --- missing settings ---------------------------------------------------------

REQUIRED = {
    "B2_KEY_ID": "b2_key_id",
    "B2_APPLICATION_KEY": "b2_application_key",
    "B2_BUCKET_NAME": "b2_bucket_name",
    "B2_ENDPOINT_URL": "b2_endpoint_url",
    "B2_REGION": "b2_region",
}


@pytest.mark.parametrize("env_name, field", REQUIRED.items())
@pytest.mark.parametrize("blank", [None, "", "   "], ids=["unset", "empty", "blank"])
def test_each_missing_setting_is_named_in_the_error(env_name, field, blank):
    value = SecretStr(blank) if blank is not None and field in ("b2_key_id", "b2_application_key") else blank

    with pytest.raises(B2ConfigurationError) as caught:
        build_b2_client(settings_with(**{field: value}))

    assert env_name in str(caught.value)
    assert [name for name in REQUIRED if name in str(caught.value)] == [env_name]  # only the missing one
    assert_message_is_safe(caught.value)


def test_with_nothing_set_every_setting_is_listed_and_no_client_is_built(monkeypatch):
    monkeypatch.setattr(client_module.boto3, "client", lambda *a, **k: pytest.fail("a client was built"))
    nothing = {field: None for field in REQUIRED.values()}

    with pytest.raises(B2ConfigurationError) as caught:
        build_b2_client(settings_with(**nothing))

    for env_name in REQUIRED:
        assert env_name in str(caught.value)


# --- endpoint and region mistakes caught before any network call ---------------


@pytest.mark.parametrize(
    "endpoint",
    ["http://s3.us-west-004.backblazeb2.com", "s3.us-west-004.backblazeb2.com", "ftp://s3.example.com"],
    ids=["plain-http", "no-scheme", "wrong-scheme"],
)
def test_the_endpoint_must_be_an_https_url(endpoint):
    with pytest.raises(B2ConfigurationError, match="https://") as caught:
        build_b2_client(settings_with(b2_endpoint_url=endpoint))

    assert_message_is_safe(caught.value)


def test_the_endpoint_must_not_carry_a_bucket_name_or_path():
    with pytest.raises(B2ConfigurationError, match="without a bucket name or path"):
        build_b2_client(settings_with(b2_endpoint_url=f"{ENDPOINT}/{BUCKET}"))


def test_a_region_that_disagrees_with_the_backblaze_endpoint_is_named_in_the_error():
    with pytest.raises(B2ConfigurationError) as caught:
        build_b2_client(settings_with(b2_region="eu-central-003"))

    assert "eu-central-003" in str(caught.value)
    assert REGION in str(caught.value)
    assert_message_is_safe(caught.value)


def test_a_custom_endpoint_is_not_held_to_the_backblaze_naming():
    client = build_b2_client(settings_with(b2_endpoint_url="https://s3.example.com", b2_region="anything-1"))

    assert client.meta.endpoint_url == "https://s3.example.com"


def test_an_invalid_region_name_is_a_configuration_error():
    with pytest.raises(B2ConfigurationError, match="B2_REGION"):
        build_b2_client(settings_with(b2_endpoint_url="https://s3.example.com", b2_region="us west"))


# --- the shared client --------------------------------------------------------


def test_the_shared_client_is_built_once(monkeypatch):
    monkeypatch.setattr(client_module, "get_settings", lambda: settings_with())

    assert get_b2_client() is get_b2_client()


def test_a_failed_build_is_not_remembered(monkeypatch):
    current = {"settings": settings_with(b2_bucket_name=None)}
    monkeypatch.setattr(client_module, "get_settings", lambda: current["settings"])

    with pytest.raises(B2ConfigurationError):
        get_b2_client()

    current["settings"] = settings_with()  # fixed in .env and restarted, in effect
    assert get_b2_client() is not None


# --- the settings -------------------------------------------------------------


def test_every_b2_setting_defaults_to_unset_so_the_app_still_starts(monkeypatch):
    for name in B2_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    defaults = Settings(_env_file=None)

    for field in REQUIRED.values():
        assert getattr(defaults, field) is None


def test_the_settings_read_the_environment_variables_by_these_names(monkeypatch):
    monkeypatch.setenv("B2_KEY_ID", KEY_ID)
    monkeypatch.setenv("B2_APPLICATION_KEY", APPLICATION_KEY)
    monkeypatch.setenv("B2_BUCKET_NAME", BUCKET)
    monkeypatch.setenv("B2_ENDPOINT_URL", ENDPOINT)
    monkeypatch.setenv("B2_REGION", REGION)

    loaded = Settings(_env_file=None)

    assert loaded.b2_key_id.get_secret_value() == KEY_ID
    assert loaded.b2_application_key.get_secret_value() == APPLICATION_KEY
    assert (loaded.b2_bucket_name, loaded.b2_endpoint_url, loaded.b2_region) == (BUCKET, ENDPOINT, REGION)


def test_both_credentials_are_hidden_when_settings_are_printed():
    shown = repr(settings_with()) + str(settings_with())

    assert KEY_ID not in shown
    assert APPLICATION_KEY not in shown


# --- scope: this phase only builds the client ---------------------------------

FORBIDDEN_WORDS = ("upload", "download", "delete", "presign", "put_object", "get_object")


@pytest.mark.parametrize("module", [client_module, check_module], ids=["b2_client", "b2_connection_check"])
def test_the_b2_modules_have_no_upload_download_delete_or_presign_functions(module):
    public_names = [name.lower() for name in dir(module) if not name.startswith("_")]

    assert [name for name in public_names for word in FORBIDDEN_WORDS if word in name] == []
