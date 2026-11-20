"""Creator-level routes: Gemini captions, hashtags and SEO keywords."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.errors import to_http_error
from app.core.security import require_internal_service
from app.schemas.publishing import PublishingTextRequest, PublishingTextResponse
from app.services.publishing_text_service import PublishingTextService, get_publishing_text_service

router = APIRouter(prefix="/publish", tags=["publish"])


TextService = Annotated[PublishingTextService, Depends(get_publishing_text_service)]


@router.post("/text", response_model=PublishingTextResponse, dependencies=[Depends(require_internal_service)])
def generate_text(request: PublishingTextRequest, service: TextService) -> PublishingTextResponse:
    try:
        return service.generate(request)
    except Exception as exc:
        raise to_http_error(exc) from exc
