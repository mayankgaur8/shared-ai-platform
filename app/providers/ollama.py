"""
Ollama provider adapter — free, local, no API cost.
Uses Ollama's /api/chat endpoint (OpenAI-compatible messages format).
"""
from __future__ import annotations

import time
import logging
import httpx

from app.config.settings import get_settings
from .base import BaseProvider, ProviderName, ProviderRequest, ProviderResponse, HealthStatus

logger = logging.getLogger("saib.providers.ollama")
settings = get_settings()


# Ollama is a free local runner — no per-token cost.
COST_PER_TOKEN = 0.0


class OllamaProvider(BaseProvider):
    """
    Connects to a locally running Ollama instance.
    Configuration: OLLAMA_BASE_URL, OLLAMA_MODEL_DEFAULT, AI_TIMEOUT_OLLAMA_MS
    """

    name = ProviderName.OLLAMA

    @property
    def default_model(self) -> str:
        return settings.OLLAMA_MODEL_DEFAULT

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        start = time.monotonic()
        model = request.model or self.default_model
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user",   "content": request.prompt},
            ],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        timeout_s = settings.AI_TIMEOUT_OLLAMA_MS / 1000

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            latency_ms = int((time.monotonic() - start) * 1000)
            tokens_in  = data.get("prompt_eval_count", 0)
            tokens_out = data.get("eval_count", 0)
            text = data.get("message", {}).get("content", "")

            logger.debug("ollama.generate model=%s latency=%dms in=%d out=%d",
                         model, latency_ms, tokens_in, tokens_out)

            return ProviderResponse(
                success=True,
                provider=self.name,
                model=model,
                response_text=text,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                estimated_cost=0.0,
                raw_response=data,
            )

        except httpx.ConnectError as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning("ollama.generate connect_error=%s", exc)
            return ProviderResponse(
                success=False, provider=self.name, model=model,
                response_text="", latency_ms=latency_ms,
                error=f"Cannot reach Ollama at {settings.OLLAMA_BASE_URL}: {exc}",
            )

        except httpx.TimeoutException as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.warning("ollama.generate timeout after %dms", latency_ms)
            return ProviderResponse(
                success=False, provider=self.name, model=model,
                response_text="", latency_ms=latency_ms,
                error=f"Ollama request timed out after {timeout_s}s",
            )

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error("ollama.generate unexpected error=%s", exc, exc_info=True)
            return ProviderResponse(
                success=False, provider=self.name, model=model,
                response_text="", latency_ms=latency_ms,
                error=str(exc),
            )

    async def health_check(self) -> HealthStatus:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                healthy = resp.status_code == 200
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
                provider=self.name,
                healthy=False,
                latency_ms=latency_ms,
                last_checked_at=time.time(),
                detail=str(exc),
            )
