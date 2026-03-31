"""
Typed Pydantic models for workflow-specific orchestration payloads.

These models are additive and mirror the current runtime contract for
the english_coach_chat workflow without changing handler logic.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CorrectionItem(BaseModel):
    """Single grammar correction returned by english_coach_chat."""

    original: str = Field(default="", description="Original learner phrase")
    corrected: str = Field(default="", description="Corrected phrase")
    explanation: str = Field(default="", description="Brief explanation of the correction")


class EnglishCoachChatInputs(BaseModel):
    """Typed inputs for the english_coach_chat workflow."""

    topic: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    level: str = Field(..., min_length=1)
    goal: str = Field(default="General English improvement", min_length=1)

    model_config = {"str_strip_whitespace": True}


class EnglishCoachChatRequest(BaseModel):
    """Typed request body for POST /v1/generate with english_coach_chat."""

    workflow: Literal["english_coach_chat"] = "english_coach_chat"
    inputs: EnglishCoachChatInputs
    session_id: Optional[str] = None
    model_preference: Optional[str] = None
    options: Optional[dict] = None

    model_config = {"str_strip_whitespace": True}


class TokensUsed(BaseModel):
    """Token counts returned by the current orchestration response."""

    input: int = 0
    output: int = 0


class EnglishCoachChatResponse(BaseModel):
    """Structured response returned by the english_coach_chat workflow."""

    workflow: Literal["english_coach_chat"] = "english_coach_chat"
    workflow_type: Literal["english_learning"] = "english_learning"
    reply: str
    corrections: list[CorrectionItem] = Field(default_factory=list)
    follow_up_question: str = ""
    model_used: str
    tokens_used: TokensUsed
    latency_ms: int = 0
    cost_usd: float = 0.0
    cached: bool = False

    model_config = {"str_strip_whitespace": True}
