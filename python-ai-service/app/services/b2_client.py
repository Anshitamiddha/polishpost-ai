"""Builds the Backblaze B2 client. B2 speaks the S3 protocol, so boto3 does the work.

This module only makes the client. It uploads, downloads, lists and deletes
nothing, and it knows nothing about thumbnails or Magic Hour.
"""

import re
import threading
from functools import lru_cache
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import InvalidRegionError

from app.core.config import Settings, get_settings

CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 10

# Backblaze's S3 endpoints look like https://s3.us-west-004.backblazeb2.com,
# with the bucket's region in the middle.
_BACKBLAZE_HOST = re.compile(r"^s3\.(?P<region>[a-z0-9-]+)\.backblazeb2\.com$")


class B2ConfigurationError(Exception):
    """A B2 setting is missing or wrong.

    The message names settings, never their values, so it is safe to print.
    """


def _text(value: str | None) -> str:
    return (value or "").strip()


def _secret(value) -> str:
    return value.get_secret_value().strip() if value else ""


def build_b2_client(settings: Settings):
    """Make the S3 client for Backblaze B2, or raise B2ConfigurationError.

    Making the client does not touch the network, so a wrong key or bucket only
    shows up when something is asked of B2 (see b2_connection_check.py).
    """
    key_id = _secret(settings.b2_key_id)
    application_key = _secret(settings.b2_application_key)
    bucket_name = _text(settings.b2_bucket_name)
    endpoint_url = _text(settings.b2_endpoint_url).rstrip("/")
    region = _text(settings.b2_region)

    required = {
        "B2_KEY_ID": key_id,
        "B2_APPLICATION_KEY": application_key,
        "B2_BUCKET_NAME": bucket_name,
        "B2_ENDPOINT_URL": endpoint_url,
        "B2_REGION": region,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise B2ConfigurationError(f"Backblaze B2 is not configured. Missing: {', '.join(missing)}.")

    _check_endpoint_and_region(endpoint_url, region)

    try:
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=key_id,
            aws_secret_access_key=application_key,
            config=Config(
                signature_version="s3v4",
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                read_timeout=READ_TIMEOUT_SECONDS,
                # One retry for a passing network hiccup, not a pile of repeat calls.
                retries={"max_attempts": 1, "mode": "standard"},
                # boto3's newer default adds a trailing checksum (aws-chunked) to uploads,
                # which Backblaze's S3 API has rejected. Only add checksums when S3 requires them.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
    except InvalidRegionError as exc:
        raise B2ConfigurationError("B2_REGION is not a valid region name, such as us-west-004.") from exc
    except ValueError as exc:
        raise B2ConfigurationError("B2_ENDPOINT_URL is not a valid URL.") from exc


def _check_endpoint_and_region(endpoint_url: str, region: str) -> None:
    """Catch the common typos before any network call is made."""
    parsed = urlparse(endpoint_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise B2ConfigurationError(
            "B2_ENDPOINT_URL must start with https:// and be the S3 endpoint Backblaze shows for the bucket."
        )
    if parsed.path not in ("", "/"):
        raise B2ConfigurationError(
            "B2_ENDPOINT_URL should be only the host, such as https://s3.us-west-004.backblazeb2.com, "
            "without a bucket name or path."
        )

    match = _BACKBLAZE_HOST.match(parsed.hostname)
    if match and match.group("region") != region:
        raise B2ConfigurationError(
            f"B2_REGION is '{region}' but B2_ENDPOINT_URL is for '{match.group('region')}'. They must match."
        )


@lru_cache
def _build_shared_client():
    return build_b2_client(get_settings())


_build_lock = threading.Lock()


def get_b2_client():
    """Return the shared client, building it on the first call.

    boto3 clients can be shared between threads, so one is enough for the whole
    service. The lock only stops two threads from building it at the same moment.
    """
    with _build_lock:
        return _build_shared_client()


# Tests reset the shared client through this.
get_b2_client.cache_clear = _build_shared_client.cache_clear
