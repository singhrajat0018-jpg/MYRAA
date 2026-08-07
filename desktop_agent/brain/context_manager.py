from __future__ import annotations

from datetime import datetime

from .models import BrainContext


class ContextManager:
    """
    Builds and maintains execution context for the Brain.
    """

    def build(self, tool: str, args: dict) -> BrainContext:

        context = BrainContext()

        context.timestamp = datetime.now()

        context.metadata["tool"] = tool

        context.metadata["args"] = args

        return context