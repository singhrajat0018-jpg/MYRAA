from __future__ import annotations

from .knowledge_request import KnowledgeRequest


class KnowledgeRouter:
    """
    Decides where knowledge should come from.

    It can route requests to:

    - Internal Knowledge
    - External Providers
    - Hybrid
    """

    def route(
        self,
        request: KnowledgeRequest,
    ) -> str:

        if request.realtime:
            return "external"

        return "internal"