"""
Unit tests for the english_coach_chat workflow.

Covers:
  - _parse_english_coach_response: all parse paths + corrections validation
  - ROUTING_TABLE: entry existence, chain order, token limits
  - APP_RULES: avantika_english_coach override, resolve_policy behaviour
  - TaskType enum: value presence

No real Ollama call, no HTTP, no database.
"""
import json
import pytest

# ── Imports under test ────────────────────────────────────────────────────────

from app.orchestration.router import (
    WORKFLOW_PROMPTS,
    _WORKFLOW_TYPES,
    _parse_english_coach_response,
)
from app.services.ai_routing.routing_table import ROUTING_TABLE
from app.services.ai_routing.app_rules import APP_RULES, resolve_policy
from app.services.ai_routing.policies import RoutingPolicy
from app.providers.base import ProviderName
from app.ai_router.schemas import TaskType

O  = ProviderName.OLLAMA
CH = ProviderName.CHEAP_API
PR = ProviderName.PREMIUM_API

_MODEL = "ollama/test-model"

# ─────────────────────────────────────────────────────────────────────────────
# Group 1 — _parse_english_coach_response: happy path
# ─────────────────────────────────────────────────────────────────────────────

def _make_raw(**overrides) -> str:
    """Build a valid JSON string the model would return."""
    base = {
        "reply": "Good effort!",
        "corrections": [
            {"original": "goed", "corrected": "went", "explanation": "irregular verb"},
        ],
        "follow_up_question": "What did you do last weekend?",
    }
    base.update(overrides)
    return json.dumps(base)


def test_parse_valid_json_all_fields_present():
    result = _parse_english_coach_response(_make_raw(), _MODEL)
    assert result["reply"] == "Good effort!"
    assert len(result["corrections"]) == 1
    assert result["corrections"][0]["original"] == "goed"
    assert result["corrections"][0]["corrected"] == "went"
    assert result["corrections"][0]["explanation"] == "irregular verb"
    assert result["follow_up_question"] == "What did you do last weekend?"
    assert result["model_used"] == _MODEL


def test_parse_valid_json_empty_corrections_list():
    raw = _make_raw(corrections=[])
    result = _parse_english_coach_response(raw, _MODEL)
    assert result["corrections"] == []


def test_parse_valid_json_multiple_corrections():
    raw = _make_raw(corrections=[
        {"original": "goed", "corrected": "went", "explanation": "irreg"},
        {"original": "buyed", "corrected": "bought", "explanation": "irreg"},
    ])
    result = _parse_english_coach_response(raw, _MODEL)
    assert len(result["corrections"]) == 2
    assert result["corrections"][1]["original"] == "buyed"


# ─────────────────────────────────────────────────────────────────────────────
# Group 2 — parser: JSON embedded in surrounding prose (regex fallback)
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_json_embedded_in_preamble():
    """Model wrote prose before the JSON block."""
    raw = 'Sure! Here is my feedback:\n' + _make_raw() + '\nHope that helps!'
    result = _parse_english_coach_response(raw, _MODEL)
    assert result["reply"] == "Good effort!"
    assert isinstance(result["corrections"], list)


def test_parse_json_embedded_only_opening_text():
    """Model wrote only a preamble sentence before JSON."""
    raw = "Here is the JSON response: " + _make_raw()
    result = _parse_english_coach_response(raw, _MODEL)
    assert result["reply"] == "Good effort!"


# ─────────────────────────────────────────────────────────────────────────────
# Group 3 — parser: fully malformed model output
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_completely_plain_text_returns_fallback():
    """Model ignored JSON instruction entirely — returns raw text as reply."""
    raw = "Great job! You made a mistake with the past tense."
    result = _parse_english_coach_response(raw, _MODEL)
    assert result["reply"] == raw
    assert result["corrections"] == []
    assert result["follow_up_question"] == ""
    assert result["model_used"] == _MODEL


def test_parse_broken_json_after_extraction_returns_fallback():
    """Regex finds a brace block but it is not valid JSON."""
    raw = "Here is feedback: { broken json without closing"
    result = _parse_english_coach_response(raw, _MODEL)
    assert result["reply"] == raw
    assert result["corrections"] == []


def test_parse_missing_reply_key_uses_raw_string():
    """JSON is valid but 'reply' key is absent — fall back to raw string."""
    data = {"corrections": [], "follow_up_question": "Can you try again?"}
    result = _parse_english_coach_response(json.dumps(data), _MODEL)
    # reply should be the raw JSON string (the data.get("reply", raw) fallback)
    assert result["reply"] == json.dumps(data)


def test_parse_missing_follow_up_key_returns_empty_string():
    """JSON valid but 'follow_up_question' absent — returns empty string."""
    data = {"reply": "Good!", "corrections": []}
    result = _parse_english_coach_response(json.dumps(data), _MODEL)
    assert result["follow_up_question"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# Group 4 — corrections field validation (hardening changes)
# ─────────────────────────────────────────────────────────────────────────────

def test_corrections_not_a_list_is_discarded():
    """Model returned corrections as a string instead of a list."""
    data = {"reply": "Hi!", "corrections": "no mistakes", "follow_up_question": "Try?"}
    result = _parse_english_coach_response(json.dumps(data), _MODEL)
    assert result["corrections"] == []


def test_corrections_with_mixed_valid_and_invalid_items():
    """Some items are dicts, some are plain strings — only dicts survive."""
    data = {
        "reply": "Hi!",
        "corrections": [
            {"original": "goed", "corrected": "went", "explanation": "irreg"},
            "this is a plain string item",
            42,
        ],
        "follow_up_question": "Try?",
    }
    result = _parse_english_coach_response(json.dumps(data), _MODEL)
    assert len(result["corrections"]) == 1
    assert result["corrections"][0]["original"] == "goed"


def test_correction_item_with_missing_keys_uses_empty_string_defaults():
    """Dict item missing some keys — absent keys default to empty string."""
    data = {
        "reply": "Hi!",
        "corrections": [{"original": "goed"}],   # no corrected or explanation
        "follow_up_question": "Try?",
    }
    result = _parse_english_coach_response(json.dumps(data), _MODEL)
    assert result["corrections"][0]["corrected"] == ""
    assert result["corrections"][0]["explanation"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# Group 5 — ROUTING_TABLE entry
# ─────────────────────────────────────────────────────────────────────────────

def test_english_coach_chat_exists_in_routing_table():
    assert "english_coach_chat" in ROUTING_TABLE


def test_english_coach_chat_default_chain_is_cheap_first():
    entry = ROUTING_TABLE["english_coach_chat"]
    assert entry.chain[0] == CH


def test_english_coach_chat_default_chain_ollama_second():
    entry = ROUTING_TABLE["english_coach_chat"]
    assert entry.chain[1] == O


def test_english_coach_chat_default_chain_premium_last():
    entry = ROUTING_TABLE["english_coach_chat"]
    assert entry.chain[2] == PR


def test_english_coach_chat_low_chain_is_ollama_first():
    entry = ROUTING_TABLE["english_coach_chat"]
    assert entry.low_chain is not None
    assert entry.low_chain[0] == O


def test_english_coach_chat_high_chain_is_premium_first():
    entry = ROUTING_TABLE["english_coach_chat"]
    assert entry.high_chain is not None
    assert entry.high_chain[0] == PR


def test_english_coach_chat_max_tokens_for_ollama():
    """Guard value should not exceed what a typical local model handles."""
    entry = ROUTING_TABLE["english_coach_chat"]
    assert entry.max_tokens_for_ollama <= 4000


def test_english_coach_chat_min_tokens_for_cheap_routes_short_greetings():
    """Short messages (e.g. 'Hi') must still reach Cheap API."""
    entry = ROUTING_TABLE["english_coach_chat"]
    assert entry.min_tokens_for_cheap <= 30


# ─────────────────────────────────────────────────────────────────────────────
# Group 6 — APP_RULES / resolve_policy
# ─────────────────────────────────────────────────────────────────────────────

def test_avantika_english_coach_rule_exists():
    assert "avantika_english_coach" in APP_RULES


def test_english_coach_chat_override_exists_in_app_rule():
    rule = APP_RULES["avantika_english_coach"]
    assert "english_coach_chat" in rule.task_policy_overrides


def test_english_coach_chat_override_is_low_cost_first():
    rule = APP_RULES["avantika_english_coach"]
    assert rule.task_policy_overrides["english_coach_chat"] == RoutingPolicy.LOW_COST_FIRST


def test_resolve_policy_free_user_english_coach_app():
    """Free-tier user → task override wins → LOW_COST_FIRST."""
    policy = resolve_policy(
        app_name="avantika_english_coach",
        user_plan="free",
        task_type="english_coach_chat",
        quality_mode="balanced",
    )
    assert policy == RoutingPolicy.LOW_COST_FIRST


def test_resolve_policy_paid_user_english_coach_app():
    """Paid user → task override STILL wins over paid_tier_policy."""
    policy = resolve_policy(
        app_name="avantika_english_coach",
        user_plan="paid",
        task_type="english_coach_chat",
        quality_mode="balanced",
    )
    assert policy == RoutingPolicy.LOW_COST_FIRST


def test_resolve_policy_high_quality_mode_overrides_task_rule():
    """quality_mode='high' is top priority — overrides even task-level rule."""
    policy = resolve_policy(
        app_name="avantika_english_coach",
        user_plan="free",
        task_type="english_coach_chat",
        quality_mode="high",
    )
    assert policy == RoutingPolicy.PREMIUM_FIRST


def test_resolve_policy_unknown_app_returns_balanced_default():
    """Unknown app falls through to DEFAULT_APP_RULE for the task."""
    policy = resolve_policy(
        app_name="some_unknown_app",
        user_plan="free",
        task_type="english_coach_chat",
        quality_mode="balanced",
    )
    # No task override → falls to free_tier_policy of DEFAULT_APP_RULE
    assert policy == RoutingPolicy.LOW_COST_FIRST


# ─────────────────────────────────────────────────────────────────────────────
# Group 7 — TaskType enum
# ─────────────────────────────────────────────────────────────────────────────

def test_task_type_english_coach_chat_exists():
    assert hasattr(TaskType, "ENGLISH_COACH_CHAT")


def test_task_type_english_coach_chat_value():
    assert TaskType.ENGLISH_COACH_CHAT.value == "english_coach_chat"


def test_task_type_english_coach_chat_is_string_subclass():
    """TaskType inherits str — callers can pass it directly as a string."""
    assert isinstance(TaskType.ENGLISH_COACH_CHAT, str)


# ─────────────────────────────────────────────────────────────────────────────
# Group 8 — Workflow registry + type tag
# ─────────────────────────────────────────────────────────────────────────────

def test_english_coach_chat_registered_in_workflow_prompts():
    assert "english_coach_chat" in WORKFLOW_PROMPTS


def test_workflow_prompts_entry_is_tuple_of_two_strings():
    system, user = WORKFLOW_PROMPTS["english_coach_chat"]
    assert isinstance(system, str) and len(system) > 0
    assert isinstance(user, str) and len(user) > 0


def test_workflow_prompt_system_contains_json_instruction():
    """System prompt must instruct the model to return JSON."""
    system, _ = WORKFLOW_PROMPTS["english_coach_chat"]
    assert "json" in system.lower()


def test_workflow_prompt_user_template_has_required_placeholders():
    """User template must include all four input placeholders."""
    _, user = WORKFLOW_PROMPTS["english_coach_chat"]
    for placeholder in ("{topic}", "{level}", "{goal}", "{user_message}"):
        assert placeholder in user, f"Missing placeholder: {placeholder}"


def test_workflow_type_tag_is_english_learning():
    assert _WORKFLOW_TYPES.get("english_coach_chat") == "english_learning"
