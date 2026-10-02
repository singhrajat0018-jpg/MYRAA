"""
MYRAA AI Provider Interface
"""

from __future__ import annotations

import abc
from typing import Iterator, Any


class AIProvider(abc.ABC):

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    @abc.abstractmethod
    def available(self) -> bool:
        ...

    @abc.abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> str:
        ...

    def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Optional streaming generation.

        Yields chunks of the response as they become available.
        If not implemented, providers should raise NotImplementedError.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support streaming")