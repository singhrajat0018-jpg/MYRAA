from __future__ import annotations

from enum import Enum, auto


class Route(Enum):

    LOCAL = auto()

    KNOWLEDGE = auto()

    SEARCH = auto()

    VISION = auto()

    LLM = auto()