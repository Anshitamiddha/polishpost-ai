"""How a failure inside a service becomes an HTTP answer.

Shared by the content and thumbnail routes, so both give the same status codes
and the same JSON shape.
"""

import logging

from fastapi import HTTPException
from pydantic import BaseModel

from app.services.errors import (
    ContentGenerationError,
    ImageNotCreatedError,
    ImageNotSavedError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderUnavailableError,
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
}


class ErrorResponse(BaseModel):
    detail: str


def to_http_error(exc: Exception) -> HTTPException:
    """Turn any failure into a JSON error that leaks nothing."""
    if isinstance(exc, ContentGenerationError):
        # isinstance, not an exact-class lookup, so a subclass keeps its parent's
        # status. An error we forgot to list is still a failure, never a 200.
        status = next(
            (code for error_class, code in STATUS_FOR_ERROR.items() if isinstance(exc, error_class)),
            500,
        )
        return HTTPException(status, detail=str(exc))

    # Something we did not plan for. The traceback goes to our log only; the
    # caller gets a bland message, since the real one might hold sensitive text.
    logger.error("Unexpected error while generating content", exc_info=exc)
    return HTTPException(500, detail="Internal server error.")
