from __future__ import annotations

import json
import re

from .action_intent import ActionIntent


FUNCTION_PATTERN = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(\{.*\})?$",
    re.DOTALL,
)


class FunctionCallParser:

    def parse(self, text: str) -> ActionIntent | None:

        text = text.strip()

        match = FUNCTION_PATTERN.match(text)

        if not match:
            return None

        function_name = match.group(1)

        arguments = {}

        if match.group(2):

            try:
                arguments = json.loads(match.group(2))

            except Exception:
                return None

        return ActionIntent(
            name=function_name,
            parameters=arguments,
        )