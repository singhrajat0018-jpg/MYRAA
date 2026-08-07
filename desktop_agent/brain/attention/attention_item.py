from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AttentionItem:
    """
    Something that deserves MYRAA's attention.
    """

    source: str

    title: str

    priority: float

    payload: Any = None

    created_at: datetime = field(
        default_factory=datetime.utcnow
    )