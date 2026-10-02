"""
MYRAA Tool Selection Engine

Validates and corrects tool selections produced by the LLM
before they reach the planner.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

from .semantic_models import SemanticTask


class ToolSelector:

    FILE_EXTENSIONS = {
        ".txt", ".pdf", ".doc", ".docx",
        ".xlsx", ".xls",
        ".ppt", ".pptx",
        ".png", ".jpg", ".jpeg",
        ".gif", ".bmp",
        ".py", ".js", ".ts",
        ".json", ".csv",
        ".zip", ".rar",
        ".mp3", ".mp4",
    }

    APP_ALIASES = {

        "notepad.exe": "Notepad",
        "chrome.exe": "Google Chrome",
        "msedge.exe": "Microsoft Edge",
        "code.exe": "Visual Studio Code",
        "explorer.exe": "File Explorer",

    }

    @classmethod
    def process(cls, task: SemanticTask) -> SemanticTask:

        log.debug("ToolSelector running")
        log.debug("Task metadata: %s", task.metadata)

        action = task.metadata.get("action")
        params = task.metadata.get("parameters", {})

        if not action:
            return task

        # -------------------------------------------------
        # Normalize application aliases
        # -------------------------------------------------

        if action == "openApplication":

            name = params.get("name")

            if isinstance(name, str):

                alias = cls.APP_ALIASES.get(name.lower())

                log.debug("Requested App: %s", name)
                log.debug("Resolved Alias: %s", alias)

                if alias is not None:
                    params["name"] = alias

        # -------------------------------------------------
        # openFile vs readFile correction
        # -------------------------------------------------

        if action == "readFile":
            log.debug("Converting readFile -> openFile")
            path = params.get("path")

            if isinstance(path, str):

                _, ext = os.path.splitext(path)

                if ext.lower() in cls.FILE_EXTENSIONS:

                    text = task.raw_text.lower()

                    if text.startswith("open "):

                        task.metadata["action"] = "openFile"

        task.metadata["parameters"] = params

        return task