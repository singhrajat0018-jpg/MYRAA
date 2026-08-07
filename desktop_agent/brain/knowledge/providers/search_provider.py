from abc import ABC
from abc import abstractmethod

from .base_provider import BaseKnowledgeProvider
from ..providers.provider_response import ProviderResponse


class SearchProvider(
    BaseKnowledgeProvider,
    ABC,
):

    @abstractmethod
    def search(
        self,
        request,
    ) -> ProviderResponse:
        ...