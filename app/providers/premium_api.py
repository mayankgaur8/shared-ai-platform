"""
Premium API provider — highest quality cloud model.
Uses OpenAI's /chat/completions endpoint. Works with:
  - OpenAI (GPT-4o, GPT-4 Turbo)
  - Azure OpenAI
  - Any OpenAI-compatible premium service

Configuration: PREMIUM_API_BASE_URL, PREMIUM_API_KEY, PREMIUM_API_MODEL_DEFAULT
Cost tracking: PREMIUM_API_COST_PER_1K_INPUT_TOKENS, PREMIUM_API_COST_PER_1K_OUTPUT_TOKENS
"""
from __future__ import annotations

import time
import logging
import httpx

from app.config.settings import get_settings
from .base import BaseProvider, ProviderName, ProviderRequest, ProviderResponse, HealthStatus

logger = logging.getLogger("saib.providers.premium_api")
settings = get_settings()


class PremiumApiProvider(BaseProvider):
    """
    High-quality cloud provider (e.g. OpenAI GPT-4o, Anthropic Claude).
    Used for premium users, complex tasks, or as a final fallback.
    """

    name = ProviderName.PREMIUM_API

    @property
    def default_model(self) -> str:
        return settings.PREMIUM_API_MODEL_DEFAULT

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.PREMIUM_API_KEY}",
            "Content-Type": "application/json",
        }

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        cost_in  = (tokens_in  / 1000) * settings.PREMIUM_API_COST_PER_1K_INPUT
        cost_out = (tokens_out / 1000) * settings.PREMIUM_API_COST_PER_1K_OUTPUT
        return round(cost_in + cost_out, 8)

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        if not settings.PREMIUM_API_KEY:
            return ProviderResponse(
                success=False, provider=self.name,
                model=self.default_model, response_text="",
                error="PREMIUM_API_KEY not configured",
            )

        start = time.monotonic()
        model = request.model or self.default_model
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user",   "content": request.prompt},
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        timeout_s = settings.AI_TIMEOUT_PREMIUM_MS / 1000

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    f"{settings.PREMIUM_API_BASE_URL}/chat/completions",
                    headers=self._build_headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            latency_ms = int((time.monotonic() - start) * 1000)
            usage      = data.get("usage", {})
            tokens_in  = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            text = data["choices"][0]["message"]["content"]

            cost = self._estimate_cost(tokens_in, tokens_out)
            logger.debug("premium_api.generate model=%s latency=%dms cost=$%.6f",
                         model, latency_ms, cost)

            return ProviderResponse(
                success=True,
                provider=self.name,
                model=data.get("model", model),
                response_text=text,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                estimated_cost=cost,
                raw_response=data,
            )

        except httpx.ConnectError as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning("premium_api.generate connect_error=%s", exc)
            return ProviderResponse(
                success=False, provider=self.name, model=model,
                response_text="", latency_ms=latency_ms,
                error=f"Cannot reach Premium API at {settings.PREMIUM_API_BASE_URL}: {exc}",
            )

        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning("premium_api.generate timeout after %dms", latency_ms)
            return ProviderResponse(
                success=False, provider=self.name, model=model,
                response_text="", latency_ms=latency_ms,
                error=f"Premium API timed out after {timeout_s}s",
            )

        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            detail = exc.response.text[:300] if exc.response else str(exc)
            logger.warning("premium_api.generate http_error=%d body=%s", exc.response.status_code, detail)
            return ProviderResponse(
                success=False, provider=self.name, model=model,
                response_text="", latency_ms=latency_ms,
                error=f"Premium API HTTP {exc.response.status_code}: {detail}",
            )

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error("premium_api.generate error=%s", exc, exc_info=True)
            return ProviderResponse(
                success=False, provider=self.name, model=model,
                response_text="", latency_ms=latency_ms,
                error=str(exc),
            )

    async def health_check(self) -> HealthStatus:
        if not settings.PREMIUM_API_KEY:
            return HealthStatus(
                provider=self.name, healthy=False,
                last_checked_at=time.time(),
                detail="PREMIUM_API_KEY not configured",
            )

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.PREMIUM_API_BASE_URL}/models",
                    headers=self._build_headers(),
                )
                healthy = resp.status_code in (200, 404)
                latency_ms = int((time.monotonic() - start) * 1000)
                return HealthStatus(
                    provider=self.name,
                    healthy=healthy,
                    latency_ms=latency_ms,
                    last_checked_at=time.time(),
                    detail="ok" if healthy else f"HTTP {resp.status_code}",
                )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return HealthStatus(
                provider=self.name, healthy=False,
                latency_ms=latency_ms, last_checked_at=time.time(),
                detail=str(exc),
            )
