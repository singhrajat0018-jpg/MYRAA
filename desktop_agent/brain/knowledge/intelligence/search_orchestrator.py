from __future__ import annotations

from ..providers.provider_manager import ProviderManager
from .knowledge_request import KnowledgeRequest
from .knowledge_result import KnowledgeResult


class SearchOrchestrator:
    """
    Executes search requests using one or more providers.
    """

    def __init__(
        self,
        provider_manager: ProviderManager,
    ):

        self.provider_manager = provider_manager

    def search(
        self,
        request: KnowledgeRequest,
    ) -> list[KnowledgeResult]:

        provider_names = ["web"]

        providers = self.provider_manager.providers_for(
            provider_names
        )

        results = []

        for provider in providers:

            if not provider.supports(request):
                continue

            try:

                provider_result = provider.search(
                    request,
                )

                if provider_result.success:

                    results.append(
                        provider_result
                    )

            except Exception:

                continue

        return results