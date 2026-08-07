from __future__ import annotations

import json

from ..semantic_models import SemanticTask, Intent
from .base import BaseSemanticProvider
from ...ai.ai_manager import AIManager
from ..semantic_models import Entity, EntityType

SYSTEM_PROMPT = """
You are MYRAA's semantic parser.

Your job is to convert the user's command into structured JSON.

Return ONLY valid JSON.

Schema:

{
  "intent": "",
  "target": "",
  "parameters": {},
  "confidence": 1.0
}

Rules:

1. If the user wants to open an APPLICATION
Examples:
- Open Chrome
- Open Notepad
- Open VS Code

Return:

intent = "openApplication"

parameters = {
    "name": "<application name>"
}

2. If the user wants to open a FILE
Examples:
- Open report.pdf
- Open notes.txt
- Open image.png
- Open script.py

Return:

intent = "openFile"

parameters = {
    "path": "<full path if known, otherwise filename>"
}

Never use openApplication for files.

3. If the user wants to open a FOLDER

Examples:
- Open Downloads
- Open Desktop

Return:

intent = "openFolder"

parameters = {
    "name": "<folder>"
}

4. If the user wants to open a WEBSITE

Return:

intent = "openWebsite"

parameters = {
    "url": "<url>"
}

Always choose the most specific tool.

Return JSON only.

No markdown.
No explanation.
"""


class OllamaSemanticProvider(BaseSemanticProvider):

    def __init__(self, ai: AIManager):
        self.ai = ai

    def parse(
        self,
        text: str,
    ) -> SemanticTask:

        response = self.ai.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=text,
            temperature=0.1,
        )

        response = response.strip()

        # Remove markdown if model returns it
        if response.startswith("```"):
            response = response.replace("```json", "")
            response = response.replace("```", "")
            response = response.strip()

        data = json.loads(response)

        # Pydantic v2
        if hasattr(SemanticTask, "model_validate"):
            print("\n========== OLLAMA PARSED DATA ==========")
            print(data)
            print("=======================================\n")

        try:
            print("\n========== OLLAMA PARSED DATA ==========")
            print(data)
            print("========================================\n")

            INTENT_MAP = {
                "openWebsite": Intent.OPEN_WEBSITE,
                "searchWeb": Intent.SEARCH_WEB,
                "searchGoogle": Intent.SEARCH_WEB,
                "searchYouTube": Intent.SEARCH_WEB,

                "openApplication": Intent.OPEN_APPLICATION,
                "closeApplication": Intent.CLOSE_APPLICATION,

                "createFile": Intent.CREATE_FILE,
                "createFolder": Intent.CREATE_FOLDER,

                "deleteFile": Intent.DELETE_FILE,
                "copyFile": Intent.COPY_FILE,
                "moveFile": Intent.MOVE_FILE,

                "chat": Intent.CHAT,
                "question": Intent.QUESTION,
            }

            task = SemanticTask(
                raw_text=text,
                intent=INTENT_MAP.get(
                    data.get("intent"),
                    Intent.UNKNOWN,
                ),
                confidence=float(data.get("confidence", 1.0)),
                metadata=data.get("parameters", {}),
            )

            print("\n========== SEMANTIC TASK ==========")
            print(task)
            print("===================================\n")

            url = data.get("parameters", {}).get("url")

            if url:
                task.add_entity(
                    entity_type=EntityType.SEARCH_QUERY,
                    value=url,
                    confidence=1.0,
                )

            return task

        except Exception as e:
            print("\n========== SEMANTIC BUILD FAILED ==========")
            print(e)
            print("Raw data:", data)
            print("===========================================\n")
            raise

