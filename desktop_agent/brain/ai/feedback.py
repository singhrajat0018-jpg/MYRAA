"""AI Manager 4.1 — controlled feedback / learning pipeline (Phase 9).

Captures routing feedback records for OFFLINE recalibration. The AI Manager
NEVER rewrites its own routing rules in production based on this data; the
records are simply retained (in-memory, optionally exported to JSON) so an
offline pipeline can later recalibrate / retrain.

Fields follow the RoutingFeedback contract: request_id, route, confidence,
outcome, verification, user_feedback, correction, failure_category, timestamp.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


@dataclass
class RoutingFeedback:
    """A single routing feedback record (offline learning only)."""

    request_id: str
    route: Dict[str, Any]
    confidence: float
    outcome: Optional[str] = None
    verification: Optional[str] = None
    user_feedback: Optional[str] = None
    correction: Optional[str] = None
    failure_category: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "route": self.route,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "verification": self.verification,
            "user_feedback": self.user_feedback,
            "correction": self.correction,
            "failure_category": self.failure_category,
            "timestamp": self.timestamp,
        }


class FeedbackStore:
    """Bounded in-memory store of RoutingFeedback records (offline only)."""

    def __init__(self, maxlen: int = 500) -> None:
        self._records: Deque[RoutingFeedback] = deque(maxlen=maxlen)

    def record(self, feedback: RoutingFeedback) -> None:
        self._records.append(feedback)

    def history(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records]

    def count(self) -> int:
        return len(self._records)

    def export(self, path: str) -> int:
        """Serialize all records to JSON (best-effort). Returns record count."""
        import json
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.history(), fh, indent=2)
        return self.count()