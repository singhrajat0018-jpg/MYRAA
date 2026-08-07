from ..providers.provider_response import ProviderResponse
from ..intelligence.knowledge_result import KnowledgeResult


class KnowledgeSynthesizer:

    def synthesize(
        self,
        results: list[ProviderResponse],
    ) -> KnowledgeResult:

        if not results:

            return KnowledgeResult(
                success=False,
                answer="No knowledge found.",
            )

        best = max(
            results,
            key=lambda x: len(x.sources),
        )

        confidence = 0.0

        if best.sources:

            confidence = (
                sum(
                    s.confidence
                    for s in best.sources
                )
                / len(best.sources)
            )

        return KnowledgeResult(
            success=True,
            answer=best.answer,
            confidence=confidence,
            sources=best.sources,
            provider=best.provider,
            metadata=best.metadata,
        )