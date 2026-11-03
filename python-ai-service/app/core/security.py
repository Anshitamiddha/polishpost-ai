"""Checks that a request really comes from our Spring Boot backend."""

import logging
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def require_internal_service(
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    """Let the request through only if it carries the shared secret."""
    secret = settings.ai_service_shared_secret

    # A blank secret counts as "not set". Otherwise an empty header would match it.
    if secret is None or not secret.get_secret_value().strip():
        # Our setup is broken, not the caller's request, so 503 and not 401.
        logger.error("AI_SERVICE_SHARED_SECRET is not set, refusing the request")
        raise HTTPException(503, detail="Service authentication is not configured.")

    # One message for "missing" and "wrong", so a caller learns nothing extra.
    # Both sides become bytes first: compare_digest rejects non-ASCII text.
    expected = secret.get_secret_value().encode("utf-8")
    supplied = (token or "").encode("utf-8")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(401, detail="Missing or invalid service token.")
