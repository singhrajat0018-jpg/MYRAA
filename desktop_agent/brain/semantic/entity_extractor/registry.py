"""
Entity Extractor Registry

Routes extraction requests
to the correct extractor.
"""

from __future__ import annotations

from typing import Dict, List

from ..semantic_models import (
    Entity,
    Intent,
    SemanticContext,
)

from .base import BaseEntityExtractor

from .message import MessageEntityExtractor
from .browser import BrowserEntityExtractor
from .file import FileEntityExtractor
from .windows import WindowsEntityExtractor
from .system import SystemEntityExtractor


class EntityExtractor:
    """
    Central registry.

    SemanticParser only talks to this class.
    """

    def __init__(self):

        self.extractors: List[BaseEntityExtractor] = [

            MessageEntityExtractor(),

            BrowserEntityExtractor(),

            FileEntityExtractor(),

            WindowsEntityExtractor(),

            SystemEntityExtractor(),
        ]

        self.intent_map: Dict[Intent, BaseEntityExtractor] = {}

        for extractor in self.extractors:

            for intent in extractor.supported_intents:

                self.intent_map[intent] = extractor

    # ----------------------------------------------------

    def extract(
        self,
        text: str,
        intent: Intent,
        context: SemanticContext,
    ) -> List[Entity]:

        extractor = self.intent_map.get(intent)

        if extractor is None:
            return []

        return extractor.extract(
            text=text,
            intent=intent,
            context=context,
        )