"""
Pydantic schemas for the unified AI gateway.

All apps call POST /v1/ai/generate with AIGenerateRequest.
All providers return AIGenerateResponse — same shape regardless of backend.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

class QualityMode(str, Enum):
    LOW      = "low"
    BALANCED = "balanced"
    HIGH     = "high"


class TaskType(str, Enum):
    # Primary task types (from spec)
    GRAMMAR_CORRECTION        = "grammar_correction"
    ENGLISH_CONVERSATION      = "english_conversation"
    ASSIGNMENT_GENERATION     = "assignment_generation"
    MCQ_GENERATION            = "mcq_generation"
    QUESTION_PAPER_GENERATION = "question_paper_generation"
    INTERVIEW_MOCK            = "interview_mock"
    RESUME_ANALYSIS           = "resume_analysis"
    # Extended
    SUMMARIZATION             = "summarization"
    TRANSLATION               = "translation"
    CODE_GENERATION           = "code_generation"
    CONTENT_WRITING           = "content_writing"
    GENERAL                   = "general"


# ── Request ───────────────────────────────────────────────────────────────────

class AIGenerateRequest(BaseModel):
    """
    Unified AI generation request accepted by POST /v1/ai/generate.
    The AI Router uses these fields to select the optimal provider.
    """

    # App identification
    app_name:    Optional[str] = Field(None, description="e.g. avantika_eduai, avantika_english_coach")
    feature:     Optional[str] = Field(None, description="Specific feature within the app")

    # Task routing hints
    task_type:   str           = Field("general", description="See TaskType enum for supported values")
    quality_mode: QualityMode  = Field(QualityMode.BALANCED, description="low=cost-optimized, high=best quality")

    # Content
    prompt:       str          = Field(..., min_length=1, max_length=32000, description="User prompt")
    system_prompt: Optional[str] = Field(None, description="Override system prompt")
    input:        Optional[str]  = Field(None, description="Alias for prompt (legacy compat)")

    # User context
    user_id:    Optional[str]  = Field(None, description="User identifier for usage tracking")
    session_id: Optional[str]  = Field(None, description="Session ID for conversation context")
    user_plan:  str            = Field("free", description="User subscription plan (free/paid/premium)")

    # Model control
    model_preference: Optional[str] = Field(None, description="Request a specific model (if allowed)")
    max_tokens:   int     = Field(1024, ge=1, le=8192)
    temperature:  float   = Field(0.7, ge=0.0, le=2.0)
    stream:       bool    = Field(False, description="Streaming not yet supported via HTTP — use WebSocket")

    # Pass-through metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Arbitrary key-value data")

    @field_validator("prompt", mode="before")
    @classmethod
    def use_input_as_fallback(cls, v: Any, info: Any) -> Any:
        """If prompt is empty/None but 'input' is provided, use input."""
        if not v:
            data = info.data if hasattr(info, "data") else {}
            return data.get("input") or v
        return v

    model_config = {"str_strip_whitespace": True}


# ── Response ─────────────────────────────────────────────────────────────────

class AIGenerateResponse(BaseModel):
    """
    Normalized response returned to all calling apps.
    Provider details are always included for observability.
    Frontend apps should only use: success, response_text, trace_id.
    """
    success:          bool
    trace_id:         str
    provider:         Optional[str]    = None
    model:            Optional[str]    = None
    response_text:    str
    latency_ms:       int              = 0
    tokens_in:        int              = 0
    tokens_out:       int              = 0
    estimated_cost:   float            = 0.0
    fallback_used:    bool             = False
    providers_attempted: List[str]     = Field(default_factory=list)
    cached:           bool             = False
    task_type:        Optional[str]    = None
    app_name:         Optional[str]    = None
    policy:           Optional[str]    = None
    error:            Optional[str]    = None


# ── Health check schemas ───────────────────────────────────────────────────────

class ProviderHealthStatus(BaseModel):
    healthy:          bool
    last_latency_ms:  int   = 0
    recent_failures:  int   = 0
    circuit_breaker:  str   = "closed"   # closed | open | half-open
    last_checked_at:  float = 0.0
    detail:           str   = ""


class AllProvidersHealth(BaseModel):
    ollama:       ProviderHealthStatus
    cheap_api:    ProviderHealthStatus
    premium_api:  ProviderHealthStatus
