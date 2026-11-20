from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.errors import ErrorResponse, to_http_error
from app.core.security import require_internal_service
from app.schemas.generation import GenerationRequest, GenerationResponse
from app.services.content_generation_service import (
    ContentGenerationService,
    get_content_generation_service,
)

router = APIRouter(prefix="/content", tags=["content"])


def get_generation_service() -> ContentGenerationService:
    """Give the route the shared service.

    Building it can fail (for example when GEMINI_API_KEY is missing). That happens
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
    # Dependencies listed here run first, so a caller without the token never
    # gets as far as building the service or reaching the AI provider.
    dependencies=[Depends(require_internal_service)],
    responses={
        401: {"model": ErrorResponse, "description": "Missing or wrong internal service token"},
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
