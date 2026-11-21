"""How a failure inside a service becomes an HTTP answer.

Shared by the routes, so they all give the same status codes and the same JSON
shape.
"""

import logging

from fastapi import HTTPException
from pydantic import BaseModel

from app.services.errors import (
    ContentGenerationError,
    ImageGeneratedButNotStoredError,
    ImageNotCreatedError,
    ImageNotSavedError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderUnavailableError,
    StorageAuthError,
    StorageError,
    StorageFileError,
    StorageNotConfiguredError,
    StorageRequestError,
    StorageUnavailableError,
)

logger = logging.getLogger(__name__)

# Which HTTP status each service error becomes. The error's own message is fixed
# text that is safe to show, so it can go straight into the response.
STATUS_FOR_ERROR = {
    ProviderAuthError: 503,  # our key is missing or rejected: not the caller's fault
    ProviderRateLimitError: 429,
    ProviderUnavailableError: 503,  # timeouts, network trouble, provider outage
    ProviderRequestError: 502,
    InvalidModelOutputError: 502,
    ImageNotCreatedError: 502,  # the model said no; its message tells the user what to try
    ImageNotSavedError: 500,  # our own disk; the caller cannot fix it
    # File storage. Setup and outage problems are 503 (retry later); a refused upload is 502.
    StorageNotConfiguredError: 503,
    StorageAuthError: 503,
    StorageUnavailableError: 503,
    StorageRequestError: 502,
    StorageFileError: 500,
    ImageGeneratedButNotStoredError: 503,  # only if the real cause is unknown, see _status_for
}


class ErrorResponse(BaseModel):
    detail: str


def _status_for(exc: Exception) -> int:
    # "Generated but not stored" has the status of the storage problem behind it.
    if isinstance(exc, ImageGeneratedButNotStoredError) and isinstance(exc.__cause__, StorageError):
        exc = exc.__cause__
    # isinstance, not an exact-class lookup, so a subclass keeps its parent's
    # status. An error we forgot to list is still a failure, never a 200.
    return next((code for error_class, code in STATUS_FOR_ERROR.items() if isinstance(exc, error_class)), 500)


def to_http_error(exc: Exception) -> HTTPException:
    """Turn any failure into a JSON error that leaks nothing."""
    if isinstance(exc, (ContentGenerationError, StorageError)):
        return HTTPException(_status_for(exc), detail=str(exc))

    # Something we did not plan for. The traceback goes to our log only; the
    # caller gets a bland message, since the real one might hold sensitive text.
    logger.error("Unexpected error while generating content", exc_info=exc)
    return HTTPException(500, detail="Internal server error.")
