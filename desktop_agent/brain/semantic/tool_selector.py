"""
MYRAA Tool Selection Engine

Validates and corrects tool selections produced by the LLM
before they reach the planner.
"""

from __future__ import annotations

import os

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

        print("=" * 60)
        print("ToolSelector running")
        print(task.metadata)
        print("=" * 60)

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

                print("Requested App :", name)
                print("Resolved Alias:", alias)

                if alias is not None:
                    params["name"] = alias

        # -------------------------------------------------
        # openFile vs readFile correction
        # -------------------------------------------------

        if action == "readFile":
            print("Converting readFile -> openFile")
            path = params.get("path")

            if isinstance(path, str):

                _, ext = os.path.splitext(path)

                if ext.lower() in cls.FILE_EXTENSIONS:

                    text = task.raw_text.lower()

                    if text.startswith("open "):

                        task.metadata["action"] = "openFile"

        task.metadata["parameters"] = params

        return task