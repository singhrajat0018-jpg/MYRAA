"""
MYRAA Brain

Metrics Collection System

Collects and exposes bounded metrics for performance monitoring and observability.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Any
import logging


logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """A single metric value with timestamp."""
    value: float
    timestamp: float


@dataclass
class CounterMetric:
    """A counter metric that can be incremented."""
    value: int = 0
    last_updated: float = field(default_factory=time.time)


@dataclass
class GaugeMetric:
    """A gauge metric that can be set to a value."""
    value: float = 0.0
    last_updated: float = field(default_factory=time.time)


@dataclass
class HistogramMetric:
    """A histogram metric that tracks distribution of values."""
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_updated: float = field(default_factory=time.time)

    def add_value(self, value: float):
        """Add a value to the histogram."""
        self.values.append(value)
        self.last_updated = time.time()

    def get_percentile(self, percentile: float) -> float:
        """Get a percentile value from the histogram."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_average(self) -> float:
        """Get the average value."""
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)


class MetricsCollector:
    """
    Collects and manages metrics for MYRAA subsystems.

    Metrics are bounded to prevent memory leaks.
    """

    def __init__(self):
        """Initialize the metrics collector."""
        self._lock = threading.RLock()
        self._counters: Dict[str, CounterMetric] = defaultdict(CounterMetric)
        self._gauges: Dict[str, GaugeMetric] = defaultdict(GaugeMetric)
        self._histograms: Dict[str, HistogramMetric] = defaultdict(HistogramMetric)
        self._start_time = time.time()

    # Counter methods
    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        with self._lock:
            counter = self._counters[name]
            counter.value += value
            counter.last_updated = time.time()

    def get_counter(self, name: str) -> int:
        """Get the current value of a counter."""
        with self._lock:
            return self._counters[name].value

    # Gauge methods
    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a value."""
        with self._lock:
            gauge = self._gauges[name]
            gauge.value = value
            gauge.last_updated = time.time()

    def get_gauge(self, name: str) -> float:
        """Get the current value of a gauge."""
        with self._lock:
            return self._gauges[name].value

    # Histogram methods
    def add_to_histogram(self, name: str, value: float) -> None:
        """Add a value to a histogram."""
        with self._lock:
            histogram = self._histograms[name]
            histogram.add_value(value)

    def get_histogram_average(self, name: str) -> float:
        """Get the average value from a histogram."""
        with self._lock:
            return self._histograms[name].get_average()

    def get_histogram_percentile(self, name: str, percentile: float) -> float:
        """Get a percentile value from a histogram."""
        with self._lock:
            return self._histograms[name].get_percentile(percentile)

    # Utility methods
    def get_uptime(self) -> float:
        """Get the uptime of the metrics collector in seconds."""
        return time.time() - self._start_time

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._start_time = time.time()

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        with self._lock:
            result = {
                "uptime_seconds": self.get_uptime(),
                "counters": {name: counter.value for name, counter in self._counters.items()},
                "gauges": {name: gauge.value for name, gauge in self._gauges.items()},
                "histograms": {
                    name: {
                        "average": histogram.get_average(),
                        "count": len(histogram.values),
                        "min": min(histogram.values) if histogram.values else 0.0,
                        "max": max(histogram.values) if histogram.values else 0.0,
                        "p50": histogram.get_percentile(50),
                        "p95": histogram.get_percentile(95),
                        "p99": histogram.get_percentile(99),
                    }
                    for name, histogram in self._histograms.items()
                }
            }
            return result


# Global metrics collector instance
metrics_collector = MetricsCollector()


def increment_action_counter(action_type: str, outcome: str = "total") -> None:
    """Increment an action counter."""
    metrics_collector.increment_counter(f"actions_{action_type}_{outcome}")


def increment_verification_counter(outcome: str = "total") -> None:
    """Increment a verification counter."""
    metrics_collector.increment_counter(f"verifications_{outcome}")


def increment_recovery_counter(strategy: str, outcome: str = "total") -> None:
    """Increment a recovery counter."""
    metrics_collector.increment_counter(f"recovery_{strategy}_{outcome}")


def record_action_latency(action_type: str, latency_seconds: float) -> None:
    """Record action execution latency."""
    metrics_collector.add_to_histogram(f"action_latency_{action_type}", latency_seconds)


def record_verification_latency(latency_seconds: float) -> None:
    """Record verification latency."""
    metrics_collector.add_to_histogram("verification_latency", latency_seconds)


def record_target_resolution_latency(latency_seconds: float) -> None:
    """Record target resolution latency."""
    metrics_collector.add_to_histogram("target_resolution_latency", latency_seconds)


def set_subsystem_health_gauge(subsystem: str, healthy: bool) -> None:
    """Set a gauge for subsystem health (1.0 = healthy, 0.0 = unhealthy)."""
    metrics_collector.set_gauge(f"subsystem_{subsystem}_healthy", 1.0 if healthy else 0.0)


def set_queue_depth_gauge(queue_name: str, depth: int) -> None:
    """Set a gauge for queue depth."""
    metrics_collector.set_gauge(f"queue_depth_{queue_name}", depth)


# ==========================================================
# F8: Telemetry / observability.
#
# Reuses the existing MetricsCollector for counters/histograms/gauges and the
# canonical error_taxonomy redaction helpers, so there is exactly ONE metrics
# system and ONE redaction policy. Telemetry events are bounded (ring buffer)
# and never contain secrets.
# ==========================================================

@dataclass
class TelemetryEvent:
    """One cross-service telemetry event (F8 canonical fields)."""
    request_id: str = ""
    task_id: str = ""
    timestamp: float = field(default_factory=time.time)
    component: str = ""          # node / desktop_agent / brain / provider / tool / verification / recovery
    route: str = ""              # /execute / /brain / /health/ready / /live
    intent: str = ""             # semantic intent
    domain: str = ""             # domain (desktop / research / finance / ...)
    capability: str = ""         # capability used
    execution_mode: str = ""     # direct / cognitive
    reasoning_depth: str = ""    # shallow / deep
    provider: str = ""           # ollama
    model: str = ""              # model name
    tool: str = ""               # tool name
    status: str = "ok"           # ok / error / confirmation / cancelled
    latency_ms: float = 0.0
    verification_status: str = ""
    recovery_attempts: int = 0
    fallback: str = ""           # provider/tool fallback used
    error_category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializable dict with automatic secret redaction."""
        try:
            from .error_taxonomy import redact_value
            return redact_value(asdict(self))
        except Exception:
            return asdict(self)


class TelemetryCollector:
    """Bounded telemetry ring buffer + derived request metrics (F8)."""

    def __init__(self, max_events: int = 500):
        self._lock = threading.RLock()
        self._events: deque = deque(maxlen=max_events)
        self._active_tasks: Dict[str, Dict[str, Any]] = {}

    # --------------------------------------------------------------
    def record(self, **fields: Any) -> TelemetryEvent:
        """Record a telemetry event and update derived metrics."""
        valid = {k: v for k, v in fields.items()
                 if k in TelemetryEvent.__dataclass_fields__ and v is not None}
        event = TelemetryEvent(**valid)
        with self._lock:
            self._events.append(event)

        status = event.status or "ok"
        metrics_collector.increment_counter("requests_total")
        metrics_collector.increment_counter(f"requests_{status}")
        if event.error_category:
            metrics_collector.increment_counter("errors_total")
            metrics_collector.increment_counter(f"errors_{event.error_category}")
        if event.tool:
            metrics_collector.add_to_histogram(f"tool_latency_{event.tool}", event.latency_ms)
        if event.provider:
            metrics_collector.add_to_histogram(f"provider_latency_{event.provider}", event.latency_ms)
        if event.verification_status == "failed":
            metrics_collector.increment_counter("verifications_failed")
        if event.recovery_attempts and event.recovery_attempts > 0:
            metrics_collector.increment_counter("recovery_attempts_total", event.recovery_attempts)
        if event.fallback:
            metrics_collector.increment_counter(f"fallbacks_{event.fallback}")
        return event

    # --------------------------------------------------------------
    def start_task(self, task_id: str, **meta: Any) -> None:
        with self._lock:
            self._active_tasks[str(task_id)] = {**meta, "started": time.time()}
            metrics_collector.set_gauge("active_tasks", len(self._active_tasks))

    def end_task(self, task_id: str) -> None:
        with self._lock:
            self._active_tasks.pop(str(task_id), None)
            metrics_collector.set_gauge("active_tasks", len(self._active_tasks))

    @property
    def active_tasks(self) -> int:
        with self._lock:
            return len(self._active_tasks)

    # --------------------------------------------------------------
    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._events)[-limit:]
        return [e.to_dict() for e in events]

    def get_error_rate(self) -> float:
        total = metrics_collector.get_counter("requests_total")
        if total <= 0:
            return 0.0
        failed = metrics_collector.get_counter("requests_error")
        return round((failed / total) * 100.0, 2)

    def summary(self) -> Dict[str, Any]:
        return {
            "requests_total": metrics_collector.get_counter("requests_total"),
            "requests_ok": metrics_collector.get_counter("requests_ok"),
            "requests_error": metrics_collector.get_counter("requests_error"),
            "requests_confirmation": metrics_collector.get_counter("requests_confirmation"),
            "requests_cancelled": metrics_collector.get_counter("requests_cancelled"),
            "errors_total": metrics_collector.get_counter("errors_total"),
            "error_rate_percent": self.get_error_rate(),
            "recovery_attempts_total": metrics_collector.get_counter("recovery_attempts_total"),
            "verifications_failed": metrics_collector.get_counter("verifications_failed"),
            "active_tasks": self.active_tasks,
        }


# Global telemetry collector (singleton).
telemetry = TelemetryCollector()


def record_system_metrics() -> None:
    """Best-effort memory/CPU gauges (F8). Requires psutil (optional)."""
    try:
        import psutil
        proc = psutil.Process()
        metrics_collector.set_gauge("process_memory_mb", proc.memory_info().rss / (1024 * 1024))
        metrics_collector.set_gauge("process_cpu_percent", proc.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        metrics_collector.set_gauge("system_memory_used_percent", vm.percent)
    except Exception:
        pass