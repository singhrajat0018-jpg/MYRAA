"""
Generic Screen Analyzer
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseAnalyzer
from ..vision_context import VisionContext

if TYPE_CHECKING:
    from ..screen_analyzer import ScreenSummary


class GenericAnalyzer(BaseAnalyzer):

    def can_handle(
        self,
        vision: VisionContext,
    ) -> bool:

        return True

    def analyze(
        self,
        vision: VisionContext,
        summary: "ScreenSummary",
    ) -> "ScreenSummary":

        return summary