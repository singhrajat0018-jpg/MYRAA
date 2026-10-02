"""
MYRAA Research synthesis (EPIC-08)

Research providers produce EVIDENCE. They are not the final answer generator.

The synthesizer converts bounded, deduplicated, ranked evidence into the final
MYRAA answer using the EXISTING AIManager provider architecture (Ollama).
No new LLM client is created.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..ai.ai_manager import AIManager
from .models import ResearchSource

log = logging.getLogger(__name__)

# Bounded evidence window fed to the model.
MAX_SOURCES_FOR_SYNTHESIS = 6
MAX_SNIPPET_CHARS = 400
MAX_CONVERSATION_TURNS = 6


class ResearchSynthesizer:
    def __init__(self, ai_manager=None) -> None:
        # AIManager is the authoritative LLM-provider router (Ollama).
        # Tavily/DDG/Wikipedia are never providers here.
        if ai_manager is not None:
            self._ai = ai_manager
        else:
            from desktop_agent.brain.ai.ai_manager import AIManager
            self._ai = AIManager()

    def synthesize(
        self,
        query: str,
        sources: List[ResearchSource],
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, str]:
        """
        Returns (final_answer, synthesis_provider_name).

        Grounds the answer in the retrieved evidence. If no AI provider is
        available, returns a controlled failure (never a fabricated current
        answer).
        """
        system_prompt = (
            "You are MYRAA, a helpful Windows desktop AI assistant. "
            "You answer a user's research question using ONLY the research "
            "evidence provided below. Follow these rules:\n"
            "- Answer the user's actual question.\n"
            "- Ground every claim in the provided sources.\n"
            "- Distinguish established facts from uncertainty.\n"
            "- Do NOT invent or assume information the sources do not support.\n"
            "- For questions about current events, prices, or markets, prefer "
            "the most recent sources.\n"
            "- Mention source context naturally where useful, e.g. "
            "'According to [title]'.\n"
            "- If the evidence is insufficient, say so clearly instead of "
            "guessing."
        )

        user_prompt = f"User question: {query}\n\n"

        if conversation_context:
            lines = []
            for turn in conversation_context[-MAX_CONVERSATION_TURNS:]:
                role = turn.get("role", "")
                text = (turn.get("text", "") or "").strip()
                if not text:
                    continue
                label = "User" if role == "user" else "MYRAA"
                lines.append(f"{label}: {text}")
            if lines:
                user_prompt += "Recent conversation:\n" + "\n".join(lines) + "\n\n"

        user_prompt += "Research evidence (title | url | date | snippet):\n"

        for src in sources[:MAX_SOURCES_FOR_SYNTHESIS]:
            date = src.published_date or "no date"
            snippet = src.snippet[:MAX_SNIPPET_CHARS]
            user_prompt += (
                f"- {src.title or '(untitled)'} | {src.url} | {date} | {snippet}\n"
            )

        # Ollama is the only LLM provider. We try it directly because
        # `route()` returns a single provider and a provider can be
        # "available" yet fail to generate (e.g. Ollama not running).
        preference = ["ollama"]

        # At least one provider must be available, else controlled failure.
        if not any(
            self._ai._by_name(name) is not None
            and self._ai._by_name(name).available()
            for name in preference
        ):
            return "", "none"

        last_provider = "none"

        for name in preference:
            provider = self._ai._by_name(name)
            if provider is None or not provider.available():
                continue

            last_provider = provider.name

            try:
                raw = provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("[Research:synthesis] %s generation failed: %s", name, exc)
                continue  # fall back to the next provider

            output = (raw or "").strip()

            if output:
                return output, provider.name

        # No provider produced an answer -> controlled failure (never a
        # fabricated current answer).
        return "", last_provider
