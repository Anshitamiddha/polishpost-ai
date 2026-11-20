from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.errors import ErrorResponse, to_http_error
from app.core.security import require_internal_service
from app.schemas.thumbnail import ThumbnailRequest, ThumbnailResponse
from app.services.thumbnail_generation_service import (
    ThumbnailGenerationService,
    get_thumbnail_generation_service,
)

router = APIRouter(prefix="/publish", tags=["publish"])


def get_thumbnail_service() -> ThumbnailGenerationService:
    """Give the route the shared service.

    Building it can fail (for example when MAGIC_HOUR_API_KEY is missing). That
    happens before the route body runs, so the route's own try/except would never
    see it. Mapping the error here keeps every failure in the same JSON shape.
    """
    try:
        return get_thumbnail_generation_service()
    except Exception as exc:
        raise to_http_error(exc) from exc


ThumbnailServiceDep = Annotated[ThumbnailGenerationService, Depends(get_thumbnail_service)]


@router.post(
    "/thumbnails",
    response_model=ThumbnailResponse,
    summary="Generate a thumbnail for a video",
    # Dependencies listed here run first, so a caller without the token never
    # gets as far as building the service or reaching Magic Hour.
    dependencies=[Depends(require_internal_service)],
    responses={
        401: {"model": ErrorResponse, "description": "Missing or wrong internal service token"},
        429: {"model": ErrorResponse, "description": "Magic Hour's limit was reached"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
        502: {"model": ErrorResponse, "description": "Magic Hour gave no usable picture"},
        503: {"model": ErrorResponse, "description": "Magic Hour unavailable, too slow or not configured"},
    },
)
def generate_thumbnail(
    request: ThumbnailRequest,
    service: ThumbnailServiceDep,
) -> ThumbnailResponse:
    # A plain `def` on purpose: the service waits on Magic Hour for many seconds,
    # and FastAPI runs `def` routes in a worker thread so other requests keep moving.
    try:
        return service.generate(request)
    except Exception as exc:
        raise to_http_error(exc) from exc
