"""
Semantic → Generic Action Mapper

Converts SemanticTask into executable generic actions.
"""

from __future__ import annotations

from .semantic_models import (
    SemanticTask,
    Intent,
    EntityType,
)


class SemanticActionMapper:

    @staticmethod
    def populate(task: SemanticTask) -> SemanticTask:

        # Already mapped (function-call path)
        if "action" in task.metadata:
            return task

        action = None
        parameters = {}

        # --------------------------------------------------
        # Open Application
        # --------------------------------------------------

        if task.intent == Intent.OPEN_APPLICATION:

            if task.has_entity(EntityType.FILE):
                action = "openFile"
                parameters = {
                    "path": task.get_entity(EntityType.FILE)
                }

            elif task.has_entity(EntityType.FOLDER):
                action = "openFolder"
                parameters = {
                    "name": task.get_entity(EntityType.FOLDER)
                }

            elif task.has_entity(EntityType.URL):
                action = "openWebsite"
                parameters = {
                    "url": task.get_entity(EntityType.URL)
                }

            elif task.has_entity(EntityType.WEBSITE):
                action = "openWebsite"
                parameters = {
                    "url": task.get_entity(EntityType.WEBSITE)
                }

            elif task.has_entity(EntityType.APPLICATION):
                action = "openApplication"
                parameters = {
                    "name": task.get_entity(EntityType.APPLICATION)
                }

        # --------------------------------------------------
        # Create File
        # --------------------------------------------------

        elif task.intent == Intent.CREATE_FILE:

            action = "createFile"

        # --------------------------------------------------
        # Create Folder
        # --------------------------------------------------

        elif task.intent == Intent.CREATE_FOLDER:

            action = "createFolder"

        elif task.intent == Intent.OPEN_WEBSITE:

            action = "openWebsite"

            if task.has_entity(EntityType.URL):
                parameters = {
                    "url": task.get_entity(EntityType.URL)
                }

            elif task.has_entity(EntityType.WEBSITE):
                parameters = {
                    "url": task.get_entity(EntityType.WEBSITE)
                }

            elif "url" in task.metadata:
                parameters = {
                    "url": task.metadata["url"]
                }

        # --------------------------------------------------
        # Search Web
        # --------------------------------------------------

        elif task.intent == Intent.SEARCH_WEB:

            action = "searchWeb"

            # Prefer SEARCH_QUERY entity
            if task.has_entity(EntityType.SEARCH_QUERY):
                parameters = {
                    "query": task.get_entity(EntityType.SEARCH_QUERY)
                }

            # Fallback for providers that store URL in metadata
            elif "url" in task.metadata:
                parameters = {
                    "query": task.metadata["url"]
                }

        # --------------------------------------------------

        if action is not None:
            task.metadata["action"] = action
            task.metadata["parameters"] = parameters

        return task