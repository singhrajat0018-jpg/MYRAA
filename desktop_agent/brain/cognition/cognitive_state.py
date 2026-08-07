from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class CognitiveState:

    last_event_key: str | None = None

    last_notification: datetime | None = None

    last_plan: datetime | None = None

    notification_count: int = 0

    plan_count: int = 0

    created_at: datetime = field(
        default_factory=datetime.utcnow
    )