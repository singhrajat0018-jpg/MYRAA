from __future__ import annotations


class LLMPolicy:

    """
    Decides whether an LLM is required.
    """

    def requires_llm(
        self,
        semantic_task,
    ) -> bool:

        action = semantic_task.metadata.get("action")

        if action:

            return False

        if semantic_task.intent.name in {

            "OPEN_APPLICATION",

            "CLOSE_APPLICATION",

            "OPEN_FILE",

            "OPEN_FOLDER",

            "CREATE_FILE",

            "DELETE_FILE",

            "MOVE_FILE",

            "COPY_FILE",

            "SEARCH_WEB",

            "OPEN_WEBSITE",

            "SET_VOLUME",

            "SET_BRIGHTNESS",

        }:

            return False

        return True