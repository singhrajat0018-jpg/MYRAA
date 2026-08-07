from __future__ import annotations

from .resolution_result import ResolutionResult


class KnowledgeResolver:

    def __init__(self, knowledge_manager):

        self.knowledge = knowledge_manager

    # --------------------------------------------------

    def resolve(self, query: str) -> ResolutionResult:

        print("[KR] resolve() entered")

        print("[KR] query =", query)

        print("[KR] knowledge =", self.knowledge)

        results = self.knowledge.find_project(query)

        print("[KR] results =", results)

        if not results:

            print("[KR] no results")

            return ResolutionResult()

        best = results[0]

        print("[KR] best =", best)

        return ResolutionResult(
            resolved=True,
            confidence=best.score,
            project=best.title,
            path=best.path,
        )