from __future__ import annotations


class ProviderSelector:

    """
    Chooses which LLM should answer.
    """

    def select(
        self,
        semantic_task,
    ) -> str:

        text = semantic_task.raw_text.lower()

        if any(

            word in text

            for word in (

                "code",

                "python",

                "explain",

                "why",

                "how",

            )

        ):

            return "gemini"

        return "ollama"