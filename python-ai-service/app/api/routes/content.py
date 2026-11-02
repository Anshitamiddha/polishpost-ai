import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.schemas.generation import GenerationRequest, GenerationResponse
from app.services.content_generation_service import (
    ContentGenerationService,
    get_content_generation_service,
)
from app.services.errors import (
    ContentGenerationError,
    InvalidModelOutputError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])

# Which HTTP status each service error becomes. The error's own message is fixed
# text that is safe to show, so it can go straight into the response.
STATUS_FOR_ERROR = {
    ProviderAuthError: 503,  # our key is missing or rejected: not the caller's fault
    ProviderRateLimitError: 429,
    ProviderUnavailableError: 503,  # timeouts, network trouble, provider outage
    ProviderRequestError: 502,
    InvalidModelOutputError: 502,
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


def get_generation_service() -> ContentGenerationService:
    """Give the route the shared service.

    Building it can fail (for example when GROQ_API_KEY is missing). That happens
    before the route body runs, so the route's own try/except would never see
    it. Mapping the error here keeps every failure in the same JSON shape.
    """
    try:
        return get_content_generation_service()
    except Exception as exc:
        raise to_http_error(exc) from exc


GenerationServiceDep = Annotated[ContentGenerationService, Depends(get_generation_service)]


@router.post(
    "/generate",
    response_model=GenerationResponse,
    summary="Generate captions and hashtags for a video",
    responses={
        429: {"model": ErrorResponse, "description": "The AI provider's limit was reached"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
        502: {"model": ErrorResponse, "description": "The AI provider gave no usable answer"},
        503: {"model": ErrorResponse, "description": "AI service unavailable or not configured"},
    },
)
def generate_content(
    request: GenerationRequest,
    service: GenerationServiceDep,
) -> GenerationResponse:
    # A plain `def` on purpose: the service makes a blocking network call, and
    # FastAPI runs `def` routes in a worker thread so other requests keep moving.
    try:
        return service.generate(request)
    except Exception as exc:
        raise to_http_error(exc) from exc
