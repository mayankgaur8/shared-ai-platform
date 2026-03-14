"""
Admin router — platform management and observability endpoints.

Endpoints:
  GET  /v1/admin/dashboard          — legacy stub
  GET  /v1/admin/providers          — provider health summary
  GET  /v1/admin/usage              — AI usage and spend summary
  GET  /v1/admin/costs              — cost breakdown (provider + app)
  GET  /v1/admin/health             — full system health
  POST /v1/admin/policies/reload    — reload app routing rules (future: DB-backed)
  GET  /v1/admin/routing-table      — inspect the routing table
"""
from __future__ import annotations

import time
import logging
from fastapi import APIRouter

logger = logging.getLogger("saib.admin")
router = APIRouter()


@router.get("/dashboard")
async def dashboard():
    """Legacy admin dashboard stub."""
    return {"detail": "Admin module active. See /v1/admin/health for full status."}


@router.get(
    "/providers",
    summary="Current provider health and circuit breaker states",
)
async def admin_providers():
    """
    Returns live health status for Ollama, Cheap API, and Premium API.
    Triggers a fresh health check ping on each provider.
    """
    from app.services.ai_routing.engine import get_routing_engine
    engine = get_routing_engine()
    states = await engine.check_all_providers()
    healthy_count = sum(1 for v in states.values() if v["healthy"])
    return {
        "providers":       states,
        "healthy_count":   healthy_count,
        "total_providers": len(states),
        "checked_at":      time.time(),
    }


@router.get(
    "/usage",
    summary="AI usage stats for the current month",
)
async def admin_usage():
    """
    Per-app and per-user AI usage and cost breakdown for the current month.
    """
    from app.services.ai_routing.cost import get_usage_accumulator
    acc = get_usage_accumulator()
    return acc.get_summary()


@router.get(
    "/costs",
    summary="Cost breakdown by provider and app",
)
async def admin_costs():
    """
    Detailed cost accounting with provider-level and app-level breakdown.
    """
    from app.services.ai_routing.cost import get_usage_accumulator
    from app.services.ai_routing.health import get_health_service
    acc     = get_usage_accumulator()
    summary = acc.get_summary()
    health  = get_health_service().get_all_states()

    return {
        "cost_summary": summary,
        "provider_health_snapshot": {
            name: {
                "healthy":         info["healthy"],
                "circuit":         info["circuit_breaker"],
                "last_latency_ms": info["last_latency_ms"],
            }
            for name, info in health.items()
        },
    }


@router.get(
    "/health",
    summary="Full platform health — providers + budget + cache",
)
async def admin_health():
    """
    Comprehensive system health check including:
    - All AI provider statuses
    - Monthly budget utilization
    - Redis connectivity
    - Routing table loaded status
    """
    from app.services.ai_routing.engine import get_routing_engine
    from app.services.ai_routing.cost import get_usage_accumulator
    from app.services.ai_routing.routing_table import ROUTING_TABLE
    from app.services.ai_routing.app_rules import APP_RULES
    from app.config.settings import get_settings

    engine   = get_routing_engine()
    states   = await engine.check_all_providers()
    acc      = get_usage_accumulator()
    spend    = acc.get_summary()
    settings = get_settings()

    redis_ok = False
    try:
        from app.config.redis import get_redis
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    all_healthy = all(v["healthy"] for v in states.values())
    return {
        "status":   "healthy" if all_healthy else "degraded",
        "providers": states,
        "budget": {
            "monthly_spend_usd":  spend["total_spend_usd"],
            "limit_usd":          spend["budget_limit_usd"],
            "used_pct":           spend["budget_used_pct"],
            "kill_switch_active": acc.budget_exceeded(),
        },
        "redis":                 "connected" if redis_ok else "unavailable",
        "routing_table_entries": len(ROUTING_TABLE),
        "app_rules_loaded":      len(APP_RULES),
        "environment":           settings.ENVIRONMENT,
        "checked_at":            time.time(),
    }


@router.post(
    "/policies/reload",
    summary="Reload routing policies (no-op until DB-backed policies)",
)
async def reload_policies():
    """
    Reload routing policies from configuration.
    Currently reloads in-memory app rules.
    Future: pull from DB policy table.
    """
    from app.services.ai_routing.routing_table import ROUTING_TABLE
    from app.services.ai_routing.app_rules import APP_RULES
    return {
        "status":        "reloaded",
        "app_rules":     list(APP_RULES.keys()),
        "routing_tasks": list(ROUTING_TABLE.keys()),
        "note":          "Policies are currently file-based. Wire DB for live reloading.",
    }


@router.get(
    "/routing-table",
    summary="Inspect the full AI routing table",
)
async def admin_routing_table():
    """
    Full routing table with per-task provider chains and quality mode overrides.
    """
    from app.services.ai_routing.routing_table import ROUTING_TABLE
    from app.services.ai_routing.app_rules import APP_RULES

    table = {}
    for task, entry in ROUTING_TABLE.items():
        table[task] = {
            "default_chain":      [p.value for p in entry.chain],
            "low_quality_chain":  [p.value for p in (entry.low_chain or entry.chain)],
            "high_quality_chain": [p.value for p in (entry.high_chain or entry.chain)],
            "description":        entry.description,
            "max_tokens_for_ollama": entry.max_tokens_for_ollama,
        }

    app_rules_summary = {
        app: {
            "default_policy":   rule.default_policy.value,
            "free_tier_policy": rule.free_tier_policy.value,
            "paid_tier_policy": rule.paid_tier_policy.value,
        }
        for app, rule in APP_RULES.items()
    }

    return {
        "routing_table":    table,
        "app_rules":        app_rules_summary,
        "total_task_types": len(table),
        "total_app_rules":  len(APP_RULES),
    }
