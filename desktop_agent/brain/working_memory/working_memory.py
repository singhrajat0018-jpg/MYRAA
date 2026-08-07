"""
MYRAA Working Memory

Maintains the assistant's short-term cognitive state.
"""

from __future__ import annotations
from .execution_memory import ExecutionRecord
from datetime import datetime
import copy
from .memory_types import (
    WorkingSnapshot,
)

from ..semantic.semantic_models import (
    SemanticTask,
    EntityType,
)


class WorkingMemory:

    def __init__(self):

        self.snapshot = WorkingSnapshot()
        self.max_history = 20
    # ----------------------------------------------------

    # Conversation

    # ----------------------------------------------------

    def update_conversation(

        self,

        user_message: str,

        ai_message: str = "",

    ):

        conv = self.snapshot.conversation

        conv.last_user_message = user_message

        conv.last_ai_message = ai_message

        conv.turn_count += 1

        self.snapshot.updated_at = datetime.utcnow()

    # ----------------------------------------------------

    # Entities

    # ----------------------------------------------------

    def update_entity(

        self,

        *,

        application=None,

        file=None,

        folder=None,

        website=None,

        person=None,

    ):

        entity = self.snapshot.entities

        if application:

            entity.current_application = application

        entity.recent_entities.append(application)

        if len(entity.recent_entities) > self.max_history:
            entity.recent_entities.pop(0)

        if file:

            entity.current_file = file

            entity.recent_entities.append(file)

            if len(entity.recent_entities) > self.max_history:
                entity.recent_entities.pop(0)

        if folder:

            entity.current_folder = folder

            entity.recent_entities.append(folder)
            if len(entity.recent_entities) > self.max_history:
                entity.recent_entities.pop(0)

        if website:

            entity.current_website = website

            entity.recent_entities.append(website)
            if len(entity.recent_entities) > self.max_history:
                 entity.recent_entities.pop(0)

        if person:

            entity.current_person = person

            entity.recent_entities.append(person)
            if len(entity.recent_entities) > self.max_history:
                entity.recent_entities.pop(0)


        self.snapshot.updated_at = datetime.utcnow()

    # ----------------------------------------------------

    # Actions

    # ----------------------------------------------------

    def update_action(

        self,

        action: str,

        tool: str,

        result: str,

    ):

        mem = self.snapshot.actions

        mem.last_action = action

        mem.last_tool = tool

        mem.last_result = result

        mem.recent_actions.append(action)

        if len(mem.recent_actions) > self.max_history:
            mem.recent_actions.pop(0)

        self.snapshot.updated_at = datetime.utcnow()

    # ----------------------------------------------------

    # Tasks

    # ----------------------------------------------------

    def update_task(

        self,

        goal=None,

        task=None,

    ):

        mem = self.snapshot.tasks

        if goal:

            mem.current_goal = goal

        if task:

            mem.current_task = task

        self.snapshot.updated_at = datetime.utcnow()

    def remember_event(self, event) -> None:
        """
        Store an observer event in working memory.
        """

        mem = self.snapshot.events

        mem.last_event_source = getattr(event, "source", None)
        mem.last_event_title = getattr(event, "title", None)
        mem.last_event_severity = getattr(event, "severity", None)

        mem.recent_events.append(
            {
                "source": getattr(event, "source", None),
                "title": getattr(event, "title", ""),
                "message": getattr(event, "message", ""),
                "severity": getattr(event, "severity", ""),
                "timestamp": getattr(event, "timestamp", None),
                "payload": getattr(event, "payload", {}),
            }
        )

        if len(mem.recent_events) > self.max_history:
            mem.recent_events.pop(0)

        self.snapshot.updated_at = datetime.utcnow()

    def remember_execution(
        self,
        title: str,
        success: bool,
        execution_time: float,
    ):

        record = ExecutionRecord(
            title=title,
            success=success,
            execution_time=execution_time,
        )

        mem = self.snapshot.execution

        mem.last_execution = record

        mem.recent_executions.append(record)

        if len(mem.recent_executions) > self.max_history:
            mem.recent_executions.pop(0)

        if success:
            mem.success_count += 1
        else:
            mem.failure_count += 1

        self.snapshot.updated_at = datetime.utcnow()

    # ----------------------------------------------------

    # Snapshot

    # ----------------------------------------------------

    def get_snapshot(self):
        """
        Return a safe copy of working memory.
        Prevent external code from modifying internal state.
        """
        return copy.deepcopy(self.snapshot)

    # ----------------------------------------------------

    # Reset

    # ----------------------------------------------------

    def clear(self):

        self.snapshot = WorkingSnapshot()

    def remember_entity(self, name: str, value: str):

        if not value:
            return

        name = name.lower()

        if name == "application":
            self.update_entity(application=value)

        elif name == "file":
            self.update_entity(file=value)

        elif name == "folder":
            self.update_entity(folder=value)

        elif name == "website":
            self.update_entity(website=value)

        elif name == "person":
            self.update_entity(person=value)


    def current_application(self):
        return self.snapshot.entities.current_application


    def current_file(self):
        return self.snapshot.entities.current_file


    def current_folder(self):
        return self.snapshot.entities.current_folder


    def current_website(self):
        return self.snapshot.entities.current_website

    def current_person(self):
        return self.snapshot.entities.current_person

    def remember_semantic_task(self, task: SemanticTask) -> None:
        """
        Extract important entities from a SemanticTask and
        store them in working memory.
        """

        if task is None:
            return

        mapping = {
            EntityType.APPLICATION: "application",
            EntityType.FILE: "file",
            EntityType.FOLDER: "folder",
            EntityType.WEBSITE: "website",
            EntityType.URL: "website",
            EntityType.PERSON: "person",
        }

        for entity in task.entities:
            kind = mapping.get(entity.entity_type)

            if kind is None:
                continue

            self.remember_entity(
                kind,
                str(entity.value),
            )

    def debug(self):

        return {

            "conversation": self.snapshot.conversation,

            "entities": self.snapshot.entities,

            "actions": self.snapshot.actions,

            "tasks": self.snapshot.tasks,

            "events": self.snapshot.events,

            "execution": self.snapshot.execution,


        }


