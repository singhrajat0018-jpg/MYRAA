from __future__ import annotations

from .base_provider import BaseKnowledgeProvider
from .provider_health import ProviderHealth
from .provider_metrics import ProviderMetrics


class ProviderRegistry:
    """
    Central registry for all Knowledge Providers.

    Responsibilities
    ----------------
    - Register providers
    - Remove providers
    - Lookup providers
    - Track provider health
    - Track provider metrics
    """

    def __init__(self):

        self._providers: dict[str, BaseKnowledgeProvider] = {}

        self.health = ProviderHealth()

        self.metrics: dict[str, ProviderMetrics] = {}

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------

    def register(
        self,
        provider: BaseKnowledgeProvider,
    ) -> None:

        self._providers[provider.name] = provider

        self.health.mark_online(
            provider.name
        )

        self.metrics[provider.name] = (
            ProviderMetrics()
        )

    def unregister(
        self,
        name: str,
    ) -> None:

        self._providers.pop(name, None)

        self.metrics.pop(name, None)

    # ---------------------------------------------------------
    # Lookup
    # ---------------------------------------------------------

    def get(
        self,
        name: str,
    ) -> BaseKnowledgeProvider | None:

        return self._providers.get(name)

    def all(
        self,
    ) -> list[BaseKnowledgeProvider]:

        return list(
            self._providers.values()
        )

    def available(
        self,
    ) -> list[str]:

        return list(
            self._providers.keys()
        )

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    def is_registered(
        self,
        name: str,
    ) -> bool:

        return name in self._providers

    def count(
        self,
    ) -> int:

        return len(
            self._providers
        )