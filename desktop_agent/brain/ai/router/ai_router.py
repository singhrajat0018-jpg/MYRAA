from __future__ import annotations

from .llm_policy import LLMPolicy
from .provider_selector import ProviderSelector
from .routing_rules import Route


class AIRouter:

    """
    Central routing layer.

    Brain never talks directly
    to Gemini/Ollama anymore.
    """

    def __init__(self):

        self.policy = LLMPolicy()

        self.selector = ProviderSelector()

    def route(

        self,

        semantic_task,

    ):

        action = semantic_task.metadata.get("action")

        if action:

            return Route.LOCAL

        if not self.policy.requires_llm(

            semantic_task,

        ):

            return Route.LOCAL

        return Route.LLM

    def provider(

        self,

        semantic_task,

    ):

        return self.selector.select(

            semantic_task,

        )