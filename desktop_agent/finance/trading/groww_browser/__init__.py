"""Groww Browser-First Integration — browser-based Groww web interaction.

Reads the Groww web interface through the user's Windows default browser,
observed via vision/OCR through UniversalController (MYRAA owns no browser
engine — no Playwright/Puppeteer/Selenium). READ-ONLY — never executes trades.

Architecture:
Groww Web (default browser) → Screen Observation (vision/OCR) →
Trading Models → Analysis → Advice
"""
from __future__ import annotations

from .groww_browser_bridge import GrowwBrowserBridge
from .groww_data_extractor import (
    GrowwDataExtractor,
    ExtractedHolding,
    ExtractedPosition,
    ExtractedOrder,
    GrowwPageState,
)
from .groww_action_blocker import TradingAdvisorPolicy, BlockedAction
from .groww_session import GrowwSessionManager, SessionState

__all__ = [
    "GrowwBrowserBridge",
    "GrowwDataExtractor",
    "ExtractedHolding",
    "ExtractedPosition",
    "ExtractedOrder",
    "GrowwPageState",
    "TradingAdvisorPolicy",
    "BlockedAction",
    "GrowwSessionManager",
    "SessionState",
]
