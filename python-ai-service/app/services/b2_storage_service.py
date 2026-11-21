"""Puts generated pictures into the private Backblaze B2 bucket.

It reuses the shared client from b2_client.py and the connection check from
b2_connection_check.py. It only uploads: no downloads, no public links and no
presigned links, so the bucket stays private. It knows nothing about Magic Hour.
"""

import logging
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from botocore import exceptions as boto_errors

from app.core.config import get_settings
from app.services.b2_client import B2ConfigurationError, get_b2_client
from app.services.b2_connection_check import B2ConnectionError, check_b2_connection
from app.services.errors import (
    StorageAuthError,
    StorageError,
    StorageFileError,
    StorageNotConfiguredError,
    StorageRequestError,
    StorageTimeoutError,
    StorageUnavailableError,
)

logger = logging.getLogger(__name__)

# The file endings we store, and the content type each one is uploaded with.
CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}

# The same limit the generation service applies to a downloaded picture.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Our own asset IDs are uuid4().hex. Checking the shape keeps odd text out of the key.
_ASSET_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class StoredObject:
    """What was stored. There is deliberately no link here: the bucket is private."""

    object_key: str
    size_bytes: int
    content_type: str


def build_object_key(workspace_id: int, asset_id: str, extension: str) -> str:
    """The key a picture is stored under: workspaces/{workspace_id}/generated/{asset_id}.{extension}.

    Raises ValueError for a part that is not what it should be. That is a bug in
    the caller, not something a user can cause, because each part is checked earlier.
    """
    # bool is a kind of int in Python, so it is refused by name.
    if isinstance(workspace_id, bool) or not isinstance(workspace_id, int) or workspace_id < 1:
        raise ValueError("workspace_id must be a positive whole number")
    if not isinstance(asset_id, str) or not _ASSET_ID.match(asset_id):
        raise ValueError("asset_id must be 32 lowercase hex characters")
    if extension not in CONTENT_TYPES:
        raise ValueError("extension must be one of: " + ", ".join(CONTENT_TYPES))
    return f"workspaces/{workspace_id}/generated/{asset_id}.{extension}"


class B2StorageService:
    def __init__(self, client, bucket_name: str):
        # The client is passed in so tests can use a fake, and the app shares one.
        self._client = client
        self._bucket_name = bucket_name

    def check_ready(self) -> None:
        """Make sure B2 answers and lets us use the bucket, or raise a StorageError.

        The thumbnail service calls this before it pays for a picture.
        """
        try:
            check_b2_connection(self._client, self._bucket_name)
        except B2ConnectionError as exc:
            # The text names the bucket and endpoint but never a credential. Only the log gets it.
            logger.warning("Backblaze is not ready (%s): %s", exc.kind, exc)
            raise _ERROR_FOR_CHECK.get(exc.kind, StorageUnavailableError)() from exc
        except B2ConfigurationError as exc:
            logger.warning("Backblaze is not ready: %s", exc)
            raise StorageNotConfiguredError() from exc

    def upload_image(self, path: Path, workspace_id: int, asset_id: str, extension: str) -> StoredObject:
        """Upload a checked picture under its workspace key."""
        key = build_object_key(workspace_id, asset_id, extension)
        return self.upload_file(path, key, CONTENT_TYPES[extension])

    def upload_file(self, path: Path, object_key: str, content_type: str) -> StoredObject:
        """Upload one local file as `object_key`, or raise a StorageError."""
        size = self._check_local_file(path)

        try:
            body = path.open("rb")
        except OSError as exc:
            logger.warning("Cannot open %s for upload: %s", path.name, type(exc).__name__)
            raise StorageFileError() from exc

        with body:
            try:
                self._client.put_object(
                    Bucket=self._bucket_name, Key=object_key, Body=body, ContentType=content_type
                )
            except boto_errors.ClientError as exc:
                raise _error_for_response(exc) from exc
            # Timeouts come before the general connection error, which one of them is a kind of.
            except (boto_errors.ConnectTimeoutError, boto_errors.ReadTimeoutError) as exc:
                logger.warning("The upload to Backblaze timed out")
                raise StorageTimeoutError() from exc
            except (boto_errors.ConnectionError, boto_errors.ConnectionClosedError) as exc:
                logger.warning("Could not reach Backblaze for the upload: %s", type(exc).__name__)
                raise StorageUnavailableError() from exc
            except boto_errors.BotoCoreError as exc:
                # The exception's own text is left out, in case it ever echoes request details.
                logger.warning("Unexpected problem during the upload: %s", type(exc).__name__)
                raise StorageRequestError() from exc
            except OSError as exc:
                # A raw socket error that botocore did not wrap, or a read error on the file.
                logger.warning("The upload failed with an OS error: %s", type(exc).__name__)
                raise StorageUnavailableError() from exc

        logger.info("Uploaded %s (%d bytes) to the bucket", object_key, size)
        return StoredObject(object_key=object_key, size_bytes=size, content_type=content_type)

    def _check_local_file(self, path: Path) -> int:
        """Refuse a file that is missing, empty or too large, before any network call."""
        try:
            if not path.is_file():
                logger.warning("The file to upload is missing: %s", path.name)
                raise StorageFileError()
            size = path.stat().st_size
        except OSError as exc:
            logger.warning("Cannot read the file to upload: %s", type(exc).__name__)
            raise StorageFileError() from exc
        if size == 0 or size > MAX_UPLOAD_BYTES:
            logger.warning("The file to upload has an unusable size: %d bytes", size)
            raise StorageFileError()
        return size


# What the connection check's `kind` means for the caller.
_ERROR_FOR_CHECK = {
    "access_denied": StorageAuthError,
    "bucket_not_found": StorageNotConfiguredError,
    "endpoint_or_region": StorageNotConfiguredError,
    "timeout": StorageTimeoutError,
    "unreachable": StorageUnavailableError,
    "unexpected": StorageUnavailableError,
}

# Codes B2 uses for "try again", even when the HTTP status is a 400.
_RETRY_CODES = {"RequestTimeout", "SlowDown", "ServiceUnavailable", "InternalError"}


def _error_for_response(exc: boto_errors.ClientError) -> StorageError:
    """Turn B2's answer to an upload into one of our errors."""
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    code = exc.response.get("Error", {}).get("Code")
    # Only the status and code are logged, never the message or the headers.
    logger.warning("Backblaze refused the upload: HTTP %s, code %s", status, code)

    if code in _RETRY_CODES or status in (408, 429) or (status is not None and status >= 500):
        return StorageUnavailableError()
    if status in (401, 403):
        return StorageAuthError()
    if status in (301, 307, 404):  # wrong endpoint, or no such bucket
        return StorageNotConfiguredError()
    return StorageRequestError()


@lru_cache
def _build_service() -> B2StorageService:
    try:
        client = get_b2_client()
    except B2ConfigurationError as exc:
        # The message names the missing settings, never their values.
        logger.error("%s", exc)
        raise StorageNotConfiguredError() from exc
    return B2StorageService(client, (get_settings().b2_bucket_name or "").strip())


_build_lock = threading.Lock()


def get_b2_storage_service() -> B2StorageService:
    """Return the shared storage service, building it on the first call."""
    with _build_lock:
        return _build_service()


# Tests reset the shared service through this.
get_b2_storage_service.cache_clear = _build_service.cache_clear
