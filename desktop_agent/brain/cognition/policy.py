from __future__ import annotations

from .priority import Priority


class CognitivePolicy:

    @staticmethod
    def priority_for(event):

        severity = str(
            getattr(event, "severity", "")
        ).lower()

        if "critical" in severity:
            return Priority.CRITICAL

        if "high" in severity:
            return Priority.HIGH

        if "medium" in severity:
            return Priority.NORMAL

        return Priority.LOW