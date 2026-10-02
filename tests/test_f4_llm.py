"""F4 tests: real LLM invocation, provider fallback, structured tool-call validation."""

from __future__ import annotations

import pytest

from desktop_agent.brain.ai.ai_manager import AIManager
from desktop_agent.registry import ValidationLayer, ToolError


class FakeProvider:
    def __init__(self, name="fake", text="hello from fake", raises=None, stream_chunks=None):
        self.name = name
        self._text = text
        self._raises = raises
        self._stream = stream_chunks or ["a", "b", "c"]
        self.calls = []

    def available(self):
        return True

    def generate(self, system_prompt, user_prompt, **kwargs):
        self.calls.append((system_prompt, user_prompt))
        if self._raises:
            raise self._raises
        return self._text

    def stream_generate(self, system_prompt, user_prompt, **kwargs):
        self.calls.append((system_prompt, user_prompt))
        if self._raises:
            raise self._raises
        for chunk in self._stream:
            yield chunk


def _manager_with(providers: dict, pref):
    m = AIManager()
    m._providers = dict(providers)
    m._preference_for = lambda hints, route=None: list(pref)
    return m


def test_generate_invokes_provider_and_returns_text():
    p = FakeProvider()
    m = _manager_with({"fake": p}, ["fake"])
    out = m.generate(system_prompt="sys", user_prompt="hello")
    assert out == "hello from fake"
    assert p.calls == [("sys", "hello")]


def test_generate_falls_back_to_next_provider_on_failure():
    bad = FakeProvider(name="bad", raises=RuntimeError("boom"))
    good = FakeProvider(name="good", text="recovered")
    m = _manager_with({"bad": bad, "good": good}, ["bad", "good"])
    out = m.generate(system_prompt="s", user_prompt="u")
    assert out == "recovered"
    assert good.calls  # the good provider was actually invoked


def test_generate_skips_unavailable_provider():
    class Unavailable(FakeProvider):
        def available(self):
            return False

    good = FakeProvider(name="good", text="ok")
    m = _manager_with({"bad": Unavailable(name="bad"), "good": good}, ["bad", "good"])
    out = m.generate(system_prompt="s", user_prompt="u")
    assert out == "ok"


def test_generate_raises_when_every_provider_fails():
    bad1 = FakeProvider(name="bad1", raises=RuntimeError("x"))
    bad2 = FakeProvider(name="bad2", raises=RuntimeError("y"))
    m = _manager_with({"bad1": bad1, "bad2": bad2}, ["bad1", "bad2"])
    with pytest.raises(RuntimeError):
        m.generate(system_prompt="s", user_prompt="u")


def test_stream_generate_yields_chunks():
    p = FakeProvider()
    m = _manager_with({"fake": p}, ["fake"])
    chunks = list(m.stream_generate(system_prompt="s", user_prompt="u"))
    assert chunks == ["a", "b", "c"]
    assert p.calls


# ---------------------------------------------------------------------------
# Structured tool-call schema validation (F4)
# ---------------------------------------------------------------------------

def test_validation_rejects_missing_required_args():
    with pytest.raises(ToolError, match="missing required argument"):
        ValidationLayer.validate({}, None, tool_name="createFile")


def test_validation_rejects_blank_required_args():
    with pytest.raises(ToolError, match="missing required argument"):
        ValidationLayer.validate({"path": "   "}, None, tool_name="readFile")


def test_validation_accepts_complete_args():
    out = ValidationLayer.validate({"path": "C:/Users/singh/a.txt", "content": "hi"}, None, tool_name="createFile")
    assert out["path"] == "C:/Users/singh/a.txt"


def test_validation_enforces_or_required_args():
    # openWebsite requires either 'name' or 'url'.
    with pytest.raises(ToolError, match="requires one of"):
        ValidationLayer.validate({}, None, tool_name="openWebsite")
    assert ValidationLayer.validate({"name": "youtube"}, None, tool_name="openWebsite")
    assert ValidationLayer.validate({"url": "https://example.com"}, None, tool_name="openWebsite")


def test_validation_rejects_non_dict_args():
    with pytest.raises(ToolError, match="must be an object"):
        ValidationLayer.validate("not-a-dict", None, tool_name="typeText")


def test_validation_ignores_tools_without_spec():
    # Tools with no required-arg spec pass through unchanged.
    assert ValidationLayer.validate({"whatever": 1}, None, tool_name="currentDateTime") == {"whatever": 1}
    assert ValidationLayer.validate({}, None, tool_name="systemInfo") == {}