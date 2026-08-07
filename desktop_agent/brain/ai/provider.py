"""
MYRAA AI Provider Interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AIProvider(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> str:
        ...