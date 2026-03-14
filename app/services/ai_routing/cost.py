"""
Cost estimation and budget control.

Per-provider cost rates are loaded from settings.
Budget enforcement: if monthly spend exceeds AI_BUDGET_MONTHLY_LIMIT,
a kill-switch flag is set and no cloud calls are allowed.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

from app.config.settings import get_settings
from app.providers.base import ProviderName

logger = logging.getLogger("saib.ai_routing.cost")
settings = get_settings()

# Token cost table: cost per 1 token (in USD)
_COST_TABLE: dict[ProviderName, dict] = {
    ProviderName.OLLAMA: {
        "input":  0.0,
        "output": 0.0,
    },
    ProviderName.CHEAP_API: {
        "input":  settings.CHEAP_API_COST_PER_1K_INPUT  / 1000,
        "output": settings.CHEAP_API_COST_PER_1K_OUTPUT / 1000,
    },
    ProviderName.PREMIUM_API: {
        "input":  settings.PREMIUM_API_COST_PER_1K_INPUT  / 1000,
        "output": settings.PREMIUM_API_COST_PER_1K_OUTPUT / 1000,
    },
}


def estimate_cost(provider: ProviderName, tokens_in: int, tokens_out: int) -> float:
    """Return estimated USD cost for the given token usage."""
    rates = _COST_TABLE.get(provider, {"input": 0.0, "output": 0.0})
    return round(rates["input"] * tokens_in + rates["output"] * tokens_out, 8)


def estimate_prompt_tokens(prompt: str, system_prompt: str = "") -> int:
    """
    Rough token count estimate before sending to provider.
    Rule of thumb: 1 token ≈ 4 characters in English.
    """
    total_chars = len(prompt) + len(system_prompt)
    return max(1, total_chars // 4)


class UsageAccumulator:
    """
    In-memory accumulator for tracking spend in the current month.
    In production you'd back this with Redis or Postgres.
    Provides a simple kill-switch when the monthly budget is exceeded.
    """

    def __init__(self) -> None:
        self._monthly_spend: float = 0.0
        self._month_key: str = self._current_month()
        self._per_user: dict[str, float] = {}
        self._per_app:  dict[str, float] = {}
        self._total_requests: int = 0

    @staticmethod
    def _current_month() -> str:
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m")

    def _reset_if_new_month(self) -> None:
        key = self._current_month()
        if key != self._month_key:
            logger.info("usage.month_reset old=%s new=%s total_spend=$%.4f",
                        self._month_key, key, self._monthly_spend)
            self._monthly_spend = 0.0
            self._per_user = {}
            self._per_app  = {}
            self._month_key = key

    def record(
        self,
        cost: float,
        user_id: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> None:
        self._reset_if_new_month()
        self._monthly_spend += cost
        self._total_requests += 1

        if user_id:
            self._per_user[user_id] = self._per_user.get(user_id, 0.0) + cost
        if app_name:
            self._per_app[app_name] = self._per_app.get(app_name, 0.0) + cost

        if settings.AI_BUDGET_MONTHLY_LIMIT > 0:
            pct = (self._monthly_spend / settings.AI_BUDGET_MONTHLY_LIMIT) * 100
            if pct >= 90:
                logger.warning(
                    "budget.near_limit spend=$%.4f limit=$%.2f pct=%.1f%%",
                    self._monthly_spend, settings.AI_BUDGET_MONTHLY_LIMIT, pct,
                )

    def budget_exceeded(self) -> bool:
        """Returns True if the monthly cloud budget has been hit (kill-switch)."""
        if settings.AI_BUDGET_MONTHLY_LIMIT <= 0:
            return False
        self._reset_if_new_month()
        return self._monthly_spend >= settings.AI_BUDGET_MONTHLY_LIMIT

    def get_summary(self) -> dict:
        self._reset_if_new_month()
        return {
            "month":            self._month_key,
            "total_spend_usd":  round(self._monthly_spend, 6),
            "budget_limit_usd": settings.AI_BUDGET_MONTHLY_LIMIT,
            "budget_used_pct":  round(
                (self._monthly_spend / settings.AI_BUDGET_MONTHLY_LIMIT * 100)
                if settings.AI_BUDGET_MONTHLY_LIMIT > 0 else 0.0, 2
            ),
            "total_requests":   self._total_requests,
            "per_app_spend":    {k: round(v, 6) for k, v in self._per_app.items()},
            "per_user_spend":   {k: round(v, 6) for k, v in self._per_user.items()},
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
_usage: UsageAccumulator | None = None


def get_usage_accumulator() -> UsageAccumulator:
    global _usage
    if _usage is None:
        _usage = UsageAccumulator()
    return _usage
