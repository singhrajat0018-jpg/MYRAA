"""
Task objects used by Planner and Orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import TaskStatus, SafetyLevel, ToolAction


@dataclass
class Task:

    id: str

    title: str

    description: str = ""

    action: Optional[ToolAction] = None

    depends_on: List[str] = field(default_factory=list)

    status: TaskStatus = TaskStatus.PENDING

    safety: SafetyLevel = SafetyLevel.SAFE

    confidence: float = 1.0

    retries: int = 0

    metadata: Dict = field(default_factory=dict)

    error: Optional[str] = None

    def ready(self, completed: List[str]) -> bool:
        """
        Check if all dependencies are completed.
        """
        return all(dep in completed for dep in self.depends_on)

    def start(self):
        self.status = TaskStatus.RUNNING

    def complete(self):
        self.status = TaskStatus.SUCCESS

    def fail(self, message: str):
        self.status = TaskStatus.FAILED
        self.error = message


class TaskGraph:
    """
    Ordered collection of executable tasks.
    """

    def __init__(self):
        self.tasks: List[Task] = []

    def add(self, task: Task):
        self.tasks.append(task)

    def pending(self):

        return [
            t
            for t in self.tasks
            if t.status == TaskStatus.PENDING
        ]

    def completed(self):

        return [
            t.id
            for t in self.tasks
            if t.status == TaskStatus.SUCCESS
        ]

    def next_ready(self):

        completed = self.completed()

        for task in self.pending():

            if task.ready(completed):

                return task

        return None

    def finished(self):

        return all(

            t.status in

            (TaskStatus.SUCCESS,
             TaskStatus.SKIPPED)

            for t in self.tasks

        )

    def failed(self):

        return any(

            t.status == TaskStatus.FAILED

            for t in self.tasks

        )