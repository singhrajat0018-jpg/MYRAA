"""Phase U.1 — Telemetry concurrency + deadlock regression suite.

Locks in the fix for the PerformanceTelemetry same-thread self-deadlock
(summary -> is_degraded -> recent re-acquiring a non-reentrant Lock).

Every test runs under the bounded hang guard: a regression of this deadlock
FAILS with a stack dump instead of hanging the suite.
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from desktop_agent.brain.performance.telemetry import (  # noqa: E402
    LatencyReport,
    PerformanceTelemetry,
)
from u1_hang_guard import bounded  # noqa: E402


def make_report(total_ms=10.0, degraded=False, fast=False) -> LatencyReport:
    return LatencyReport(
        timestamp=time.time(),
        stage_latencies={"stage": total_ms},
        total_ms=total_ms,
        cache_hit_rate=0.0,
        parallel_tasks=0,
        fast_path_hit=fast,
        model_tier="fast",
        degraded=degraded,
    )


class TelemetryIsolatedTestCase(unittest.TestCase):
    """Fresh singleton per test — PerformanceTelemetry() is ALWAYS a singleton."""

    def setUp(self) -> None:
        PerformanceTelemetry.reset_singleton()
        self.tel = PerformanceTelemetry(history_size=200)

    def tearDown(self) -> None:
        PerformanceTelemetry.reset_singleton()


# ---------------------------------------------------------------------------
# Semantics preserved (§12)
# ---------------------------------------------------------------------------

class TestSemanticsPreserved(TelemetryIsolatedTestCase):

    def test_empty_state_contract(self):
        self.assertEqual(self.tel.summary(), {"status": "no_data", "requests": 0})
        self.assertFalse(self.tel.is_degraded())
        self.assertEqual(self.tel.recent(5), [])
        self.assertEqual(self.tel.avg_latency(), 0.0)
        self.assertEqual(self.tel.fast_path_ratio(), 0.0)

    def test_summary_keys_unchanged_after_records(self):
        for i, deg in enumerate([False, False, True]):
            rep = self.tel.build_report({"s": 1.0}, float(i + 1), degraded=deg)
            self.assertIsInstance(rep, LatencyReport)
        s = self.tel.summary()
        self.assertEqual(
            set(s.keys()),
            {"status", "total_requests", "avg_latency_ms",
             "fast_path_ratio", "latest_latency_ms"},
        )
        self.assertEqual(s["total_requests"], 3)
        self.assertIn(s["status"], {"healthy", "degraded"})

    def test_degraded_rule_math_unchanged(self):
        # <3 reports -> never degraded
        self.tel.record(make_report(degraded=True))
        self.tel.record(make_report(degraded=True))
        self.assertFalse(self.tel.is_degraded())
        # 3/5 degraded = 60% -> degraded boundary holds (>= threshold)
        for _ in range(3):
            self.tel.record(make_report(degraded=True))
        self.assertTrue(self.tel.is_degraded())
        # 2/5 degraded -> healthy
        PerformanceTelemetry.reset_singleton()
        tel2 = PerformanceTelemetry()
        for _ in range(3):
            tel2.record(make_report())
        tel2.record(make_report(degraded=True))
        tel2.record(make_report(degraded=True))
        self.assertFalse(tel2.is_degraded())

    def test_recent_returns_copy_not_internal_state(self):
        self.tel.record(make_report())
        got = self.tel.recent(10)
        got.clear()
        self.assertEqual(len(self.tel.recent(10)), 1)


# ---------------------------------------------------------------------------
# The original deadlock, as an executable regression (§13)
# ---------------------------------------------------------------------------

class TestOriginalDeadlockRegression(TelemetryIsolatedTestCase):

    def test_summary_on_nonempty_history_does_not_deadlock(self):
        # Pre-fix this EXACT sequence deadlocked forever on line recent().
        for i in range(6):
            self.tel.build_report({"s": 1.0}, float(i), degraded=(i % 2 == 0))
        summary = bounded(
            self.tel.summary, timeout_s=10, label="summary()->is_degraded->recent"
        )
        self.assertEqual(summary["total_requests"], 6)

    def test_concurrent_mixed_api_hammer(self):
        """record -> recent -> summary -> is_degraded concurrently, repeatedly."""
        errors: list[str] = []

        def hammer(role: str) -> None:
            try:
                for i in range(150):
                    if role == "recorder":
                        self.tel.build_report(
                            {"s": 1.0}, float(i % 20),
                            fast_path_hit=(i % 3 == 0),
                            degraded=(i % 7 == 0),
                        )
                    elif role == "reader":
                        self.tel.recent(5)
                    elif role == "summarizer":
                        s = self.tel.summary()
                        assert isinstance(s, dict) and "status" in s
                    else:
                        assert isinstance(self.tel.is_degraded(), bool)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{role}: {exc}")

        roles = ["recorder"] * 3 + ["reader"] * 2 + ["summarizer"] * 2 + ["degrader"]
        threads = [threading.Thread(target=hammer, args=(r,), daemon=True) for r in roles]
        started = [t.start() for t in threads]
        del started

        deadline = time.time() + 30
        for t in threads:
            t.join(max(0.05, deadline - time.time()))
        hung = [t for t in threads if t.is_alive()]
        self.assertFalse(hung, f"threads still alive (deadlock?): {len(hung)}")
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# Targeted concurrency matrix (§7 scenarios 1–10)
# ---------------------------------------------------------------------------

class TestConcurrencyMatrix(TelemetryIsolatedTestCase):

    def _run_threads(self, targets, timeout_s=30):
        threads = [
            threading.Thread(target=fn, daemon=True) for fn in targets
        ]
        start = time.perf_counter()
        for t in threads:
            t.start()
        deadline = start + timeout_s
        for t in threads:
            t.join(max(0.01, deadline - time.perf_counter()))
        alive = [t for t in threads if t.is_alive()]
        return alive, time.perf_counter() - start

    def test_1_concurrent_record(self):
        def writer(seed):
            for i in range(300):
                self.tel.record(make_report(float((seed + i) % 25)))
        alive, dur = self._run_threads([(lambda s=s: writer(s)) for s in range(8)])
        self.assertFalse(alive)
        self.assertLess(dur, 30)
        self.assertEqual(self.tel.summary()["total_requests"], 2400)

    def test_2_concurrent_recent(self):
        self.tel.record(make_report())
        errors = []
        def reader():
            try:
                for _ in range(500):
                    self.tel.recent(3)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
        alive, _ = self._run_threads([reader] * 6)
        self.assertFalse(alive)
        self.assertEqual(errors, [])

    def test_3_recent_during_summary(self):
        stop = threading.Event()

        def summarizer():
            while not stop.is_set():
                bounded(self.tel.summary, timeout_s=5, label="summary")
                time.sleep(0)

        def recents():
            while not stop.is_set():
                bounded(self.tel.recent, args=(4,), timeout_s=5, label="recent")

        workers = [threading.Thread(target=summarizer, daemon=True),
                   threading.Thread(target=recents, daemon=True)]
        for w in workers:
            w.start()
        for i in range(200):
            self.tel.record(make_report(float(i)))
        stop.set()
        for w in workers:
            w.join(timeout=5)
        self.assertFalse(any(w.is_alive() for w in workers))

    def test_4_summary_during_record(self):
        errors = []

        def recorder():
            for i in range(400):
                self.tel.record(make_report(float(i)))

        def summarizer():
            try:
                for _ in range(400):
                    self.tel.summary()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        alive, _ = self._run_threads([recorder, recorder, summarizer])
        self.assertFalse(alive)
        self.assertEqual(errors, [])

    def test_5_is_degraded_during_writes(self):
        result = {}

        def degrader():
            result["degraded"] = bounded(
                lambda: all(isinstance(self.tel.is_degraded(), bool) for _ in range(300)),
                timeout_s=15,
                label="is_degraded loop",
            )

        def recorder():
            for i in range(600):
                self.tel.record(make_report(degraded=(i % 2 == 0)))

        alive, _ = self._run_threads([recorder, recorder, degrader])
        self.assertFalse(alive)
        self.assertTrue(result.get("degraded"))

    def test_6_no_background_worker_threads_spawned(self):
        before = threading.active_count()
        for i in range(100):
            self.tel.build_report({"s": 1.0}, float(i))
            self.tel.summary()
            self.tel.recent(5)
            self.tel.is_degraded()
        # Give any hypothetical leaked thread a moment to register.
        time.sleep(0.05)
        after = threading.active_count()
        self.assertLessEqual(after, before + 1)  # ±pytest-internal jitter only

    def test_7_repeated_startup_shutdown(self):
        for _ in range(50):
            PerformanceTelemetry.reset_singleton()
            tel = PerformanceTelemetry(history_size=50)
            tel.record(make_report())
            self.assertEqual(tel.summary()["total_requests"], 1)
        PerformanceTelemetry.reset_singleton()

    def test_8_high_frequency_telemetry(self):
        start = time.perf_counter()
        for i in range(5000):
            self.tel.build_report({"s": 0.1}, 0.1, fast_path_hit=(i % 2 == 0))
        dur = time.perf_counter() - start
        self.assertEqual(self.tel.summary()["total_requests"], 5000)
        self.assertLess(dur, 20.0, f"high-frequency writes too slow: {dur:.2f}s")

    def test_9_empty_telemetry_state_threadsafe(self):
        errors = []

        def probe():
            try:
                for _ in range(200):
                    self.tel.summary()
                    self.tel.is_degraded()
                    self.tel.avg_latency()
                    self.tel.fast_path_ratio()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        alive, _ = self._run_threads([probe] * 4)
        self.assertFalse(alive)
        self.assertEqual(errors, [])

    def test_10_large_history_bounded(self):
        PerformanceTelemetry.reset_singleton()
        tel = PerformanceTelemetry(history_size=1000)
        for i in range(2500):
            tel.record(make_report(float(i % 50)))
        self.assertEqual(len(tel.recent(2000)), 1000)  # deque maxlen enforced
        s = bounded(tel.summary, timeout_s=10, label="summary(large)")
        self.assertEqual(s["total_requests"], 2500)


if __name__ == "__main__":
    unittest.main()
