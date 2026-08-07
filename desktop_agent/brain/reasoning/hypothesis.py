from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Hypothesis:

    title: str

    confidence: float

    explanation: str