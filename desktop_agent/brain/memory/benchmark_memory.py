"""
MYRAA Memory 2.0 — M13: Benchmark suite.

Measures actual latency/throughput of the unified memory store operations so
performance regressions are detectable and reproducible.

Run (repo root):
    python -m desktop_agent.brain.memory.benchmark_memory [--iterations N]

Prints a plain-text table of executed numbers. Uses clean synthetic fixtures
(no secrets, no live services, no network).
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import tempfile
import time
from typing import Callable, List

from desktop_agent.brain.memory.memory_commands import MemoryCommandEngine
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryScope,
    MemoryStatus,
    MemoryType,
    Provenance,
    RetentionPolicy,
)

TOPICS = ["NIFTY", "TCS", "RELIANCE", "INFOSYS", "HDFC", "SBI", "ADANI", "TATA"]
FACTS = [
    "price is around", "support at", "resistance at", "volume spiked",
    "moving average crossed", "earnings due next week", "institutional buying",
    "volatility rising", "breaks above", "consolidating near",
]

FRUIT = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape",
         "honeydew", "kiwi", "lemon", "mango", "nectarine", "orange", "peach"]
COLOR = ["red", "blue", "green", "yellow", "purple", "orange", "pink", "teal"]
ADJ = ["sweet", "tart", "ripe", "fresh", "local", "organic", "seasonal", "crunchy"]


def _fmt(value: float) -> str:
    if value >= 1:
        return f"{value:.2f}s"
    if value >= 0.001:
        return f"{value * 1000:.2f}ms"
    return f"{value * 1_000_000:.2f}us"


def _bench(fn: Callable, iterations: int) -> List[float]:
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


def _stats(samples: List[float]) -> str:
    samples = sorted(samples)
    mean = statistics.mean(samples)
    p50 = samples[len(samples) // 2]
    p95 = samples[int(len(samples) * 0.95) - 1] if samples else 0
    return f"mean={_fmt(mean)} p50={_fmt(p50)} p95={_fmt(p95)}"


def _clean_fact() -> str:
    return f"{random.choice(FRUIT)} {random.choice(ADJ)} {random.choice(COLOR)} " \
           f"batch {random.randint(1, 100000)}"


def _record(n: int) -> MemoryRecord:
    return MemoryRecord(
        type=MemoryType.SEMANTIC,
        content=_clean_fact(),
        summary=_clean_fact()[:80],
        source="benchmark",
        scope=MemoryScope.USER,
        importance=0.7,
        confidence=0.8,
        provenance=Provenance.SYSTEM_OBSERVED,
        retention_policy=RetentionPolicy.MEDIUM_TERM,
        tags={"bench"},
    )


def run_benchmarks(iterations: int = 5) -> dict:
    results: dict = {}
    rows: List[str] = []

    def add(name: str, fn: Callable, iters: int = iterations) -> None:
        samples = _bench(fn, iters)
        results[name] = samples
        rows.append(f"{name:<42} {_stats(samples)}")

    fd, path = tempfile.mkstemp(suffix=".json")
    import os
    os.close(fd)
    manager = UnifiedMemoryManager(path)

    N = 300
    batch = [_record(i) for i in range(N)]

    # Warm up
    for rec in batch[:20]:
        manager.remember(rec)
    manager.clear()

    # --- remember throughput (fresh inserts) ---
    def remember_single():
        manager.remember(_record(0))
    add(f"remember (single insert, {iterations} samples)", remember_single, iterations)
    manager.clear()

    def remember_bulk():
        for rec in batch:
            manager.remember(rec)
    start = time.perf_counter()
    remember_bulk()
    elapsed = time.perf_counter() - start
    results["remember_bulk"] = {"n": N, "seconds": elapsed,
                                "per_sec": N / elapsed if elapsed else 0}
    rows.append(f"{'remember bulk (' + str(N) + ' inserts)':<42} "
                f"total={_fmt(elapsed)} ({N / elapsed:.0f} ops/s)")

    # --- recall by id ---
    ids = [r.id for r in manager.get_all_active()]

    def recall_by_id():
        manager.recall(random.choice(ids))
    add("recall by id (random)", recall_by_id)

    # --- recall_by_content ---
    def recall_content():
        manager.recall_by_content(random.choice(FRUIT), limit=5)
    add("recall_by_content (top-5)", recall_content)

    # --- get_all_active ---
    def get_all_active():
        manager.get_all_active()
    add("get_all_active", get_all_active)

    # --- consolidate over the populated store ---
    def consolidate():
        manager.consolidate()
    add("consolidate pass (over %d records)" % N, consolidate, max(1, iterations // 2))

    # --- decay sweep ---
    def decay():
        manager.run_decay()
    add("run_decay sweep", decay)

    # --- lifecycle transitions ---
    active = manager.get_all_active()
    def lifecycle_cycle():
        target = active[random.randrange(len(active))]
        manager.archive(target.id)
        manager.restore(target.id)
    add("archive+restore round-trip", lifecycle_cycle, max(3, iterations))

    # --- M10 command engine ---
    engine = MemoryCommandEngine(manager)

    def cmd_remember():
        engine.handle(f"remember that {random.choice(FRUIT)} is {random.choice(ADJ)}")
    add("command: REMEMBER", cmd_remember, max(3, iterations))

    def cmd_recall():
        engine.handle(f"what do you remember about {random.choice(FRUIT)}?")
    add("command: RECALL", cmd_recall, max(3, iterations))

    def cmd_parse_only():
        engine.parser.parse(f"remember that {random.choice(FRUIT)} is {random.choice(ADJ)}")
    add("parser.parse (no store I/O)", cmd_parse_only, max(3, iterations))

    total = manager.get_count()
    active_count = manager.get_active_count()

    # Cleanup
    manager.clear()
    try:
        os.unlink(path)
    except OSError:
        pass

    print("\nMYRAA Memory 2.0 Benchmark (executed)")
    print("=" * 78)
    for row in rows:
        print(row)
    print("-" * 78)
    print(f"{'store final size':<42} total={total} active={active_count}")
    print("\nReproduce:  python -m desktop_agent.brain.memory.benchmark_memory "
          f"--iterations {iterations}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MYRAA Memory 2.0 benchmark")
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    run_benchmarks(args.iterations)