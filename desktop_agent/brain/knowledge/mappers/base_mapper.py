from abc import ABC
from abc import abstractmethod

from ..providers.provider_response import ProviderResponse


class BaseMapper(ABC):

    @abstractmethod
    def map(
        self,
        response,
    ) -> ProviderResponse:
        ...