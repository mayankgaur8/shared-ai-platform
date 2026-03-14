"""
Routing table — maps task_type to an ordered list of provider preferences.

Chain order = [primary, first_fallback, last_fallback]
The engine tries them in order until one succeeds.

Quality mode overrides:
  - "low"      → always try Ollama first regardless of task defaults
  - "high"     → always try Premium first regardless of task defaults
  - "balanced" → use the default chain from this table
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.providers.base import ProviderName

O  = ProviderName.OLLAMA
CH = ProviderName.CHEAP_API
PR = ProviderName.PREMIUM_API


@dataclass
class RoutingEntry:
    """
    Routing config for a single task type.

    Fields:
      chain          — default provider order (primary → fallbacks)
      low_chain      — used when quality_mode="low" or user is free-tier
      high_chain     — used when quality_mode="high" or user is premium
      min_tokens_for_cheap   — if prompt is shorter than this, Ollama is preferred
      max_tokens_for_ollama  — if prompt is longer than this, skip Ollama (context limit)
    """
    chain:                  List[ProviderName]
    low_chain:              Optional[List[ProviderName]] = None
    high_chain:             Optional[List[ProviderName]] = None
    min_tokens_for_cheap:   int = 100
    max_tokens_for_ollama:  int = 4000    # Ollama context window guard
    description:            str = ""


# ── Master routing table ───────────────────────────────────────────────────────
# Requirement spec (from architecture brief):
#   grammar_correction          → Ollama  → Cheap API  → Premium API
#   english_conversation        → Cheap   → Premium    → Ollama
#   assignment_generation       → Cheap   → Ollama     → Premium API
#   interview_mock              → Cheap   → Premium    → Ollama
#   resume_analysis             → Cheap   → Premium    → Ollama
#   question_paper_generation   → Ollama  → Cheap API  → Premium API
#   mcq_generation              → Ollama  → Cheap API  → Premium API
# ──────────────────────────────────────────────────────────────────────────────

ROUTING_TABLE: dict[str, RoutingEntry] = {

    "grammar_correction": RoutingEntry(
        chain=[O, CH, PR],
        low_chain=[O, CH, PR],
        high_chain=[CH, PR, O],
        min_tokens_for_cheap=50,
        max_tokens_for_ollama=3000,
        description="Simple grammar/spelling fixes — Ollama handles these well for free.",
    ),

    "english_conversation": RoutingEntry(
        chain=[CH, PR, O],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        min_tokens_for_cheap=20,
        max_tokens_for_ollama=3000,
        description="Interactive tutoring — needs reliability; Cheap API as primary.",
    ),

    "assignment_generation": RoutingEntry(
        chain=[CH, O, PR],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        min_tokens_for_cheap=80,
        max_tokens_for_ollama=3500,
        description="Structured assignments — moderate quality needed.",
    ),

    "mcq_generation": RoutingEntry(
        chain=[O, CH, PR],
        low_chain=[O, CH, PR],
        high_chain=[CH, PR, O],
        min_tokens_for_cheap=50,
        max_tokens_for_ollama=4000,
        description="Multiple choice questions — Ollama handles well at zero cost.",
    ),

    "question_paper_generation": RoutingEntry(
        chain=[O, CH, PR],
        low_chain=[O, CH, PR],
        high_chain=[CH, PR, O],
        min_tokens_for_cheap=100,
        max_tokens_for_ollama=4000,
        description="Full question papers — Ollama first to minimize cost.",
    ),

    "interview_mock": RoutingEntry(
        chain=[CH, PR, O],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        min_tokens_for_cheap=30,
        max_tokens_for_ollama=3000,
        description="Mock interviews — moderate-to-high quality needed.",
    ),

    "resume_analysis": RoutingEntry(
        chain=[CH, PR, O],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        min_tokens_for_cheap=100,
        max_tokens_for_ollama=5000,
        description="Resume review — contextual understanding; Cheap API as primary.",
    ),

    # ── Additional task types ──────────────────────────────────────────────────

    "summarization": RoutingEntry(
        chain=[O, CH, PR],
        low_chain=[O, CH, PR],
        high_chain=[CH, PR, O],
        description="Text summarization — Ollama handles short-to-medium texts well.",
    ),

    "translation": RoutingEntry(
        chain=[CH, O, PR],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        description="Language translation — Cheap API for reliability.",
    ),

    "code_generation": RoutingEntry(
        chain=[CH, PR, O],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        description="Code writing — Cheap API or Premium for accuracy.",
    ),

    "content_writing": RoutingEntry(
        chain=[CH, O, PR],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        description="Blog/article writing.",
    ),

    "general": RoutingEntry(
        chain=[CH, O, PR],
        low_chain=[O, CH, PR],
        high_chain=[PR, CH, O],
        description="Catch-all for unrecognized task types.",
    ),
}


def get_routing_entry(task_type: str) -> RoutingEntry:
    """Return the routing entry for a task type, falling back to 'general'."""
    return ROUTING_TABLE.get(task_type, ROUTING_TABLE["general"])
