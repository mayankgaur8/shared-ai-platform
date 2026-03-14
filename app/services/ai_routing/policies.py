"""
Routing policy layer.

A policy transforms the default provider chain from the routing table
into the final chain the engine will attempt.

Policies:
  low_cost_first    — Ollama → Cheap → Premium  (maximize free usage)
  balanced          — use routing_table defaults (recommended)
  premium_first     — Premium → Cheap → Ollama  (best quality)
  fallback_safe     — same as balanced, but always appends all providers
  strict_local_only — Ollama only (no cloud calls allowed)

App-specific overrides are layered on top by app_rules.py.
"""
from __future__ import annotations

from enum import Enum
from typing import List

from app.providers.base import ProviderName

O  = ProviderName.OLLAMA
CH = ProviderName.CHEAP_API
PR = ProviderName.PREMIUM_API

ALL_PROVIDERS = [O, CH, PR]


class RoutingPolicy(str, Enum):
    LOW_COST_FIRST    = "low_cost_first"
    BALANCED          = "balanced"
    PREMIUM_FIRST     = "premium_first"
    FALLBACK_SAFE     = "fallback_safe"
    STRICT_LOCAL_ONLY = "strict_local_only"


def apply_policy(
    chain: List[ProviderName],
    policy: RoutingPolicy,
) -> List[ProviderName]:
    """
    Given a base chain and a policy, return the final ordered provider list.
    Duplicates are removed while preserving order.
    """
    if policy == RoutingPolicy.LOW_COST_FIRST:
        # Force Ollama first, then fill in the rest
        return _dedupe([O, CH, PR])

    elif policy == RoutingPolicy.PREMIUM_FIRST:
        # Force Premium first
        return _dedupe([PR, CH, O])

    elif policy == RoutingPolicy.STRICT_LOCAL_ONLY:
        # Never call cloud APIs
        return [O]

    elif policy == RoutingPolicy.FALLBACK_SAFE:
        # Use the given chain but guarantee all providers are included as fallbacks
        return _dedupe(chain + [p for p in ALL_PROVIDERS if p not in chain])

    else:  # BALANCED or unknown — trust the routing table
        return _dedupe(chain)


def _dedupe(lst: List[ProviderName]) -> List[ProviderName]:
    """Preserve order, remove duplicates."""
    seen = set()
    result = []
    for item in lst:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
