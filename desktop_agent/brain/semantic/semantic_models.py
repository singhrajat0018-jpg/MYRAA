"""
MYRAA Cognitive Engine (MCE)
Semantic Models

These models define MYRAA's cognitive understanding.
They represent WHAT the user means, not HOW to execute it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


# ==========================================================
# Intent
# ==========================================================

class Intent(str, Enum):
    UNKNOWN = "unknown"

    CHAT = "chat"

    QUESTION = "question"

    OPEN_APPLICATION = "open_application"
    CLOSE_APPLICATION = "close_application"

    SEARCH_WEB = "search_web"

    OPEN_WEBSITE = "open_website"

    SEND_MESSAGE = "send_message"
    SEND_EMAIL = "send_email"

    CREATE_FILE = "create_file"
    CREATE_FOLDER = "create_folder"

    DELETE_FILE = "delete_file"
    MOVE_FILE = "move_file"
    COPY_FILE = "copy_file"

    SYSTEM_CONTROL = "system_control"

    PLAY_MEDIA = "play_media"
    STOP_MEDIA = "stop_media"

    AUTOMATION = "automation"

    CODE_TASK = "code_task"

    VISION = "vision"

    MULTI_STEP_TASK = "multi_step_task"

    SET_GOAL = "set_goal"

    GET_GOAL = "get_goal"
    
    CLEAR_GOAL = "clear_goal"

    ROUTER_ACTION = "router_action"
# ==========================================================
# Entity Types
# ==========================================================

class EntityType(str, Enum):

    APPLICATION = "application"

    PERSON = "person"

    CONTACT = "contact"

    FILE = "file"

    FOLDER = "folder"

    URL = "url"

    WEBSITE = "website"

    SEARCH_QUERY = "search_query"

    MESSAGE = "message"

    EMAIL = "email"

    PHONE = "phone"

    DATE = "date"

    TIME = "time"

    PLATFORM = "platform"

    WINDOW = "window"

    PROCESS = "process"

    LOCATION = "location"

    PROJECT = "project"

    CLIPBOARD = "clipboard"

    UNKNOWN = "unknown"


# ==========================================================
# Priority
# ==========================================================

class Priority(str, Enum):

    LOW = "low"

    NORMAL = "normal"

    HIGH = "high"

    CRITICAL = "critical"


# ==========================================================
# Confirmation
# ==========================================================

class ConfirmationPolicy(str, Enum):

    NEVER = "never"

    IF_REQUIRED = "if_required"

    ALWAYS = "always"


# ==========================================================
# Entity
# ==========================================================

@dataclass(slots=True)
class Entity:

    entity_type: EntityType

    value: Any

    confidence: float = 1.0

    metadata: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Semantic Context
# ==========================================================

@dataclass(slots=True)
class SemanticContext:

    language: str = "unknown"

    active_app: Optional[str] = None

    active_window: Optional[str] = None

    clipboard: Optional[str] = None

    conversation_id: Optional[str] = None

    previous_intent: Optional[Intent] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Semantic Task
# ==========================================================

@dataclass(slots=True)
class SemanticTask:

    task_id: str = field(default_factory=lambda: str(uuid4()))

    raw_text: str = ""

    normalized_text: str = ""

    language: str = "unknown"

    intent: Intent = Intent.UNKNOWN

    entities: List[Entity] = field(default_factory=list)

    confidence: float = 0.0

    priority: Priority = Priority.NORMAL

    confirmation: ConfirmationPolicy = ConfirmationPolicy.IF_REQUIRED

    context: Optional[SemanticContext] = None

    reasoning: List[str] = field(default_factory=list)

    goal: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=datetime.utcnow)

    # ------------------------------------------------------

    def add_entity(
        self,
        entity_type: EntityType,
        value: Any,
        confidence: float = 1.0,
        **metadata,
    ) -> None:

        self.entities.append(
            Entity(
                entity_type=entity_type,
                value=value,
                confidence=confidence,
                metadata=metadata,
            )
        )

    # ------------------------------------------------------

    def get_entity(
        self,
        entity_type: EntityType,
    ) -> Optional[Any]:

        for entity in self.entities:

            if entity.entity_type == entity_type:

                return entity.value

        return None

    # ------------------------------------------------------

    def get_entities(
        self,
        entity_type: EntityType,
    ) -> List[Any]:

        return [

            entity.value

            for entity in self.entities

            if entity.entity_type == entity_type

        ]

    # ------------------------------------------------------

    def has_entity(
        self,
        entity_type: EntityType,
    ) -> bool:

        return self.get_entity(entity_type) is not None

    # ------------------------------------------------------

    @property
    def is_confident(self) -> bool:

        return self.confidence >= 0.75



    def remember_semantic_task(self, task: SemanticTask) -> None:
        """
        Store semantic entities from the latest user request into
        working memory.
        """

        mapping = {
            EntityType.APPLICATION: ("application", task.get_entity(EntityType.APPLICATION)),
            EntityType.FILE: ("file", task.get_entity(EntityType.FILE)),
            EntityType.FOLDER: ("folder", task.get_entity(EntityType.FOLDER)),
            EntityType.WEBSITE: ("website", task.get_entity(EntityType.WEBSITE)),
            EntityType.URL: ("website", task.get_entity(EntityType.URL)),
            EntityType.PERSON: ("person", task.get_entity(EntityType.PERSON)),
        }

        for _, (kind, value) in mapping.items():
            if value is not None:
                self.remember_entity(kind, str(value))