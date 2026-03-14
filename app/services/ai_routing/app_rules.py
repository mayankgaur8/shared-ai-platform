"""
App-specific routing overrides.

Each app can have rules that adjust:
  - default policy
  - quality_mode forced for certain plans
  - task_type to policy mapping

These are applied AFTER the routing table chain is selected
and BEFORE the final policy is applied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict

from app.providers.base import ProviderName
from .policies import RoutingPolicy

O  = ProviderName.OLLAMA
CH = ProviderName.CHEAP_API
PR = ProviderName.PREMIUM_API


@dataclass
class AppRule:
    """
    Routing override for a named app.

    Fields:
      default_policy         — policy applied to all requests from this app
      free_tier_policy       — policy for free-plan users of this app
      paid_tier_policy       — policy for paid-plan users of this app
      task_policy_overrides  — per-task policy overrides for this app
      force_quality_mode     — if set, overrides incoming quality_mode
      allowed_providers      — if set, restrict to these providers only
    """
    default_policy:         RoutingPolicy = RoutingPolicy.BALANCED
    free_tier_policy:       RoutingPolicy = RoutingPolicy.LOW_COST_FIRST
    paid_tier_policy:       RoutingPolicy = RoutingPolicy.BALANCED
    task_policy_overrides:  Dict[str, RoutingPolicy] = field(default_factory=dict)
    force_quality_mode:     Optional[str] = None      # "low" | "balanced" | "high"
    allowed_providers:      Optional[list] = None     # restrict to subset


# ── Per-app rules ──────────────────────────────────────────────────────────────

APP_RULES: Dict[str, AppRule] = {

    "avantika_eduai": AppRule(
        default_policy=RoutingPolicy.LOW_COST_FIRST,
        free_tier_policy=RoutingPolicy.LOW_COST_FIRST,   # Free users → Ollama first
        paid_tier_policy=RoutingPolicy.BALANCED,
        task_policy_overrides={
            "question_paper_generation": RoutingPolicy.LOW_COST_FIRST,
            "mcq_generation":            RoutingPolicy.LOW_COST_FIRST,
            "assignment_generation":     RoutingPolicy.BALANCED,
        },
    ),

    "avantika_interview_prep": AppRule(
        default_policy=RoutingPolicy.BALANCED,
        free_tier_policy=RoutingPolicy.LOW_COST_FIRST,
        paid_tier_policy=RoutingPolicy.BALANCED,
        task_policy_overrides={
            "interview_mock": RoutingPolicy.BALANCED,
            "resume_analysis": RoutingPolicy.BALANCED,
        },
    ),

    "avantika_english_coach": AppRule(
        default_policy=RoutingPolicy.BALANCED,
        free_tier_policy=RoutingPolicy.LOW_COST_FIRST,
        paid_tier_policy=RoutingPolicy.BALANCED,         # Paid → Cheap API first for reliability
        task_policy_overrides={
            "grammar_correction":    RoutingPolicy.LOW_COST_FIRST,
            "english_conversation":  RoutingPolicy.BALANCED,
            "english_coach_chat":    RoutingPolicy.LOW_COST_FIRST,  # Groq/phi3 first; premium only on fallback
        },
    ),

    "avantika_resume_builder": AppRule(
        default_policy=RoutingPolicy.BALANCED,
        free_tier_policy=RoutingPolicy.LOW_COST_FIRST,
        paid_tier_policy=RoutingPolicy.BALANCED,
        task_policy_overrides={
            "resume_analysis": RoutingPolicy.BALANCED,
        },
    ),
}

# Default rule for unknown apps
DEFAULT_APP_RULE = AppRule(
    default_policy=RoutingPolicy.BALANCED,
    free_tier_policy=RoutingPolicy.LOW_COST_FIRST,
    paid_tier_policy=RoutingPolicy.BALANCED,
)


def get_app_rule(app_name: Optional[str]) -> AppRule:
    """Return the routing rule for an app, falling back to the default."""
    if not app_name:
        return DEFAULT_APP_RULE
    return APP_RULES.get(app_name.lower().replace(" ", "_"), DEFAULT_APP_RULE)


def resolve_policy(
    app_name: Optional[str],
    user_plan: str,
    task_type: str,
    quality_mode: str,
) -> RoutingPolicy:
    """
    Determine the final RoutingPolicy from app + user plan + task + quality.

    Priority (highest to lowest):
      1. quality_mode="high" → PREMIUM_FIRST
      2. quality_mode="low"  → LOW_COST_FIRST
      3. App-specific task override
      4. App-specific plan override
      5. App default policy
    """
    if quality_mode == "high":
        return RoutingPolicy.PREMIUM_FIRST
    if quality_mode == "low":
        return RoutingPolicy.LOW_COST_FIRST

    rule = get_app_rule(app_name)

    # Task-level override within this app
    if task_type in rule.task_policy_overrides:
        return rule.task_policy_overrides[task_type]

    # Plan-level override
    is_paid = user_plan.lower() in ("paid", "premium", "pro", "enterprise")
    if is_paid:
        return rule.paid_tier_policy
    else:
        return rule.free_tier_policy
