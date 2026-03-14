"""
Orchestration router — /v1/generate and /v1/chat endpoints.

This is a functional stub: it calls Ollama directly so you can test
end-to-end before the full WorkflowExecutor is wired up.
Replace the body of each handler with WorkflowExecutor.execute(...)
once the DB models and prompt registry are populated.
"""
import json
import re
import time
import httpx
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from app.config.settings import get_settings

logger = logging.getLogger("saib.orchestration")
router = APIRouter()
settings = get_settings()


# ── Request / Response schemas ────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    workflow: str
    inputs: dict
    session_id: Optional[str] = None
    model_preference: Optional[str] = None
    options: Optional[dict] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    workflow_context: Optional[str] = None
    options: Optional[dict] = None


# ── Simple Ollama call helper ─────────────────────────────────────────────────

async def _call_ollama(system: str, user: str, model: str | None = None) -> dict:
    model_name = model or settings.OLLAMA_DEFAULT_MODEL
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
            resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["message"]["content"],
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
                "model": model_name,
            }
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Ollama at {settings.OLLAMA_BASE_URL}. "
                   "Is the Ollama service running? Run: ollama serve",
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama request timed out.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e.response.text}")


# ── Workflow system prompts (stub — replace with DB prompt registry) ───────────

WORKFLOW_PROMPTS: dict[str, tuple[str, str]] = {
    "quiz_generation": (
        "You are an expert educator. Create well-structured quiz questions. "
        "Always return valid JSON with a 'questions' array.",
        "Generate {question_count} quiz questions about: {topic}. "
        "Grade level: {grade_level}. "
        "Each question must have: id, type, question, options (A/B/C/D), correct_answer, explanation. "
        "Return ONLY valid JSON.",
    ),
    "assignment_generation": (
        "You are an experienced teacher creating detailed assignments.",
        "Create an assignment on: {topic}. "
        "Subject: {subject}. Grade level: {grade_level}. "
        "Include title, objective, tasks, rubric. Return as JSON.",
    ),
    "mock_interview_chat": (
        "You are an experienced interviewer conducting a {interview_type} interview "
        "for the role of {target_role}. Ask one question at a time. "
        "Be professional, encouraging, and give brief feedback after each answer.",
        "{message}",
    ),
    "interview_questions": (
        "You are a senior hiring manager. Create well-crafted interview questions. "
        "Return valid JSON with a 'questions' array.",
        "Generate {question_count} {category} interview questions for: {target_role}. "
        "Difficulty: {difficulty}. Include what_to_assess and ideal_answer_points.",
    ),
    "resume_analysis": (
        "You are an expert ATS specialist and career coach. "
        "Provide detailed, actionable resume feedback.",
        "Analyze this resume for the role of {target_role}:\n\n{resume_text}\n\n"
        "Return JSON with: overall_score, sections, keyword_analysis, strengths, "
        "critical_improvements, rewritten_summary.",
    ),
    "health_chatbot": (
        "You are a compassionate health information assistant. "
        "IMPORTANT: Provide general wellness information only. "
        "Never diagnose or prescribe. Always recommend consulting a healthcare professional. "
        "For emergencies, immediately advise calling emergency services.",
        "{message}",
    ),
    "astrology_insights": (
        "You are an insightful astrology expert. "
        "Provide uplifting, constructive insights framed as possibilities for self-reflection. "
        "Always note readings are for entertainment purposes only.",
        "Provide {insight_type} insights for {zodiac_sign}. "
        "Focus on: love, career, health, personal growth. "
        "Include an affirmation and a disclaimer. Return as JSON.",
    ),
    "mcq_generation": (
        "You are an expert at creating high-quality multiple choice questions. "
        "Each question must have one definitively correct answer and three plausible distractors. "
        "Return only valid JSON.",
        "Create {question_count} MCQ questions on: {topic}. "
        "Subject: {subject}. Difficulty: {difficulty}. "
        "Return JSON with 'mcqs' array, each having: question, options (A/B/C/D), correct, explanation.",
    ),
    "question_paper": (
        "You are an expert examiner creating formal question papers.",
        "Create a question paper on: {topic}. "
        "Subject: {subject}. Duration: {duration}. Total marks: {total_marks}. "
        "Include sections with different question types. Return as JSON.",
    ),
    "english_coach_chat": (
        "You are a warm, encouraging English language coach helping learners improve their English. "
        "When the learner sends a message, you must:\n"
        "1. Reply conversationally in simple, friendly English suited to their level.\n"
        "2. Gently identify any grammar mistakes — be encouraging, never harsh.\n"
        "3. Briefly explain each mistake and give the corrected phrase.\n"
        "4. If the learner's sentence needs improvement, provide a cleaner version.\n"
        "5. Ask exactly one short follow-up practice question to keep them engaged.\n\n"
        "Always respond with valid JSON only — no text outside the JSON block.\n"
        "Required JSON format:\n"
        "{\n"
        '  "reply": "Your friendly, encouraging reply to the learner",\n'
        '  "corrections": [\n'
        '    {"original": "wrong phrase", "corrected": "correct phrase", "explanation": "brief reason"}\n'
        "  ],\n"
        '  "follow_up_question": "One short follow-up question for practice"\n'
        "}\n"
        'If there are no grammar mistakes, return "corrections" as an empty list [].',
        "Topic: {topic}\n"
        "Learner level: {level}\n"
        "Goal: {goal}\n\n"
        "Learner message: {user_message}",
    ),
}


def _build_prompt(template: str, inputs: dict) -> str:
    """Simple .format() substitution — replace with Jinja2 renderer once prompt registry is live."""
    try:
        return template.format(**{k: v for k, v in inputs.items() if isinstance(v, (str, int, float))})
    except KeyError:
        return template  # return unformatted if variables missing — model handles it gracefully


def _parse_english_coach_response(raw: str, model_used: str) -> dict[str, Any]:
    """
    Parse the structured JSON output from the english_coach_chat workflow.
    Falls back gracefully if the model returns malformed JSON.
    """
    _fallback = {"reply": raw, "corrections": [], "follow_up_question": "", "model_used": model_used}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract a JSON object embedded in surrounding text
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            logger.warning("english_coach_chat: no JSON block found in model output")
            return _fallback
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            logger.warning("english_coach_chat: JSON parse failed after extraction")
            return _fallback

    return {
        "reply":             data.get("reply", raw),
        "corrections":       data.get("corrections", []),
        "follow_up_question": data.get("follow_up_question", ""),
        "model_used":        model_used,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate(request: GenerateRequest):
    """Run a named AI workflow. Non-streaming."""
    start = time.monotonic()

    workflow = request.workflow
    logger.info("workflow_start workflow=%s session=%s", workflow, request.session_id)

    prompts = WORKFLOW_PROMPTS.get(workflow)
    if not prompts:
        available = list(WORKFLOW_PROMPTS.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow}' not found. Available: {available}",
        )

    system_tmpl, user_tmpl = prompts

    # Merge inputs, supplying defaults for optional fields per workflow
    inputs = dict(request.inputs)
    if workflow == "english_coach_chat":
        inputs.setdefault("goal", "General English improvement")

    system_prompt = _build_prompt(system_tmpl, inputs)
    user_prompt = _build_prompt(user_tmpl, inputs)

    result = await _call_ollama(
        system=system_prompt,
        user=user_prompt,
        model=request.model_preference,
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    model_used = f"ollama/{result['model']}"
    logger.info("workflow=%s model=%s latency=%dms", workflow, model_used, latency_ms)

    # ── Workflow-specific structured response ─────────────────────────────────
    if workflow == "english_coach_chat":
        parsed = _parse_english_coach_response(result["content"], model_used)
        return {
            "workflow": workflow,
            **parsed,
            "tokens_used": {
                "input": result["input_tokens"],
                "output": result["output_tokens"],
            },
            "latency_ms": latency_ms,
            "cost_usd": 0.0,
            "cached": False,
        }

    return {
        "workflow": workflow,
        "model_used": model_used,
        "output": result["content"],
        "tokens_used": {
            "input": result["input_tokens"],
            "output": result["output_tokens"],
        },
        "latency_ms": latency_ms,
        "cost_usd": 0.0,
        "cached": False,
        "_note": "Stub mode: using direct Ollama call. Wire up WorkflowExecutor for full platform features.",
    }


@router.post("/chat")
async def chat(request: ChatRequest):
    """Multi-turn chat with optional workflow context."""
    start = time.monotonic()

    workflow = request.workflow_context or "mock_interview_chat"
    prompts = WORKFLOW_PROMPTS.get(workflow, (
        "You are a helpful AI assistant.",
        "{message}",
    ))

    system_tmpl, user_tmpl = prompts
    system_prompt = system_tmpl
    user_prompt = _build_prompt(user_tmpl, {"message": request.message})

    result = await _call_ollama(system=system_prompt, user=user_prompt)
    latency_ms = int((time.monotonic() - start) * 1000)

    return {
        "session_id": request.session_id or "no-session",
        "response": result["content"],
        "model_used": f"ollama/{result['model']}",
        "tokens_used": {
            "input": result["input_tokens"],
            "output": result["output_tokens"],
        },
        "latency_ms": latency_ms,
        "_note": "Stub mode: session memory not persisted yet. Wire up MemoryService for persistence.",
    }
