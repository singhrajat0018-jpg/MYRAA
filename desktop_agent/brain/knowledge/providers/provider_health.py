class ProviderHealth:

    def __init__(self):

        self._status = {}

    def mark_online(
        self,
        provider: str,
    ):

        self._status[provider] = True

    def mark_offline(
        self,
        provider: str,
    ):

        self._status[provider] = False

    def is_online(
        self,
        provider: str,
    ):

        return self._status.get(provider, True)