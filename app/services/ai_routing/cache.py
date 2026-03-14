"""
Redis response cache for repeated prompts.

Cache key is a hash of: task_type + normalized_prompt + provider_chain[0] + model.
TTL is configurable via REDIS_TTL_AI_RESPONSE (default 300s).

Cache is skipped when:
  - stream=True
  - cache is disabled (AI_CACHE_ENABLED=false)
  - Redis is unavailable (fails silently)
"""
from __future__ import annotations

import json
import hashlib
import logging
from typing import Optional

from app.config.settings import get_settings

logger = logging.getLogger("saib.ai_routing.cache")
settings = get_settings()

_CACHE_PREFIX = "ai:resp:"


def _make_key(task_type: str, prompt: str, system_prompt: str, primary_provider: str) -> str:
    """Build a deterministic cache key from the request fingerprint."""
    fingerprint = f"{task_type}|{primary_provider}|{system_prompt[:100]}|{prompt}"
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    return f"{_CACHE_PREFIX}{task_type}:{digest}"


async def get_cached_response(
    task_type: str,
    prompt: str,
    system_prompt: str,
    primary_provider: str,
) -> Optional[dict]:
    """Return cached response dict or None if not found / cache disabled."""
    if not settings.AI_CACHE_ENABLED:
        return None

    try:
        from app.config.redis import get_redis
        redis = await get_redis()
        key   = _make_key(task_type, prompt, system_prompt, primary_provider)
        raw   = await redis.get(key)
        if raw:
            logger.debug("cache.hit key=%s", key)
            return json.loads(raw)
    except Exception as exc:
        logger.warning("cache.get_error key_prefix=%s error=%s", _CACHE_PREFIX, exc)
    return None


async def set_cached_response(
    task_type: str,
    prompt: str,
    system_prompt: str,
    primary_provider: str,
    response: dict,
) -> None:
    """Store response in Redis cache. Fails silently if Redis is down."""
    if not settings.AI_CACHE_ENABLED:
        return

    try:
        from app.config.redis import get_redis
        redis = await get_redis()
        key   = _make_key(task_type, prompt, system_prompt, primary_provider)
        ttl   = settings.REDIS_TTL_AI_RESPONSE
        await redis.setex(key, ttl, json.dumps(response))
        logger.debug("cache.set key=%s ttl=%ds", key, ttl)
    except Exception as exc:
        logger.warning("cache.set_error error=%s", exc)
