"""
AI Router — unified gateway endpoints.

Endpoints:
  POST /v1/ai/generate          — main generation endpoint (all apps use this)
  GET  /v1/ai/health/providers  — provider health + circuit breaker status
  GET  /v1/ai/routing-table     — show current routing rules (debug/admin)
  GET  /v1/ai/usage/summary     — monthly spend and usage summary

All apps should call only /v1/ai/generate.
The router handles provider selection, fallback, caching, and cost tracking.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Request

from .schemas import AIGenerateRequest, AIGenerateResponse
from .middleware import verify_app_api_key
from app.services.ai_routing.engine import get_routing_engine
from app.services.ai_routing.routing_table import ROUTING_TABLE
from app.services.ai_routing.health import get_health_service
from app.services.ai_routing.cost import get_usage_accumulator

logger = logging.getLogger("saib.ai_router")
router = APIRouter()


# ── POST /v1/ai/generate ──────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=AIGenerateResponse,
    summary="Unified AI generation endpoint",
    description=(
        "Send any AI task to this single endpoint. "
        "The router automatically selects the best provider based on task type, "
        "quality mode, user plan, and provider health. "
        "Supports grammar correction, conversation, assignments, MCQs, "
        "interview mock, resume analysis, and more."
    ),
)
async def generate(
    request: AIGenerateRequest,
    _: None = Depends(verify_app_api_key),
):
    """
    Main AI gateway. Accepts a unified request and returns a normalized response.
    Provider selection, fallback, caching, and cost tracking happen transparently.
    """
    engine = get_routing_engine()

    result = await engine.generate(
        prompt           = request.prompt,
        task_type        = request.task_type,
        system_prompt    = request.system_prompt or "You are a helpful assistant.",
        app_name         = request.app_name,
        feature          = request.feature,
        user_id          = request.user_id,
        session_id       = request.session_id,
        user_plan        = request.user_plan,
        quality_mode     = request.quality_mode.value,
        model_preference = request.model_preference,
        max_tokens       = request.max_tokens,
        temperature      = request.temperature,
        stream           = request.stream,
        metadata         = request.metadata,
    )

    return AIGenerateResponse(**result)


# ── GET /v1/ai/health/providers ───────────────────────────────────────────────

@router.get(
    "/health/providers",
    summary="Provider health and circuit breaker status",
)
async def provider_health():
    """
    Returns real-time health, latency, failure counts, and circuit breaker
    state for all configured AI providers.
    Triggers a live health check on each provider.
    """
    engine = get_routing_engine()
    states = await engine.check_all_providers()
    return {
        "providers": states,
        "summary": {
            name: ("healthy" if info["healthy"] else "unhealthy")
            for name, info in states.items()
        },
    }


# ── GET /v1/ai/routing-table ──────────────────────────────────────────────────

@router.get(
    "/routing-table",
    summary="Show current routing rules for all task types",
)
async def routing_table():
    """
    Returns the full routing table — which provider chain is used for each
    task type and what happens under low/high quality modes.
    Useful for debugging routing decisions.
    """
    table = {}
    for task, entry in ROUTING_TABLE.items():
        table[task] = {
            "default_chain":     [p.value for p in entry.chain],
            "low_quality_chain": [p.value for p in (entry.low_chain or entry.chain)],
            "high_quality_chain":[p.value for p in (entry.high_chain or entry.chain)],
            "description":       entry.description,
            "max_tokens_for_ollama": entry.max_tokens_for_ollama,
        }
    return {"routing_table": table, "total_task_types": len(table)}


# ── GET /v1/ai/usage/summary ──────────────────────────────────────────────────

@router.get(
    "/usage/summary",
    summary="Monthly AI spend and usage summary",
)
async def usage_summary():
    """
    Returns current month's AI usage stats:
    total spend, per-app and per-user breakdown, budget utilization.
    """
    acc = get_usage_accumulator()
    return acc.get_summary()
