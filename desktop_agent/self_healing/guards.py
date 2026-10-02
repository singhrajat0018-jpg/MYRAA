from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    _HAS_PSUTIL = False

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    max_cpu_pct: float = 80.0
    max_memory_mb: float = 2048.0
    max_disk_mb: float = 1024.0
    max_threads: int = 20
    max_time_seconds: float = 300.0
    max_concurrent_heals: int = 3


@dataclass
class LoopGuardConfig:
    max_repair_attempts: int = 5
    max_candidate_versions: int = 10
    max_rollback_count: int = 3
    max_time_budget_seconds: float = 600.0
    same_failure_threshold: int = 3


@dataclass
class LoopGuardState:
    repair_attempts: int = 0
    candidate_versions: int = 0
    rollback_count: int = 0
    start_time: float = 0.0
    same_failure_count: int = 0
    last_failure_hash: str = ""


def _get_resource_usage() -> dict[str, Any]:
    usage: dict[str, Any] = {
        "cpu_pct": 0.0,
        "memory_mb": 0.0,
        "disk_mb": 0.0,
        "threads": 0,
    }
    if not _HAS_PSUTIL:
        return usage
    try:
        usage["cpu_pct"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        usage["memory_mb"] = mem.used / (1024 * 1024)
        disk = psutil.disk_usage("/")
        usage["disk_mb"] = disk.used / (1024 * 1024)
        usage["threads"] = psutil.Process().num_threads()
    except Exception:
        logger.debug("Failed to read resource usage", exc_info=True)
    return usage


class ResourceGuard:
    _instance: ResourceGuard | None = None
    _lock_class = threading.Lock()

    def __new__(cls, limits: ResourceLimits | None = None) -> ResourceGuard:
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_fields(limits or ResourceLimits())
            return cls._instance

    def _init_fields(self, limits: ResourceLimits) -> None:
        self._lock = threading.Lock()
        self._limits = limits
        self._active_operations = 0
        self._operation_start: float = 0.0

    def check_resources(self) -> tuple[bool, dict[str, Any]]:
        usage = _get_resource_usage()
        reasons: list[str] = []
        if usage["cpu_pct"] > self._limits.max_cpu_pct:
            reasons.append(f"cpu {usage['cpu_pct']:.1f}% > {self._limits.max_cpu_pct}%")
        if usage["memory_mb"] > self._limits.max_memory_mb:
            reasons.append(f"memory {usage['memory_mb']:.0f}MB > {self._limits.max_memory_mb:.0f}MB")
        if usage["disk_mb"] > self._limits.max_disk_mb:
            reasons.append(f"disk {usage['disk_mb']:.0f}MB > {self._limits.max_disk_mb:.0f}MB")
        within = len(reasons) == 0
        usage["within_limits"] = within
        usage["violations"] = reasons
        return within, usage

    def can_start_operation(self) -> bool:
        with self._lock:
            if self._active_operations >= self._limits.max_concurrent_heals:
                return False
        within, _ = self.check_resources()
        if not within:
            return False
        if self._operation_start > 0:
            elapsed = time.time() - self._operation_start
            if elapsed > self._limits.max_time_seconds:
                return False
        return True

    def record_operation_start(self) -> None:
        with self._lock:
            self._active_operations += 1
            if self._operation_start == 0.0:
                self._operation_start = time.time()

    def record_operation_end(self) -> None:
        with self._lock:
            self._active_operations = max(0, self._active_operations - 1)
            if self._active_operations == 0:
                self._operation_start = 0.0

    def get_usage(self) -> dict[str, Any]:
        return _get_resource_usage()

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock_class:
            cls._instance = None


class LoopProtectionGuard:
    _instance: LoopProtectionGuard | None = None
    _lock_class = threading.Lock()

    def __new__(
        cls, config: LoopGuardConfig | None = None
    ) -> LoopProtectionGuard:
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_fields(config or LoopGuardConfig())
            return cls._instance

    def _init_fields(self, config: LoopGuardConfig) -> None:
        self._lock = threading.Lock()
        self._config = config
        self._state = LoopGuardState(start_time=time.time())

    def can_attempt_repair(self) -> bool:
        with self._lock:
            s = self._state
            c = self._config
            if s.repair_attempts >= c.max_repair_attempts:
                return False
            if s.same_failure_count >= c.same_failure_threshold:
                return False
            elapsed = time.time() - s.start_time
            if elapsed >= c.max_time_budget_seconds:
                return False
            return True

    def record_repair_attempt(self, failure_hash: str = "") -> None:
        with self._lock:
            self._state.repair_attempts += 1
            if failure_hash and failure_hash == self._state.last_failure_hash:
                self._state.same_failure_count += 1
            else:
                self._state.last_failure_hash = failure_hash
                self._state.same_failure_count = 1 if failure_hash else 0

    def can_create_candidate(self) -> bool:
        with self._lock:
            return self._state.candidate_versions < self._config.max_candidate_versions

    def record_candidate_creation(self) -> None:
        with self._lock:
            self._state.candidate_versions += 1

    def can_rollback(self) -> bool:
        with self._lock:
            return self._state.rollback_count < self._config.max_rollback_count

    def record_rollback(self) -> None:
        with self._lock:
            self._state.rollback_count += 1

    def is_loop_detected(self) -> bool:
        with self._lock:
            return self._state.same_failure_count >= self._config.same_failure_threshold

    def reset(self) -> None:
        with self._lock:
            self._state = LoopGuardState(start_time=time.time())

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "repair_attempts": self._state.repair_attempts,
                "candidate_versions": self._state.candidate_versions,
                "rollback_count": self._state.rollback_count,
                "start_time": self._state.start_time,
                "elapsed_seconds": time.time() - self._state.start_time,
                "same_failure_count": self._state.same_failure_count,
                "last_failure_hash": self._state.last_failure_hash,
            }

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock_class:
            cls._instance = None
