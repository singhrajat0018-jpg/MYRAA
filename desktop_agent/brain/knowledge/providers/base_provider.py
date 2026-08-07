from __future__ import annotations

from abc import ABC, abstractmethod

from ..intelligence.knowledge_request import KnowledgeRequest
from ..intelligence.knowledge_result import KnowledgeResult


class BaseKnowledgeProvider(ABC):
    """
    Base class for every external knowledge provider.

    Examples:
        Google
        News
        Weather
        Finance
        GitHub
        Wikipedia
    """

    name: str = "base"

    priority: int = 100

    realtime: bool = True

    @abstractmethod
    def supports(
        self,
        request: KnowledgeRequest,
    ) -> bool:
        """
        Return True if this provider
        can answer the request.
        """
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        request: KnowledgeRequest,
    ) -> KnowledgeResult:
        """
        Execute the request.
        """
        raise NotImplementedError