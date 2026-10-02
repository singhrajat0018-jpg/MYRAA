"""Multi-tier context caching for the execution pipeline.

Provides in-memory LRU, tool-result, and screen-state caching with
TTL expiry, invalidation, and cross-tier promotion.
"""

from __future__ import annotations

import time
import threading
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from collections import OrderedDict


class CacheTier(Enum):
    """Cache tiers ordered by speed and capacity."""
    L1_SCREEN = "screen"
    L2_TOOL_RESULT = "tool"
    L3_CONTEXT = "context"
    L4_MEMORY = "memory"
    L5_SEMANTIC = "semantic"


@dataclass
class CacheEntry:
    key: str
    value: Any
    tier: CacheTier
    created_at: float
    ttl_ms: float
    access_count: int = 0
    last_access: float = 0.0
    size_bytes: int = 0

    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) * 1000 > self.ttl_ms

    def touch(self):
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


DEFAULT_TTLS = {
    CacheTier.L1_SCREEN: 5_000,
    CacheTier.L2_TOOL_RESULT: 60_000,
    CacheTier.L3_CONTEXT: 30_000,
    CacheTier.L4_MEMORY: 120_000,
    CacheTier.L5_SEMANTIC: 300_000,
}

DEFAULT_CAPACITIES = {
    CacheTier.L1_SCREEN: 1,
    CacheTier.L2_TOOL_RESULT: 200,
    CacheTier.L3_CONTEXT: 100,
    CacheTier.L4_MEMORY: 500,
    CacheTier.L5_SEMANTIC: 200,
}


class ContextCache:
    """Multi-tier context cache with TTL and LRU eviction. Thread-safe."""

    _instance: Optional['ContextCache'] = None
    _lock_class = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, ttls: Optional[dict] = None, capacities: Optional[dict] = None):
        if self._initialized:
            return
        self._initialized = True
        self._ttls = ttls or DEFAULT_TTLS.copy()
        self._capacities = capacities or DEFAULT_CAPACITIES.copy()
        self._tiers: dict[CacheTier, OrderedDict[str, CacheEntry]] = {
            tier: OrderedDict() for tier in CacheTier
        }
        self._stats = {tier: CacheStats() for tier in CacheTier}
        self._lock = threading.Lock()

    def _make_key(self, raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str, tier: CacheTier) -> Optional[Any]:
        with self._lock:
            entries = self._tiers[tier]
            if key not in entries:
                self._stats[tier].misses += 1
                return None
            entry = entries[key]
            if entry.expired:
                del entries[key]
                self._stats[tier].expired += 1
                self._stats[tier].misses += 1
                return None
            entry.touch()
            entries.move_to_end(key)
            self._stats[tier].hits += 1
            return entry.value

    def put(self, key: str, value: Any, tier: CacheTier,
            ttl_ms: Optional[float] = None, size_bytes: int = 0):
        ttl = ttl_ms or self._ttls[tier]
        with self._lock:
            entries = self._tiers[tier]
            if key in entries:
                del entries[key]
            while len(entries) >= self._capacities[tier]:
                evicted_key, _ = entries.popitem(last=False)
                self._stats[tier].evictions += 1
                self._stats[tier].total_size_bytes -= 1
            entry = CacheEntry(
                key=key, value=value, tier=tier,
                created_at=time.time(), ttl_ms=ttl,
                size_bytes=size_bytes,
            )
            entries[key] = entry
            self._stats[tier].entry_count = len(entries)
            self._stats[tier].total_size_bytes += size_bytes

    def invalidate(self, key: str, tier: CacheTier) -> bool:
        with self._lock:
            if key in self._tiers[tier]:
                del self._tiers[tier][key]
                self._stats[tier].entry_count = len(self._tiers[tier])
                return True
            return False

    def invalidate_pattern(self, pattern: str, tier: Optional[CacheTier] = None):
        tiers = [tier] if tier else list(CacheTier)
        with self._lock:
            for t in tiers:
                keys_to_del = [k for k in self._tiers[t] if pattern in k]
                for k in keys_to_del:
                    del self._tiers[t][k]
                self._stats[t].entry_count = len(self._tiers[t])

    def clear(self, tier: Optional[CacheTier] = None):
        with self._lock:
            tiers = [tier] if tier else list(CacheTier)
            for t in tiers:
                self._tiers[t].clear()
                self._stats[t] = CacheStats()

    def stats(self) -> dict[CacheTier, CacheStats]:
        with self._lock:
            result = {}
            for tier in CacheTier:
                s = CacheStats(
                    hits=self._stats[tier].hits,
                    misses=self._stats[tier].misses,
                    evictions=self._stats[tier].evictions,
                    expired=self._stats[tier].expired,
                    entry_count=len(self._tiers[tier]),
                )
                result[tier] = s
            return result

    def total_hit_rate(self) -> float:
        total_hits = sum(s.hits for s in self._stats.values())
        total_misses = sum(s.misses for s in self._stats.values())
        total = total_hits + total_misses
        return total_hits / total if total > 0 else 0.0

    @classmethod
    def singleton(cls) -> 'ContextCache':
        return cls()

    @classmethod
    def reset_singleton(cls):
        with cls._lock_class:
            cls._instance = None
