from __future__ import annotations

from .semantic_models import (
    SemanticTask,
    Intent,
    EntityType,
)


class LocalSemanticParser:

    def parse(self, text: str) -> SemanticTask:
        lower = text.lower().strip()

        task = SemanticTask(
            raw_text=text,
            normalized_text=lower,
            confidence=0.6,
        )

        if lower.startswith("openapplication"):
            task.intent = Intent.OPEN_APPLICATION

            import json

            try:
                start = text.find("{")
                if start != -1:
                    args = json.loads(text[start:])
                    task.add_entity(
                        EntityType.APPLICATION,
                        args.get("name", "")
                    )
            except Exception:
                pass

            return task


        if lower.startswith("closeapplication"):
            task.intent = Intent.CLOSE_APPLICATION

            import json

            try:
                start = text.find("{")
                if start != -1:
                    args = json.loads(text[start:])
                    task.add_entity(
                        EntityType.APPLICATION,
                        args.get("name", "")
                    )
            except Exception:
                pass

            return task

        if lower.startswith("openfolder"):
            task.intent = Intent.OPEN_FOLDER

            import json

            try:
                start = text.find("{")
                if start != -1:
                    args = json.loads(text[start:])
                    task.add_entity(
                        EntityType.FOLDER,
                        args.get("name", "")
                    )
            except Exception:
                pass

            return task