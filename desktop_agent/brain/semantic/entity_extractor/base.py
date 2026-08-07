"""
MYRAA Cognitive Engine
Entity Extractor Base

Every entity extractor inherits from this class.

Responsibility:
---------------
Extract semantic entities from user input.

This module NEVER:

- Executes tools
- Plans tasks
- Makes decisions

It only extracts structured semantic information.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..semantic_models import (
    Entity,
    Intent,
    SemanticContext,
)


class BaseEntityExtractor(ABC):
    """
    Base interface for all entity extractors.
    """

    @property
    @abstractmethod
    def supported_intents(self) -> List[Intent]:
        """
        Intents handled by this extractor.
        """
        raise NotImplementedError

    @abstractmethod
    def extract(
        self,
        text: str,
        intent: Intent,
        context: SemanticContext,
    ) -> List[Entity]:
        """
        Extract semantic entities.

        Returns
        -------
        List[Entity]
        """
        raise NotImplementedError