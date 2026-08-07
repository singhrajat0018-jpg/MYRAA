"""
MYRAA Cognitive Engine
Gemini Semantic Provider

Production Version
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from google import genai

from .base import BaseSemanticProvider
from .parser_response import ParserResponse

from ..semantic_models import (
    SemanticTask,
    Intent,
    EntityType,
)

SYSTEM_PROMPT = """
You are MYRAA's Semantic Parser.

Your ONLY job is to convert user requests into JSON.

Return ONLY JSON.

Schema:

{
    "intent":"OPEN_APPLICATION",
    "confidence":0.98,
    "entities":[
        {
            "entity_type":"APPLICATION",
            "value":"Chrome"
        }
    ]
}

Rules:

- Never explain.
- Never answer.
- Never use markdown.
- Always return valid JSON.
"""


class GeminiSemanticProvider(BaseSemanticProvider):

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.6-flash",
    ):

        api_key = api_key or os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "Gemini API key not found."
            )

        self.client = genai.Client(
            api_key=api_key
        )

        self.model = model

    # ----------------------------------------------------

    def parse(
        self,
        text: str,
    ) -> ParserResponse:

        start = time.perf_counter()

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                SYSTEM_PROMPT,
                text,
            ],
        )

        raw = response.text or ""

        json_text = self._extract_json(raw)

        data = json.loads(json_text)

        task = self._build_task(
            raw_text=text,
            data=data,
        )

        latency = (
            time.perf_counter() - start
        ) * 1000

        return ParserResponse(
            task=task,
            raw_response=raw,
            provider="Gemini",
            latency_ms=latency,
        )

    # ----------------------------------------------------

    def _build_task(
        self,
        raw_text: str,
        data: dict[str, Any],
    ) -> SemanticTask:

        # ----------------------------
        # Intent
        # ----------------------------

        intent_raw = str(
            data.get("intent", "UNKNOWN")
        )

        intent_name = (
            intent_raw
            .strip()
            .upper()
            .replace(" ", "_")
            .replace("-", "_")
        )

        try:
            intent = Intent[intent_name]
        except KeyError:
            intent = Intent.UNKNOWN

        # ----------------------------
        # Create Semantic Task
        # ----------------------------

        task = SemanticTask(
            raw_text=raw_text,
            normalized_text=raw_text.lower(),
            intent=intent,
            confidence=float(
                data.get("confidence", 0.0)
            ),
        )

        # ----------------------------
        # Entities
        # ----------------------------

        for item in data.get("entities", []):

            entity_raw = str(
                item.get(
                    "entity_type",
                    "UNKNOWN",
                )
            )

            entity_name = (
                entity_raw
                .strip()
                .upper()
                .replace(" ", "_")
                .replace("-", "_")
            )

            try:
                entity_enum = EntityType[
                    entity_name
                ]
            except KeyError:
                entity_enum = EntityType.UNKNOWN

            task.add_entity(
                entity_type=entity_enum,
                value=item.get("value"),
                confidence=float(
                    item.get(
                        "confidence",
                        1.0,
                    )
                ),
            )

        return task

    # ----------------------------------------------------

    @staticmethod
    def _extract_json(
        text: str,
    ) -> str:
        """
        Extract JSON from Gemini response.

        Handles:
        - Plain JSON
        - ```json ... ```
        - Extra whitespace
        """

        text = text.strip()

        if text.startswith("```"):

            text = re.sub(
                r"^```json",
                "",
                text,
                flags=re.IGNORECASE,
            )

            text = re.sub(
                r"^```",
                "",
                text,
            )

            text = text.rstrip("`").strip()

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                "No JSON object found in Gemini response."
            )

        return text[start:end + 1]