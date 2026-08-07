from .knowledge_request import KnowledgeRequest


class SourceSelector:
    """
    Chooses which providers should answer a request.

    Currently rule-based.
    Later it will become AI-driven.
    """

    def select(self, request: KnowledgeRequest) -> list[str]:

        category = request.category.lower()

        if category == "news":
            return ["news"]

        if category == "weather":
            return ["weather"]

        if category == "finance":
            return ["finance"]

        if category == "research":
            return ["research"]

        return ["web"]