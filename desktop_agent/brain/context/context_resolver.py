"""
MYRAA Context Resolver
"""

from __future__ import annotations


class ContextResolver:

    def resolve(
        self,
        text: str,
        working_memory,
    ) -> str:

        app = working_memory.current_application()

        if app is None:
            return text

        lower = text.lower()

        replacements = {
            " it ": f" {app} ",
            " this ": f" {app} ",
            " that ": f" {app} ",
        }

        resolved = f" {text} "

        for key, value in replacements.items():
            resolved = resolved.replace(key, value)

        return resolved.strip()