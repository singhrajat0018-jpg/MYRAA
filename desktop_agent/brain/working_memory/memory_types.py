"""
Working Memory Data Models.

These dataclasses represent MYRAA's short-term cognitive state.
"""

from __future__ import annotations
from .execution_memory import ExecutionMemory
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(slots=True)
class ConversationMemory:
    last_user_message: str = ""
    last_ai_message: str = ""
    turn_count: int = 0


@dataclass(slots=True)
class EntityMemory:
    current_application: Optional[str] = None
    current_file: Optional[str] = None
    current_folder: Optional[str] = None
    current_website: Optional[str] = None
    current_person: Optional[str] = None

    recent_entities: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ActionMemory:
    last_action: Optional[str] = None
    last_tool: Optional[str] = None
    last_result: Optional[str] = None

    recent_actions: List[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskMemory:
    current_goal: Optional[str] = None
    current_task: Optional[str] = None

    pending_tasks: List[str] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)

@dataclass(slots=True)
class EventMemory:
    """
    Background events observed by MYRAA.

    Examples:
    - Battery low
    - Internet disconnected
    - Stock alert
    - Weather warning
    """

    last_event_source: Optional[str] = None
    last_event_title: Optional[str] = None
    last_event_severity: Optional[str] = None

    recent_events: List[dict] = field(default_factory=list)


@dataclass(slots=True)
class WorkingSnapshot:

    conversation: ConversationMemory = field(
        default_factory=ConversationMemory
    )

    entities: EntityMemory = field(
        default_factory=EntityMemory
    )

    actions: ActionMemory = field(
        default_factory=ActionMemory
    )

    tasks: TaskMemory = field(
        default_factory=TaskMemory
    )

    updated_at: datetime = field(
        default_factory=datetime.utcnow
    )

    events: EventMemory = field(
        default_factory=EventMemory
    )

    execution: ExecutionMemory = field(
        default_factory=ExecutionMemory
    )