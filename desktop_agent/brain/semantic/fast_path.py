from __future__ import annotations

from .semantic_models import Intent


FAST_INTENTS = {

    Intent.OPEN_APPLICATION,

    Intent.CLOSE_APPLICATION,

    Intent.OPEN_WEBSITE,

    Intent.CREATE_FILE,

    Intent.CREATE_FOLDER,

    Intent.DELETE_FILE,

    Intent.COPY_FILE,

    Intent.MOVE_FILE,

    Intent.SEARCH_WEB,

}


class FastPath:

    """
    Determines whether a SemanticTask
    can completely bypass the LLM.
    """

    @staticmethod
    def should_skip_llm(task) -> bool:

        if task is None:
            return False

        return task.intent in FAST_INTENTS