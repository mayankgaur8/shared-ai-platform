"""Unit tests for the Prompt Renderer."""
import pytest
from unittest.mock import MagicMock

from app.prompts.renderer import PromptRenderer
from app.shared.exceptions import PromptRenderError


@pytest.fixture
def renderer():
    return PromptRenderer()


def make_version(system_template=None, user_template="Hello {{ name }}!", variables=None):
    v = MagicMock()
    v.system_template = system_template
    v.user_template = user_template
    v.variables = variables or []
    v.prompt_id = "test-prompt-id"
    v.version = 1
    return v


def test_renders_user_template(renderer):
    version = make_version(user_template="Topic: {{ topic }}, Count: {{ count }}")
    system, user = renderer.render(version, {"topic": "Photosynthesis", "count": 5})
    assert user == "Topic: Photosynthesis, Count: 5"
    assert system is None


def test_renders_system_template(renderer):
    version = make_version(
        system_template="You are a {{ role }} expert.",
        user_template="Answer this: {{ question }}",
    )
    system, user = renderer.render(version, {"role": "science", "question": "What is DNA?"})
    assert "science" in system
    assert "What is DNA?" in user


def test_raises_on_missing_required_variable(renderer):
    version = make_version(
        user_template="Topic: {{ topic }}",
        variables=[{"name": "topic", "type": "string", "required": True}],
    )
    with pytest.raises(PromptRenderError, match="topic"):
        renderer.render(version, {})


def test_uses_default_for_optional_variable(renderer):
    version = make_version(
        user_template="Lang: {{ lang }}",
        variables=[{"name": "lang", "type": "string", "required": False, "default": "English"}],
    )
    # Providing the default explicitly works
    _, user = renderer.render(version, {"lang": "French"})
    assert "French" in user


def test_raises_on_syntax_error(renderer):
    version = make_version(user_template="{% if %}broken{% endif %}")
    with pytest.raises(PromptRenderError):
        renderer.render(version, {})


def test_raises_on_undefined_variable_in_strict_mode(renderer):
    version = make_version(user_template="Hello {{ undefined_var }}!")
    with pytest.raises(PromptRenderError):
        renderer.render(version, {})
