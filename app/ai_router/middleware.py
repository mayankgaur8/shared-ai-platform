"""
AI Router middleware — API key validation and rate limiting for calling apps.

Internal apps authenticate with a shared API key sent in the
X-App-Api-Key header.  Allowlist is configured via AI_INTERNAL_APP_KEYS
(comma-separated list of valid keys in env).

When AI_REQUIRE_APP_KEY=false (default for dev), the check is skipped.
"""
from __future__ import annotations

import logging
from fastapi import Request, HTTPException
from app.config.settings import get_settings

logger   = logging.getLogger("saib.ai_router.middleware")
settings = get_settings()

HEADER_NAME = "X-App-Api-Key"


async def verify_app_api_key(request: Request) -> None:
    """
    FastAPI dependency — call with Depends(verify_app_api_key).
    Validates the internal API key from the request header.
    """
    if not settings.AI_REQUIRE_APP_KEY:
        return   # Dev mode: skip auth

    key = request.headers.get(HEADER_NAME)
    if not key:
        raise HTTPException(
            status_code=401,
            detail=f"Missing {HEADER_NAME} header. Internal API key required.",
        )

    allowed_keys = [
        k.strip()
        for k in settings.AI_INTERNAL_APP_KEYS.split(",")
        if k.strip()
    ]

    if key not in allowed_keys:
        # Log without exposing the actual key
        logger.warning(
            "ai_auth.rejected path=%s key_prefix=%s",
            request.url.path, key[:6] + "***" if len(key) > 6 else "***",
        )
        raise HTTPException(
            status_code=403,
            detail="Invalid API key. Access denied.",
        )

    logger.debug("ai_auth.accepted path=%s", request.url.path)
