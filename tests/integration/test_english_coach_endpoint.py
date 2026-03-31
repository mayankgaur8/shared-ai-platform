"""
Integration tests for the english_coach_chat workflow endpoint.

Tests POST /v1/generate and GET /v1/workflows against the full FastAPI app.
_call_ollama is monkeypatched — no real Ollama process required.
No database is needed for the orchestration router.

Run:
    pytest tests/integration/test_english_coach_endpoint.py -v
"""
import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def http_client():
    """
    Lightweight async client — no DB override needed.
    The orchestration router does not use SQLAlchemy.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


def _ollama_response(content: str, model: str = "llama3.2") -> dict:
    """Build the dict _call_ollama returns on success."""
    return {
        "content":       content,
        "input_tokens":  50,
        "output_tokens": 80,
        "model":         model,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

_VALID_COACH_JSON = json.dumps({
    "reply": "Great effort! Two small fixes below.",
    "corrections": [
        {"original": "goed", "corrected": "went", "explanation": "irregular verb"},
        {"original": "buyed", "corrected": "bought", "explanation": "irregular verb"},
    ],
    "follow_up_question": "What did you do last weekend?",
})

_VALID_INPUTS = {
    "topic": "Daily routines",
    "user_message": "Yesterday I goed to market and buyed many things.",
    "level": "beginner",
    "goal": "Improve past tense",
}

_INPUTS_NO_GOAL = {
    "topic": "Daily routines",
    "user_message": "Yesterday I goed to market.",
    "level": "beginner",
    # goal intentionally omitted
}


# ── Test Group 1: happy path ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_returns_200(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_generate_response_has_required_fields(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    body = resp.json()
    for field in ("workflow", "reply", "corrections", "follow_up_question",
                  "model_used", "tokens_used", "latency_ms", "cost_usd", "cached"):
        assert field in body, f"Missing field in response: {field}"


@pytest.mark.asyncio
async def test_generate_corrections_is_list(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert isinstance(resp.json()["corrections"], list)


@pytest.mark.asyncio
async def test_generate_correction_items_have_expected_keys(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    corrections = resp.json()["corrections"]
    assert len(corrections) == 2
    for item in corrections:
        assert "original" in item
        assert "corrected" in item
        assert "explanation" in item


@pytest.mark.asyncio
async def test_generate_workflow_field_equals_english_coach_chat(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert resp.json()["workflow"] == "english_coach_chat"


@pytest.mark.asyncio
async def test_generate_workflow_type_is_english_learning(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert resp.json()["workflow_type"] == "english_learning"


@pytest.mark.asyncio
async def test_generate_tokens_used_shape(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    tokens = resp.json()["tokens_used"]
    assert "input" in tokens and "output" in tokens
    assert tokens["input"] == 50
    assert tokens["output"] == 80


# ── Test Group 2: optional goal field ────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_goal_omitted_does_not_raise(http_client, monkeypatch):
    """Omitting 'goal' must never result in a 500 or KeyError."""
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _INPUTS_NO_GOAL},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_generate_goal_omitted_still_returns_structured_response(http_client, monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _INPUTS_NO_GOAL},
    )
    body = resp.json()
    assert "reply" in body
    assert "corrections" in body
    assert "follow_up_question" in body


# ── Test Group 3: parser fallback paths ──────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_model_returns_plain_text_does_not_500(http_client, monkeypatch):
    """Model ignores JSON instruction — endpoint must not raise."""
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(
            "Great job! You made some small past-tense mistakes."
        )),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_generate_model_returns_plain_text_fallback_shape(http_client, monkeypatch):
    """Fallback: raw text → reply, empty corrections, empty follow_up."""
    plain = "Great job! Two small past-tense mistakes."
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(plain)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    body = resp.json()
    assert body["reply"] == plain
    assert body["corrections"] == []
    assert body["follow_up_question"] == ""


@pytest.mark.asyncio
async def test_generate_model_returns_json_with_wrong_corrections_type(http_client, monkeypatch):
    """corrections is a string instead of list — must be silently discarded."""
    bad_json = json.dumps({
        "reply": "Good!",
        "corrections": "no mistakes today",
        "follow_up_question": "Try again?",
    })
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(bad_json)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert resp.status_code == 200
    assert resp.json()["corrections"] == []


@pytest.mark.asyncio
async def test_generate_model_returns_json_with_mixed_corrections(http_client, monkeypatch):
    """corrections list has valid dicts and invalid items — only dicts survive."""
    mixed_json = json.dumps({
        "reply": "Good!",
        "corrections": [
            {"original": "goed", "corrected": "went", "explanation": "irreg"},
            "stray string",
        ],
        "follow_up_question": "Try again?",
    })
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(mixed_json)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    body = resp.json()
    assert len(body["corrections"]) == 1
    assert body["corrections"][0]["original"] == "goed"


@pytest.mark.asyncio
async def test_generate_model_returns_json_embedded_in_prose(http_client, monkeypatch):
    """Model wraps JSON in surrounding text — regex fallback must extract it."""
    wrapped = "Sure! Here is my response:\n" + _VALID_COACH_JSON + "\nHope this helps!"
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(wrapped)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Great effort! Two small fixes below."
    assert len(body["corrections"]) == 2


# ── Test Group 4: error cases ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_unknown_workflow_returns_404(http_client):
    """Requesting a non-existent workflow must return 404, not 500."""
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "does_not_exist", "inputs": {}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_404_detail_lists_available_workflows(http_client):
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "does_not_exist", "inputs": {}},
    )
    detail = resp.json()["detail"]
    assert "english_coach_chat" in detail


# ── Test Group 5: workflow registry ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_workflows_includes_english_coach_chat(http_client):
    resp = await http_client.get("/v1/workflows")
    assert resp.status_code == 200
    assert "english_coach_chat" in resp.json()["workflows"]


@pytest.mark.asyncio
async def test_list_workflows_returns_list(http_client):
    resp = await http_client.get("/v1/workflows")
    assert isinstance(resp.json()["workflows"], list)


@pytest.mark.asyncio
async def test_existing_workflows_not_broken(http_client, monkeypatch):
    """Sanity check: mcq_generation still works after our changes."""
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response('{"mcqs": []}')),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={
            "workflow": "mcq_generation",
            "inputs": {"topic": "Maths", "subject": "Algebra", "difficulty": "easy", "question_count": 2},
        },
    )
    assert resp.status_code == 200
    # mcq_generation returns generic "output" field, not structured
    assert "output" in resp.json()


# ── Test Group 6: response does not include generic "_note" field ─────────────

@pytest.mark.asyncio
async def test_english_coach_response_has_no_stub_note_field(http_client, monkeypatch):
    """english_coach_chat returns structured response — not the stub note."""
    monkeypatch.setattr(
        "app.orchestration.router._call_ollama",
        AsyncMock(return_value=_ollama_response(_VALID_COACH_JSON)),
    )
    resp = await http_client.post(
        "/v1/generate",
        json={"workflow": "english_coach_chat", "inputs": _VALID_INPUTS},
    )
    assert "_note" not in resp.json()
    assert "output" not in resp.json()
