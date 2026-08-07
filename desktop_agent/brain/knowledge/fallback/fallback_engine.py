from .fallback_chain import FallbackChain


class FallbackEngine:

    def __init__(self):

        self._chains = {}

    def register(
        self,
        chain: FallbackChain,
    ):

        self._chains[
            chain.primary
        ] = chain

    def fallback_for(
        self,
        provider: str,
    ) -> list[str]:

        chain = self._chains.get(provider)

        if chain is None:

            return []

        return chain.alternatives