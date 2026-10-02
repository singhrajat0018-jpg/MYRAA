"""
EPIC-09 deterministic unit tests for ResearchSynthesizer.

The synthesizer's AIManager is replaced with a fake — no real Ollama call.
Verifies grounded prompt construction, Ollama-only provider ordering,
and controlled failure when the provider fails to generate.
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.research.synthesizer import ResearchSynthesizer
from desktop_agent.brain.research.models import ResearchSource


class FakeProvider:
    def __init__(self, name, available=True, output="", raise_on_generate=False):
        self.name = name
        self._available = available
        self._output = output
        self._raise = raise_on_generate
        self.last_kwargs = None

    def available(self):
        return self._available

    def generate(self, **kwargs):
        self.last_kwargs = kwargs
        if self._raise:
            raise RuntimeError(f"{self.name} generation failed")
        return self._output


class FakeAI:
    _PREFERENCES = {"conversational": ["ollama"]}

    def __init__(self, providers):
        self._providers = {p.name: p for p in providers}

    def _by_name(self, name):
        return self._providers.get(name)


def make_synthesizer(*providers):
    synth = ResearchSynthesizer()
    synth._ai = FakeAI(list(providers))
    return synth


def source(provider="tavily", title="NVIDIA", url="https://nvidia.com", date="2026-08-01"):
    return ResearchSource(
        provider=provider,
        title=title,
        url=url,
        snippet="NVIDIA builds GPUs and AI compute infrastructure.",
        published_date=date,
    )


# ---------------------------------------------------------------
# Prompt grounding
# ---------------------------------------------------------------

def test_prompt_is_grounded_and_includes_query_evidence_and_dates():
    ollama = FakeProvider("ollama", output="grounded answer")
    synth = make_synthesizer(ollama)
    sources = [source(date="2026-08-01"), source(title="NoDate", date="")]
    ans, prov = synth.synthesize("Latest NVIDIA news", sources, conversation_context=None)
    assert ans == "grounded answer"
    assert prov == "ollama"
    sys_p = ollama.last_kwargs["system_prompt"]
    usr_p = ollama.last_kwargs["user_prompt"]
    # The prompt must demand grounding and forbid fabrication.
    assert "ONLY the research evidence" in sys_p
    assert "Do NOT invent" in sys_p
    assert "uncertainty" in sys_p
    assert "prefer the most recent" in sys_p
    # Evidence (query, bounded sources, dates) must reach the model.
    assert "Latest NVIDIA news" in usr_p
    assert "https://nvidia.com" in usr_p
    assert "2026-08-01" in usr_p


def test_prompt_bounds_evidence_window():
    ollama = FakeProvider("ollama", output="ok")
    synth = make_synthesizer(ollama)
    many = [source(title=f"S{i}", url=f"https://x.com/{i}", date="") for i in range(20)]
    synth.synthesize("query", many)
    usr_p = ollama.last_kwargs["user_prompt"]
    # Only the bounded evidence window (MAX_SOURCES_FOR_SYNTHESIS=6) is included.
    assert usr_p.count("https://x.com/") == 6


# ---------------------------------------------------------------
# Provider ordering (Ollama only)
# ---------------------------------------------------------------

def test_ollama_succeeds_is_used():
    ollama = FakeProvider("ollama", output="from-ollama")
    synth = make_synthesizer(ollama)
    ans, prov = synth.synthesize("q", [source()])
    assert (ans, prov) == ("from-ollama", "ollama")


def test_ollama_fails_is_controlled_failure():
    ollama = FakeProvider("ollama", raise_on_generate=True)
    synth = make_synthesizer(ollama)
    ans, prov = synth.synthesize("q", [source()])
    assert ans == ""


def test_no_provider_available_returns_none():
    synth = make_synthesizer(FakeProvider("ollama", available=False))
    ans, prov = synth.synthesize("q", [source()])
    assert ans == ""
    assert prov == "none"
