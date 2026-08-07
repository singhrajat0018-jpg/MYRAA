from .knowledge_request import KnowledgeRequest
from .knowledge_result import KnowledgeResult
from .source_selector import SourceSelector
from ..providers.provider_registry import ProviderRegistry
from ..providers.web_provider import WebProvider

class IntelligenceEngine:
    """
    Entry point of MYRAA's Real-Time Knowledge System.
    """

    def __init__(self):

        self.selector = SourceSelector()

        self.registry = ProviderRegistry()

        self.registry.register(
            WebProvider()
        )

    def process(
        self,
        request: KnowledgeRequest,
    ) -> KnowledgeResult:

        provider_names = self.selector.select(request)

        for provider_name in provider_names:

            provider = self.registry.get(provider_name)

            if provider is None:
                continue

            if not provider.supports(request):
                continue

            return provider.search(request)

        return KnowledgeResult(
            success=False,
            answer="No suitable provider found.",
            confidence=0.0,
        )