from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..vision_context import VisionContext

if TYPE_CHECKING:
    from ..screen_analyzer import ScreenSummary


class BaseAnalyzer(ABC):

    @abstractmethod
    def can_handle(
        self,
        vision: VisionContext,
    ) -> bool:
        ...

    @abstractmethod
    def analyze(
        self,
        vision: VisionContext,
        summary: "ScreenSummary",
    ) -> "ScreenSummary":
        ...