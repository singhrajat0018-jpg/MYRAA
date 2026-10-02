"""MetricStore — persistent skill metrics with atomic writes + bounded history.

Survives restart. Uses existing persistence conventions.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DIR = pathlib.Path.home() / ".myraa" / "skill_metrics"
_MAX_HISTORY = 100  # bounded recent history per skill


class MetricStore:
    """Persistent skill metrics store.

    Features:
    - Atomic writes (temp + os.replace)
    - .bak backup
    - Corruption recovery
    - Bounded history
    - Aggregated statistics
    """

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        self._dir = pathlib.Path(storage_dir) if storage_dir else _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._metrics_file = self._dir / "metrics.json"
        self._lock = threading.Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        data = self._read()
        if data:
            self._cache = data
            logger.info("MetricStore loaded: %d skills", len(self._cache))

    def record_success(self, skill_id: str, latency_ms: float) -> None:
        """Record a successful skill execution."""
        self._ensure_loaded()
        with self._lock:
            if skill_id not in self._cache:
                self._cache[skill_id] = self._empty_metric()
            m = self._cache[skill_id]
            m["total_calls"] += 1
            m["success_count"] += 1
            m["total_latency_ms"] += latency_ms
            m["avg_latency_ms"] = m["total_latency_ms"] / m["total_calls"]
            m["last_success"] = time.time()
            m["last_used"] = time.time()
            # Bounded history
            m["history"].append({
                "type": "success",
                "latency_ms": latency_ms,
                "timestamp": time.time(),
            })
            if len(m["history"]) > _MAX_HISTORY:
                m["history"] = m["history"][-_MAX_HISTORY:]
            self._write()

    def record_failure(self, skill_id: str, error: str) -> None:
        """Record a failed skill execution."""
        self._ensure_loaded()
        with self._lock:
            if skill_id not in self._cache:
                self._cache[skill_id] = self._empty_metric()
            m = self._cache[skill_id]
            m["total_calls"] += 1
            m["failure_count"] += 1
            m["last_failure"] = time.time()
            m["last_used"] = time.time()
            m["recent_errors"].append(error)
            if len(m["recent_errors"]) > 10:
                m["recent_errors"] = m["recent_errors"][-10:]
            m["history"].append({
                "type": "failure",
                "error": error,
                "timestamp": time.time(),
            })
            if len(m["history"]) > _MAX_HISTORY:
                m["history"] = m["history"][-_MAX_HISTORY:]
            self._write()

    def get_metrics(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a skill."""
        self._ensure_loaded()
        with self._lock:
            return self._cache.get(skill_id)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all skill metrics."""
        self._ensure_loaded()
        with self._lock:
            return dict(self._cache)

    def summary(self) -> Dict[str, Any]:
        """Get aggregated summary."""
        self._ensure_loaded()
        with self._lock:
            skills = dict(self._cache)

        total_calls = sum(m["total_calls"] for m in skills.values())
        total_success = sum(m["success_count"] for m in skills.values())
        total_failures = sum(m["failure_count"] for m in skills.values())

        return {
            "total_skills": len(skills),
            "total_calls": total_calls,
            "total_success": total_success,
            "total_failures": total_failures,
            "overall_success_rate": total_success / total_calls if total_calls > 0 else 1.0,
            "skills": {k: {
                "total_calls": v["total_calls"],
                "success_rate": v["success_count"] / v["total_calls"] if v["total_calls"] > 0 else 1.0,
                "avg_latency_ms": v["avg_latency_ms"],
                "last_used": v["last_used"],
            } for k, v in skills.items()},
        }

    def reset(self) -> None:
        with self._lock:
            self._cache.clear()
            self._write()

    def _empty_metric(self) -> Dict[str, Any]:
        return {
            "total_calls": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_latency_ms": 0.0,
            "avg_latency_ms": 0.0,
            "last_success": 0.0,
            "last_failure": 0.0,
            "last_used": 0.0,
            "recent_errors": [],
            "history": [],
        }

    def _read(self) -> Dict[str, Dict[str, Any]]:
        if not self._metrics_file.exists():
            return {}
        try:
            with open(self._metrics_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupt metrics file: %s — attempting backup", exc)
            bak = self._metrics_file.with_suffix(".bak")
            if bak.exists():
                try:
                    with open(bak, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    quarantine = self._metrics_file.with_suffix(f".corrupt.{int(time.time())}")
                    self._metrics_file.rename(quarantine)
                    bak.rename(self._metrics_file)
                    return data
                except Exception:
                    pass
            return {}

    def _write(self) -> bool:
        try:
            tmp = self._metrics_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, default=str)
            if self._metrics_file.exists():
                bak = self._metrics_file.with_suffix(".bak")
                if bak.exists():
                    bak.unlink()
                self._metrics_file.rename(bak)
            tmp.rename(self._metrics_file)
            return True
        except Exception as exc:
            logger.error("Failed to write metrics: %s", exc)
            return False


# Global singleton
_metric_store: Optional[MetricStore] = None


def get_metric_store() -> MetricStore:
    global _metric_store
    if _metric_store is None:
        _metric_store = MetricStore()
    return _metric_store
