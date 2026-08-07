"""
Initiative Adapter

Converts autonomous initiatives into SemanticTasks so they
can reuse the normal Brain pipeline.

Autonomy
    ↓
Initiative
    ↓
SemanticTask
"""

from __future__ import annotations

from desktop_agent.brain.semantic.semantic_models import (
    SemanticTask,
    Intent,
)

from .initiative_engine import (
    Initiative,
    InitiativeType,
)


class InitiativeAdapter:

    """
    Converts Initiative -> SemanticTask
    """

    def convert(
        self,
        initiative: Initiative,
    ) -> SemanticTask | None:
        print(f"[Autonomy] Initiative -> {initiative.title}")
        if initiative.type == InitiativeType.NOTIFY:

            task = SemanticTask(
                intent=Intent.CHAT,
                raw_text=initiative.description,
                goal=initiative.title,
            )

            print(f"[Autonomy] SemanticTask -> {task.intent}")

            return task

        if initiative.type == InitiativeType.SUGGEST:

            return SemanticTask(
                intent=Intent.CHAT,
                raw_text=initiative.description,
                goal=initiative.title,
            )

        if initiative.type == InitiativeType.REMIND:

            return SemanticTask(
                intent=Intent.CHAT,
                raw_text=initiative.description,
                goal=initiative.title,
            )

        if initiative.type == InitiativeType.PLAN:

            return SemanticTask(
                intent=Intent.CHAT,
                raw_text=initiative.description,
                goal=initiative.title,
            )

        if initiative.type == InitiativeType.EXECUTE:

            return SemanticTask(
                intent=Intent.CHAT,
                raw_text=initiative.description,
                goal=initiative.title,
            )

        return None