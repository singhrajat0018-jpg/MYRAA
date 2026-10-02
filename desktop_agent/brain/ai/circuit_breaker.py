"""
Circuit Breaker — Prevents cascading failures for external services.

States:
  CLOSED  → normal operation, requests pass through
  OPEN    → failures exceeded threshold, requests fail fast
  HALF_OPEN → after cooldown, one probe request allowed to test recovery

Thread-safe via threading.Lock.
"""

from __future__ import annotations
import time
import threading
import logging
from enum import Enum
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    half_open_max_probes: int = 1
    success_threshold: int = 2


@dataclass
class CircuitBreakerStats:
    state: str = "closed"
    consecutive_failures: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_rejected: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    last_state_change: float = 0.0
    opened_at: float = 0.0


class CircuitBreaker:
    def __init__(self, name: str = "default", config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_probes = 0
        self._opened_at = 0.0
        self._last_success = 0.0
        self._last_failure = 0.0
        self._last_state_change = time.monotonic()
        self._total_successes = 0
        self._total_failures = 0
        self._total_rejected = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.config.cooldown_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.config.cooldown_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    self._total_rejected += 1
                    return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_probes >= self.config.half_open_max_probes:
                    self._total_rejected += 1
                    return False
                self._half_open_probes += 1

            return True

    def record_success(self) -> None:
        with self._lock:
            self._total_successes += 1
            self._last_success = time.monotonic()
            self._consecutive_failures = 0

            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._consecutive_successes += 1

    def record_failure(self) -> None:
        with self._lock:
            self._total_failures += 1
            self._last_failure = time.monotonic()
            self._consecutive_failures += 1
            self._consecutive_successes = 0

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()

        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
            log.warning(
                "[CircuitBreaker:%s] OPENED after %d failures (cooldown %ds)",
                self.name, self._consecutive_failures, self.config.cooldown_seconds,
            )
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_probes = 0
            self._consecutive_successes = 0
            log.info("[CircuitBreaker:%s] HALF_OPEN — probing...", self.name)
        elif new_state == CircuitState.CLOSED:
            log.info(
                "[CircuitBreaker:%s] CLOSED (recovered after %d successes)",
                self.name, self._consecutive_successes,
            )

    def reset(self) -> None:
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._half_open_probes = 0

    def stats(self) -> CircuitBreakerStats:
        with self._lock:
            return CircuitBreakerStats(
                state=self._state.value,
                consecutive_failures=self._consecutive_failures,
                total_successes=self._total_successes,
                total_failures=self._total_failures,
                total_rejected=self._total_rejected,
                last_success=self._last_success,
                last_failure=self._last_failure,
                last_state_change=self._last_state_change,
                opened_at=self._opened_at,
            )
