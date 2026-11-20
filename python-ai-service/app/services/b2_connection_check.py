"""Checks that Backblaze B2 can be reached with the configured credentials.

It uses HeadBucket, which only asks "does this bucket exist, and may these
credentials use it?". Nothing is uploaded, downloaded, listed or changed.

Run it from the python-ai-service folder:

    python -m app.services.b2_connection_check
"""

import logging
import sys

from botocore import exceptions as boto_errors

from app.core.config import get_settings
from app.services.b2_client import B2ConfigurationError, get_b2_client

logger = logging.getLogger(__name__)


class B2ConnectionError(Exception):
    """B2 could not be reached, or it refused us.

    `kind` says which problem it is. The message is fixed text that never holds
    a credential, so it is safe to print or log.
    """

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def check_b2_connection(client, bucket_name: str) -> None:
    """Ask B2 whether the bucket is reachable. Return quietly, or raise.

    Raises B2ConnectionError for a connection or access problem, and
    B2ConfigurationError when the bucket name itself is not a valid name.
    """
    try:
        client.head_bucket(Bucket=bucket_name)
    except boto_errors.ClientError as exc:
        raise _error_for_response(exc, bucket_name) from exc
    # Timeouts come before the general connection error, which one of them is a kind of.
    except (boto_errors.ConnectTimeoutError, boto_errors.ReadTimeoutError) as exc:
        raise B2ConnectionError(
            "timeout",
            "Timed out talking to Backblaze. Check your internet connection and B2_ENDPOINT_URL.",
        ) from exc
    except (boto_errors.ConnectionError, boto_errors.ConnectionClosedError) as exc:
        raise B2ConnectionError(
            "unreachable",
            f"Could not connect to Backblaze at {client.meta.endpoint_url}. "
            "Check B2_ENDPOINT_URL and your internet connection.",
        ) from exc
    except boto_errors.ParamValidationError as exc:
        raise B2ConfigurationError(
            f"B2_BUCKET_NAME '{bucket_name}' is not a valid bucket name."
        ) from exc
    except boto_errors.BotoCoreError as exc:
        # The exception's own text is left out, in case it ever echoes request details.
        raise B2ConnectionError(
            "unexpected", f"Unexpected problem while checking Backblaze ({type(exc).__name__})."
        ) from exc


def _error_for_response(exc: boto_errors.ClientError, bucket_name: str) -> B2ConnectionError:
    """Turn B2's answer into a plain-words error.

    HeadBucket answers have no body, so the HTTP status is all there is to go on.
    """
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    code = exc.response.get("Error", {}).get("Code")
    logger.info("HeadBucket was refused: HTTP %s, code %s", status, code)

    if status in (401, 403):
        return B2ConnectionError(
            "access_denied",
            f"Backblaze refused the request (HTTP {status}). The key ID or application key is wrong, "
            f"or the key has no access to bucket '{bucket_name}'. HeadBucket cannot tell these apart, "
            "so check both.",
        )
    if status == 404:
        return B2ConnectionError(
            "bucket_not_found",
            f"Bucket '{bucket_name}' was not found at this endpoint. Check B2_BUCKET_NAME, and that "
            "B2_ENDPOINT_URL and B2_REGION are the ones for this bucket.",
        )
    if status in (301, 307, 400):
        return B2ConnectionError(
            "endpoint_or_region",
            f"Backblaze rejected the endpoint or region (HTTP {status}). Check that B2_ENDPOINT_URL "
            f"and B2_REGION match the region of bucket '{bucket_name}'.",
        )
    return B2ConnectionError(
        "unexpected", f"Backblaze answered with an unexpected error (HTTP {status}, code {code})."
    )


def main() -> int:
    """The diagnostic command. Prints PASS or FAIL, and returns the exit code."""
    print("Checking Backblaze B2 with HeadBucket. Nothing is uploaded, downloaded or changed.")
    try:
        client = get_b2_client()
        bucket_name = get_settings().b2_bucket_name.strip()
        print(f"  Bucket:   {bucket_name}")
        print(f"  Endpoint: {client.meta.endpoint_url}")
        print(f"  Region:   {client.meta.region_name}")
        check_b2_connection(client, bucket_name)
    except (B2ConfigurationError, B2ConnectionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: the bucket is reachable and these credentials can use it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
