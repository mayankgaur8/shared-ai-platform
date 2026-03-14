"""
AI Routing Engine — the central orchestrator.

Receives a normalized AIGenerateRequest and:
  1. Resolves provider chain from routing table + quality mode
  2. Applies app-specific rules and routing policy
  3. Checks provider health / circuit breaker
  4. Skips cloud providers if budget exceeded
  5. Checks Redis cache for repeated prompts
  6. Calls the primary provider; falls back on failure
  7. Updates health state, cost accumulator, and cache
  8. Returns a structured AIGenerateResponse with full observability data
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import List, Optional

from app.providers.base import ProviderName, ProviderRequest, ProviderResponse
from app.providers.ollama import OllamaProvider
from app.providers.cheap_api import CheapApiProvider
from app.providers.premium_api import PremiumApiProvider

from .routing_table import get_routing_entry
from .policies import RoutingPolicy, apply_policy
from .app_rules import resolve_policy
from .health import get_health_service
from .cost import estimate_cost, estimate_prompt_tokens, get_usage_accumulator
from .cache import get_cached_response, set_cached_response

logger = logging.getLogger("saib.ai_routing.engine")

# Provider registry — one instance per process
_PROVIDERS = {
    ProviderName.OLLAMA:      OllamaProvider(),
    ProviderName.CHEAP_API:   CheapApiProvider(),
    ProviderName.PREMIUM_API: PremiumApiProvider(),
}

CLOUD_PROVIDERS = {ProviderName.CHEAP_API, ProviderName.PREMIUM_API}


class AIRoutingEngine:
    """
    Stateless routing orchestrator.
    Uses module-level singletons for health, cost, and cache services.
    """

    async def generate(
        self,
        # ── Request fields ────────────────────────────────────────────────────
        prompt: str,
        task_type: str                  = "general",
        system_prompt: str              = "You are a helpful assistant.",
        app_name: Optional[str]         = None,
        feature: Optional[str]          = None,
        user_id: Optional[str]          = None,
        session_id: Optional[str]       = None,
        user_plan: str                  = "free",
        quality_mode: str               = "balanced",   # low | balanced | high
        model_preference: Optional[str] = None,
        max_tokens: int                 = 1024,
        temperature: float              = 0.7,
        stream: bool                    = False,
        metadata: Optional[dict]        = None,
    ) -> dict:
        """
        Main entry point. Returns a normalized response dict regardless of provider.
        """
        trace_id   = str(uuid.uuid4())
        start_time = time.monotonic()
        health_svc = get_health_service()
        usage_acc  = get_usage_accumulator()

        # ── 1. Resolve provider chain ──────────────────────────────────────────
        entry  = get_routing_entry(task_type)
        policy = resolve_policy(app_name, user_plan, task_type, quality_mode)

        # Quality mode overrides the chain used from the routing entry
        if quality_mode == "low":
            base_chain = entry.low_chain or entry.chain
        elif quality_mode == "high":
            base_chain = entry.high_chain or entry.chain
        else:
            base_chain = entry.chain

        # Apply routing policy to finalize order
        chain: List[ProviderName] = apply_policy(base_chain, policy)

        # ── 2. Budget kill-switch — block cloud if over budget ─────────────────
        if usage_acc.budget_exceeded():
            logger.warning("budget.exceeded trace=%s — restricting to Ollama only", trace_id)
            chain = [p for p in chain if p not in CLOUD_PROVIDERS]
            if not chain:
                return self._error_response(
                    trace_id, "Monthly AI budget exceeded. Please contact support.",
                    app_name, task_type, latency_ms=0,
                )

        # ── 3. Filter unavailable providers (circuit open) ────────────────────
        available_chain = [p for p in chain if health_svc.is_available(p)]
        if not available_chain:
            logger.error("routing.all_providers_unavailable trace=%s chain=%s",
                         trace_id, chain)
            return self._error_response(
                trace_id, "All AI providers are currently unavailable. Please try again later.",
                app_name, task_type, latency_ms=int((time.monotonic() - start_time) * 1000),
            )

        # ── 4. Cache lookup (skip for streaming or disabled) ──────────────────
        if not stream:
            cached = await get_cached_response(
                task_type, prompt, system_prompt, available_chain[0].value
            )
            if cached:
                cached["trace_id"]    = trace_id
                cached["cached"]      = True
                cached["latency_ms"]  = int((time.monotonic() - start_time) * 1000)
                logger.info(
                    "routing.cache_hit trace=%s task=%s provider=%s",
                    trace_id, task_type, cached.get("provider"),
                )
                return cached

        # ── 5. Build provider request ──────────────────────────────────────────
        est_tokens_in = estimate_prompt_tokens(prompt, system_prompt)
        provider_req  = ProviderRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model_preference,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
            task_type=task_type,
            metadata=metadata or {},
        )

        # ── 6. Try providers in order ──────────────────────────────────────────
        last_error:    str = "Unknown error"
        fallback_used: bool = False
        attempted:     List[str] = []

        for idx, provider_name in enumerate(available_chain):
            provider = _PROVIDERS[provider_name]
            if idx > 0:
                fallback_used = True
                logger.info(
                    "routing.fallback trace=%s from=%s to=%s reason=%s",
                    trace_id, attempted[-1] if attempted else "?", provider_name.value, last_error[:80],
                )

            attempted.append(provider_name.value)
            response: ProviderResponse = await provider.generate(provider_req)

            if response.success:
                # ── Record success ─────────────────────────────────────────────
                health_svc.record_success(provider_name, response.latency_ms)
                actual_cost = estimate_cost(provider_name, response.tokens_in, response.tokens_out)
                usage_acc.record(actual_cost, user_id=user_id, app_name=app_name)
                total_latency_ms = int((time.monotonic() - start_time) * 1000)

                logger.info(
                    "routing.success trace=%s task=%s provider=%s model=%s "
                    "latency=%dms cost=$%.6f fallback=%s in=%d out=%d",
                    trace_id, task_type, provider_name.value, response.model,
                    total_latency_ms, actual_cost, fallback_used,
                    response.tokens_in, response.tokens_out,
                )

                result = {
                    "success":       True,
                    "trace_id":      trace_id,
                    "provider":      provider_name.value,
                    "model":         response.model,
                    "response_text": response.response_text,
                    "latency_ms":    total_latency_ms,
                    "tokens_in":     response.tokens_in,
                    "tokens_out":    response.tokens_out,
                    "estimated_cost": actual_cost,
                    "fallback_used": fallback_used,
                    "providers_attempted": attempted,
                    "cached":        False,
                    "task_type":     task_type,
                    "app_name":      app_name,
                    "policy":        policy.value,
                }

                # ── Cache successful response ─────────────────────────────────
                if not stream:
                    await set_cached_response(
                        task_type, prompt, system_prompt,
                        available_chain[0].value, result,
                    )

                return result

            else:
                # ── Record failure and continue to next provider ───────────────
                health_svc.record_failure(provider_name, response.error or "")
                last_error = response.error or "Provider returned failure"
                logger.warning(
                    "routing.provider_failed trace=%s provider=%s error=%s",
                    trace_id, provider_name.value, last_error[:120],
                )

        # ── 7. All providers failed ────────────────────────────────────────────
        total_latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "routing.all_failed trace=%s task=%s attempted=%s last_error=%s",
            trace_id, task_type, attempted, last_error[:200],
        )
        return self._error_response(
            trace_id,
            "We are experiencing technical difficulties. Please try again in a moment.",
            app_name, task_type,
            latency_ms=total_latency_ms,
            providers_attempted=attempted,
            error_detail=last_error[:300],
        )

    # ── Provider health check pass-through ────────────────────────────────────

    async def check_all_providers(self) -> dict:
        """Run health checks on all providers and return status snapshot."""
        health_svc = get_health_service()
        await health_svc.run_health_checks(list(_PROVIDERS.values()))
        return health_svc.get_all_states()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _error_response(
        trace_id: str,
        message: str,
        app_name: Optional[str],
        task_type: str,
        latency_ms: int,
        providers_attempted: Optional[List[str]] = None,
        error_detail: Optional[str] = None,
    ) -> dict:
        return {
            "success":            False,
            "trace_id":           trace_id,
            "provider":           None,
            "model":              None,
            "response_text":      message,
            "latency_ms":         latency_ms,
            "tokens_in":          0,
            "tokens_out":         0,
            "estimated_cost":     0.0,
            "fallback_used":      False,
            "providers_attempted": providers_attempted or [],
            "cached":             False,
            "task_type":          task_type,
            "app_name":           app_name,
            "policy":             None,
            "error":              error_detail,
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
_engine: AIRoutingEngine | None = None


def get_routing_engine() -> AIRoutingEngine:
    global _engine
    if _engine is None:
        _engine = AIRoutingEngine()
    return _engine
