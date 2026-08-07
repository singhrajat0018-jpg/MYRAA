"""
Speech data models for MYRAA.

This module contains lightweight dataclasses shared by the
speech recognition pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class AudioChunk:
    """
    One PCM audio chunk received from the frontend.
    """

    pcm: bytes
    sample_rate: int = 16000
    channels: int = 1
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class Transcript:
    """
    Final speech recognition result.
    """

    text: str
    confidence: float = 1.0
    language: str = "auto"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration: Optional[float] = None