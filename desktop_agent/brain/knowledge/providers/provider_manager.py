from .provider_registry import ProviderRegistry


class ProviderManager:

    def __init__(self):

        self.registry = ProviderRegistry()

    def providers_for(
        self,
        names: list[str],
    ):

        providers = []

        for name in names:

            provider = self.registry.get(name)

            if provider:

                providers.append(provider)

        return providers