"""
Semantic → Generic Action Mapper

Converts SemanticTask into executable generic actions.
"""

from __future__ import annotations

import re

from .semantic_models import (
    SemanticTask,
    Intent,
    EntityType,
)


def _site_named_in(text: str):
    """Resolve a website named in ``text`` through the ONE website resolver.

    The alias table lives only in ``desktop_agent.tools_websites``; this module
    keeps no copy of it.
    """
    if not text:
        return None
    try:
        from desktop_agent.tools_websites import SITE_URLS, resolve_site
    except Exception:  # pragma: no cover - import guard
        return None
    lowered = str(text).lower()
    for alias in SITE_URLS:
        # Single-letter aliases ("x") are too easy to hit by accident.
        if len(alias) < 2:
            continue
        if re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", lowered):
            return resolve_site(alias)
    return resolve_site(str(text))


def _site_from_task(task: SemanticTask):
    """Website named by the task (entity first, then the spoken text)."""
    for entity_type in (EntityType.APPLICATION, EntityType.URL, EntityType.WEBSITE):
        value = task.get_entity(entity_type)
        if value:
            resolved = _site_named_in(str(value))
            if resolved:
                return resolved
    if task.has_entity(EntityType.FILE) or task.has_entity(EntityType.FOLDER):
        return None
    return _site_named_in(task.normalized_text) or _site_named_in(task.raw_text)


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

            # "open gmail" / "open netflix": the intent classifier saw "open X"
            # and no entity extractor fired, but the name IS a website. Resolve
            # it through the ONE website resolver so the request reaches the URL
            # opener instead of being dropped with no action.
            site_url = _site_from_task(task)

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

            elif site_url:
                action = "openWebsite"
                parameters = {
                    "url": site_url
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