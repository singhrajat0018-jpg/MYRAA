"""AgentTelemetry — observability for MYRAA agent execution.

Tracks: agent_started, agent_completed, agent_failed, agent_handoff,
agent_retry, agent_cancelled, agent_timeout, agent_escalated.
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """Single agent execution event."""
    event_type: str  # agent_started, agent_completed, agent_failed, etc.
    agent_id: str
    task_id: str
    skill_id: str = ""
    latency_ms: float = 0.0
    status: str = ""
    result_summary: str = ""
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "skill_id": self.skill_id,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "result_summary": self.result_summary,
            "errors": self.errors,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class AgentTelemetry:
    """Ring-buffered agent event telemetry.

    Tracks: events, counts, latencies, errors.
    Does NOT persist raw events forever.
    """

    def __init__(self, max_events: int = 500) -> None:
        self._max_events = max_events
        self._events: List[AgentEvent] = []
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._latencies: Dict[str, List[float]] = {}

    def record(self, event: AgentEvent) -> None:
        """Record an agent event."""
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

            # Update counters
            key = f"{event.event_type}:{event.skill_id}"
            self._counters[key] = self._counters.get(key, 0) + 1

            # Update latencies
            if event.latency_ms > 0:
                if event.skill_id not in self._latencies:
                    self._latencies[event.skill_id] = []
                self._latencies[event.skill_id].append(event.latency_ms)
                if len(self._latencies[event.skill_id]) > 100:
                    self._latencies[event.skill_id] = self._latencies[event.skill_id][-100:]

    def record_started(self, agent_id: str, task_id: str, skill_id: str = "") -> None:
        self.record(AgentEvent("agent_started", agent_id, task_id, skill_id))

    def record_completed(
        self,
        agent_id: str,
        task_id: str,
        skill_id: str,
        latency_ms: float,
        result_summary: str = "",
    ) -> None:
        self.record(AgentEvent(
            "agent_completed", agent_id, task_id, skill_id,
            latency_ms=latency_ms, status="completed", result_summary=result_summary,
        ))

    def record_failed(
        self,
        agent_id: str,
        task_id: str,
        skill_id: str,
        errors: List[str],
    ) -> None:
        self.record(AgentEvent(
            "agent_failed", agent_id, task_id, skill_id,
            status="failed", errors=errors,
        ))

    def record_handoff(self, from_agent: str, to_agent: str, task_id: str) -> None:
        self.record(AgentEvent(
            "agent_handoff", from_agent, task_id,
            metadata={"to_agent": to_agent},
        ))

    def record_timeout(self, agent_id: str, task_id: str, skill_id: str) -> None:
        self.record(AgentEvent(
            "agent_timeout", agent_id, task_id, skill_id, status="timeout",
        ))

    def record_cancelled(self, agent_id: str, task_id: str) -> None:
        self.record(AgentEvent(
            "agent_cancelled", agent_id, task_id, status="cancelled",
        ))

    def record_escalated(self, agent_id: str, task_id: str, reason: str = "") -> None:
        self.record(AgentEvent(
            "agent_escalated", agent_id, task_id, status="escalated",
            metadata={"reason": reason},
        ))

    def recent(self, n: int = 50) -> List[AgentEvent]:
        with self._lock:
            return list(self._events[-n:])

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            events = list(self._events)
            counters = dict(self._counters)
            latencies = dict(self._latencies)

        # Compute latency percentiles
        latency_stats: Dict[str, Dict[str, float]] = {}
        for skill_id, lats in latencies.items():
            if lats:
                sorted_lats = sorted(lats)
                latency_stats[skill_id] = {
                    "p50": sorted_lats[len(sorted_lats) // 2],
                    "p90": sorted_lats[int(len(sorted_lats) * 0.9)],
                    "p99": sorted_lats[int(len(sorted_lats) * 0.99)],
                    "count": len(lats),
                }

        return {
            "total_events": len(events),
            "counters": counters,
            "latency_stats": latency_stats,
            "event_types": list(set(e.event_type for e in events)),
        }

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._counters.clear()
            self._latencies.clear()
