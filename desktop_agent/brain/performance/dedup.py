"""Request deduplication to prevent duplicate tool executions."""

from __future__ import annotations

import time
import hashlib
import threading
from dataclasses import dataclass
from typing import Any, Optional
from collections import OrderedDict


@dataclass
class DedupResult:
    is_duplicate: bool
    key: str
    original_result: Any = None
    wait_ms: float = 0.0


class RequestDeduplicator:
    """Deduplicate identical in-flight requests. Thread-safe."""

    def __init__(self, window_ms: float = 5000.0, max_entries: int = 200):
        self._window_ms = window_ms
        self._max_entries = max_entries
        self._inflight: OrderedDict[str, float] = OrderedDict()
        self._results: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _make_key(self, tool_name: str, args: dict) -> str:
        raw = f"{tool_name}:{sorted(args.items())}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def check(self, tool_name: str, args: dict) -> DedupResult:
        key = self._make_key(tool_name, args)
        with self._lock:
            self._evict_expired()
            if key in self._inflight:
                wait = time.time() - self._inflight[key]
                return DedupResult(
                    is_duplicate=True, key=key,
                    wait_ms=wait * 1000,
                )
            self._inflight[key] = time.time()
            return DedupResult(is_duplicate=False, key=key)

    def complete(self, key: str, result: Any = None):
        with self._lock:
            self._results[key] = result

    def get_result(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._results.get(key)

    def release(self, key: str):
        with self._lock:
            self._inflight.pop(key, None)
            self._results.pop(key, None)

    def _evict_expired(self):
        now = time.time()
        expired = [k for k, t in self._inflight.items()
                   if (now - t) * 1000 > self._window_ms]
        for k in expired:
            self._inflight.pop(k, None)
            self._results.pop(k, None)
        while len(self._inflight) > self._max_entries:
            oldest_key, _ = self._inflight.popitem(last=False)
            self._results.pop(oldest_key, None)

    def clear(self):
        with self._lock:
            self._inflight.clear()
            self._results.clear()

    def active_count(self) -> int:
        with self._lock:
            return len(self._inflight)
