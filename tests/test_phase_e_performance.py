"""Phase E: Performance Layer Tests.

Tests: LatencyTracker, ContextCache, ParallelExecutor, ModelRouter,
StreamProcessor, ContextCompressor, RequestDeduplicator, FastPath,
PerformanceTelemetry.
"""

import time
import threading
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from desktop_agent.brain.performance.latency_tracker import (
    LatencyTracker, LatencyBudget, StageStats
)
from desktop_agent.brain.performance.context_cache import (
    ContextCache, CacheTier, CacheStats
)
from desktop_agent.brain.performance.parallel_executor import (
    ParallelExecutor, ParallelTask, ExecutionPool
)
try:
    from desktop_agent.brain.performance.model_router import (
        ModelRouter, ModelTier, RouteDecision
    )
    HAS_MODEL_ROUTER = True
except ImportError:
    HAS_MODEL_ROUTER = False
from desktop_agent.brain.performance.streaming import (
    StreamProcessor, StreamPhase, StreamChunk
)
from desktop_agent.brain.performance.compression import (
    ContextCompressor, CompressionResult, estimate_tokens
)
from desktop_agent.brain.performance.dedup import (
    RequestDeduplicator, DedupResult
)
from desktop_agent.brain.performance.fast_path import FastPath, FastPathResult
from desktop_agent.brain.performance.telemetry import (
    PerformanceTelemetry, LatencyReport
)


# ============================================================
# LatencyTracker
# ============================================================

class TestLatencyTracker:
    def setup_method(self):
        LatencyTracker.reset_singleton()

    def teardown_method(self):
        LatencyTracker.reset_singleton()

    def test_record_and_report(self):
        tracker = LatencyTracker(max_samples=100)
        tracker.record("perception", 45.0, LatencyBudget.PERCEPTION)
        tracker.record("perception", 30.0, LatencyBudget.PERCEPTION)
        report = tracker.report()
        assert "perception" in report
        assert report["perception"].count == 2

    def test_context_manager(self):
        tracker = LatencyTracker(max_samples=100)
        with tracker.measure("test_stage", LatencyBudget.PERCEPTION):
            time.sleep(0.001)
        report = tracker.report()
        assert "test_stage" in report
        assert report["test_stage"].count == 1
        assert report["test_stage"].min_ms > 0

    def test_over_budget_detection(self):
        tracker = LatencyTracker(max_samples=100)
        tracker.record("fast_stage", 5.0, LatencyBudget.PERCEPTION)
        tracker.record("slow_stage", 100.0, LatencyBudget.PERCEPTION)
        report = tracker.report()
        assert report["fast_stage"].over_budget_count == 0
        assert report["slow_stage"].over_budget_count == 1

    def test_percentiles(self):
        tracker = LatencyTracker(max_samples=1000)
        for i in range(100):
            tracker.record("stage", float(i), LatencyBudget.PERCEPTION)
        stats = tracker.get_stage_stats("stage")
        assert stats.count == 100
        assert stats.min_ms == 0.0
        assert stats.max_ms == 99.0
        assert stats.p50_ms > 0
        assert stats.p90_ms > stats.p50_ms

    def test_singleton(self):
        t1 = LatencyTracker.singleton()
        t2 = LatencyTracker.singleton()
        assert t1 is t2

    def test_is_degraded(self):
        tracker = LatencyTracker(max_samples=100)
        for _ in range(10):
            tracker.record("stage", 200.0, LatencyBudget.PERCEPTION)
        assert tracker.is_degraded()

    def test_reset(self):
        tracker = LatencyTracker(max_samples=100)
        tracker.record("stage", 10.0, LatencyBudget.PERCEPTION)
        tracker.reset()
        report = tracker.report()
        assert "stage" not in report or report["stage"].count == 0

    def test_metadata(self):
        tracker = LatencyTracker(max_samples=100)
        tracker.record("stage", 10.0, LatencyBudget.PERCEPTION,
                       metadata={"tool": "click"})
        report = tracker.report()
        assert report["stage"].count == 1


# ============================================================
# ContextCache
# ============================================================

class TestContextCache:
    def setup_method(self):
        ContextCache.reset_singleton()

    def teardown_method(self):
        ContextCache.reset_singleton()

    def test_put_and_get(self):
        cache = ContextCache()
        cache.put("key1", "value1", CacheTier.L3_CONTEXT)
        result = cache.get("key1", CacheTier.L3_CONTEXT)
        assert result == "value1"

    def test_cache_miss(self):
        cache = ContextCache()
        result = cache.get("nonexistent", CacheTier.L3_CONTEXT)
        assert result is None

    def test_ttl_expiry(self):
        cache = ContextCache()
        cache.put("key1", "value1", CacheTier.L1_SCREEN, ttl_ms=1)
        time.sleep(0.01)
        result = cache.get("key1", CacheTier.L1_SCREEN)
        assert result is None

    def test_lru_eviction(self):
        cache = ContextCache(capacities={CacheTier.L2_TOOL_RESULT: 3})
        for i in range(5):
            cache.put(f"key{i}", f"val{i}", CacheTier.L2_TOOL_RESULT)
        assert cache.get("key0", CacheTier.L2_TOOL_RESULT) is None
        assert cache.get("key1", CacheTier.L2_TOOL_RESULT) is None
        assert cache.get("key4", CacheTier.L2_TOOL_RESULT) == "val4"

    def test_invalidate(self):
        cache = ContextCache()
        cache.put("key1", "value1", CacheTier.L3_CONTEXT)
        assert cache.invalidate("key1", CacheTier.L3_CONTEXT) is True
        assert cache.get("key1", CacheTier.L3_CONTEXT) is None

    def test_invalidate_pattern(self):
        cache = ContextCache()
        cache.put("user:1", "a", CacheTier.L3_CONTEXT)
        cache.put("user:2", "b", CacheTier.L3_CONTEXT)
        cache.put("tool:1", "c", CacheTier.L3_CONTEXT)
        cache.invalidate_pattern("user:", CacheTier.L3_CONTEXT)
        assert cache.get("user:1", CacheTier.L3_CONTEXT) is None
        assert cache.get("tool:1", CacheTier.L3_CONTEXT) == "c"

    def test_clear(self):
        cache = ContextCache()
        cache.put("key1", "value1", CacheTier.L3_CONTEXT)
        cache.clear(CacheTier.L3_CONTEXT)
        assert cache.get("key1", CacheTier.L3_CONTEXT) is None

    def test_hit_rate(self):
        cache = ContextCache()
        cache.put("key1", "value1", CacheTier.L3_CONTEXT)
        cache.get("key1", CacheTier.L3_CONTEXT)
        cache.get("miss", CacheTier.L3_CONTEXT)
        stats = cache.stats()
        assert stats[CacheTier.L3_CONTEXT].hits == 1
        assert stats[CacheTier.L3_CONTEXT].misses == 1
        assert cache.total_hit_rate() == 0.5

    def test_singleton(self):
        c1 = ContextCache.singleton()
        c2 = ContextCache.singleton()
        assert c1 is c2


# ============================================================
# ParallelExecutor
# ============================================================

class TestParallelExecutor:
    def setup_method(self):
        ParallelExecutor.reset_singleton()

    def teardown_method(self):
        ParallelExecutor.reset_singleton()

    def test_execute_all(self):
        executor = ParallelExecutor(pool_size=2)
        tasks = [
            ParallelTask("t1", lambda: 1 + 1),
            ParallelTask("t2", lambda: 2 + 2),
        ]
        results = executor.execute_all(tasks)
        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].value == 2
        assert results[1].value == 4

    def test_execute_any(self):
        executor = ParallelExecutor(pool_size=2)
        def slow():
            time.sleep(0.5)
            return "slow"
        def fast():
            return "fast"
        tasks = [ParallelTask("fast", fast, timeout_ms=5000),
                 ParallelTask("slow", slow, timeout_ms=5000)]
        result = executor.execute_any(tasks)
        assert result.success
        assert result.value == "fast"

    def test_task_failure(self):
        def fail():
            raise RuntimeError("boom")
        executor = ParallelExecutor(pool_size=2)
        tasks = [ParallelTask("fail", fail)]
        results = executor.execute_all(tasks)
        assert not results[0].success
        assert "boom" in results[0].error

    def test_timeout(self):
        executor = ParallelExecutor(pool_size=2)
        tasks = [ParallelTask("slow", lambda: time.sleep(10), timeout_ms=50)]
        results = executor.execute_all(tasks)
        assert not results[0].success

    def test_fail_fast(self):
        def fail():
            raise RuntimeError("boom")
        def slow():
            time.sleep(10)
        executor = ParallelExecutor(pool_size=2)
        tasks = [ParallelTask("fail", fail), ParallelTask("slow", slow)]
        results = executor.execute_all(tasks, fail_fast=True)
        assert not results[0].success

    def test_active_count(self):
        executor = ParallelExecutor(pool_size=2)
        assert executor.active_count() == 0


# ============================================================
# ModelRouter (removed — tests preserved but skipped)
# ============================================================

@pytest.mark.skipif(not HAS_MODEL_ROUTER, reason="ModelRouter removed")
class TestModelRouter:
    def setup_method(self):
        ModelRouter.reset_singleton()

    def teardown_method(self):
        ModelRouter.reset_singleton()

    def test_route_simple_query(self):
        router = ModelRouter()
        decision = router.route(complexity=0.1, latency_budget_ms=300)
        assert decision.tier == ModelTier.FAST

    def test_route_complex_query(self):
        router = ModelRouter()
        decision = router.route(complexity=0.9, latency_budget_ms=2000)
        assert decision.tier == ModelTier.STRONG

    def test_route_vision(self):
        router = ModelRouter()
        decision = router.route(needs_vision=True)
        assert decision.tier == ModelTier.VISION

    def test_route_local(self):
        router = ModelRouter()
        decision = router.route(prefer_local=True)
        assert decision.tier == ModelTier.LOCAL

    def test_record_latency(self):
        router = ModelRouter()
        router.record_latency(ModelTier.FAST, 150.0)
        router.record_latency(ModelTier.FAST, 200.0)
        avg = router.avg_latency(ModelTier.FAST)
        assert avg == 175.0

    def test_provider_availability(self):
        router = ModelRouter()
        router.set_provider_available("ollama", False)
        decision = router.route(prefer_local=True)
        assert decision.tier != ModelTier.LOCAL

    def test_get_profile(self):
        router = ModelRouter()
        profile = router.get_profile(ModelTier.FAST)
        assert profile.provider == "gemini"

    def test_singleton(self):
        r1 = ModelRouter.singleton()
        r2 = ModelRouter.singleton()
        assert r1 is r2


# ============================================================
# StreamProcessor
# ============================================================

class TestStreamProcessor:
    def test_emit_and_read(self):
        sp = StreamProcessor()
        sp.start()
        chunk = sp.emit(StreamPhase.PERCEPTION, {"elements": 5})
        assert chunk.phase == StreamPhase.PERCEPTION
        assert chunk.seq == 1
        assert len(sp.chunks()) == 1

    def test_listener(self):
        sp = StreamProcessor()
        sp.start()
        received = []
        sp.on_chunk(lambda c: received.append(c))
        sp.emit(StreamPhase.CONTEXT, "data")
        assert len(received) == 1

    def test_latest(self):
        sp = StreamProcessor()
        sp.start()
        sp.emit(StreamPhase.PERCEPTION, "a")
        sp.emit(StreamPhase.EXECUTION, "b")
        assert sp.latest().phase == StreamPhase.EXECUTION

    def test_elapsed(self):
        sp = StreamProcessor()
        sp.start()
        time.sleep(0.001)
        assert sp.elapsed_ms() > 0

    def test_clear(self):
        sp = StreamProcessor()
        sp.start()
        sp.emit(StreamPhase.PERCEPTION, "a")
        sp.clear()
        assert len(sp.chunks()) == 0


# ============================================================
# ContextCompressor
# ============================================================

class TestContextCompressor:
    def test_no_compression_needed(self):
        comp = ContextCompressor(max_tokens=1000)
        result = comp.compress("short text")
        assert result.compressed == "short text"
        assert result.strategy == "none"

    def test_truncation_compression(self):
        comp = ContextCompressor(max_tokens=10)
        long_text = "word " * 200
        result = comp.compress(long_text)
        assert result.compressed_tokens < result.original_tokens
        assert "compressed" in result.compressed.lower()

    def test_screen_description_compression(self):
        comp = ContextCompressor()
        desc = "\n".join([f"Element {i}: button" for i in range(30)])
        result = comp.compress_screen_description(desc, max_lines=10)
        assert "more elements" in result.compressed

    def test_conversation_compression(self):
        comp = ContextCompressor()
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        compressed = comp.compress_conversation(messages, max_turns=5)
        assert "earlier messages" in compressed

    def test_estimate_tokens(self):
        assert estimate_tokens("") >= 1
        assert estimate_tokens("hello") >= 1


# ============================================================
# RequestDeduplicator
# ============================================================
class TestRequestDeduplicator:
    def test_no_duplicate(self):
        dedup = RequestDeduplicator()
        result = dedup.check("tool", {"arg": "val"})
        assert not result.is_duplicate
        dedup.release(result.key)

    def test_duplicate_detection(self):
        dedup = RequestDeduplicator()
        r1 = dedup.check("tool", {"arg": "val"})
        r2 = dedup.check("tool", {"arg": "val"})
        assert r2.is_duplicate
        dedup.release(r1.key)

    def test_different_args(self):
        dedup = RequestDeduplicator()
        r1 = dedup.check("tool", {"arg": "a"})
        r2 = dedup.check("tool", {"arg": "b"})
        assert not r2.is_duplicate
        dedup.release(r1.key)
        dedup.release(r2.key)

    def test_complete_and_get(self):
        dedup = RequestDeduplicator()
        r = dedup.check("tool", {"arg": "val"})
        dedup.complete(r.key, "result")
        assert dedup.get_result(r.key) == "result"
        dedup.release(r.key)

    def test_expiry(self):
        dedup = RequestDeduplicator(window_ms=1)
        r = dedup.check("tool", {"arg": "val"})
        time.sleep(0.01)
        r2 = dedup.check("tool", {"arg": "val"})
        assert not r2.is_duplicate
        dedup.release(r.key)

    def test_clear(self):
        dedup = RequestDeduplicator()
        dedup.check("tool", {"arg": "val"})
        dedup.clear()
        assert dedup.active_count() == 0


# ============================================================
# FastPath
# ============================================================
class TestFastPath:
    def test_simple_open(self):
        fp = FastPath()
        result = fp.match("open notepad")
        assert result.matched
        assert result.tool_name == "openApplication"
        assert result.args["application"] == "notepad"

    def test_search(self):
        fp = FastPath()
        result = fp.match("search for python docs")
        assert result.matched
        assert result.tool_name == "searchWeb"

    def test_volume(self):
        fp = FastPath()
        result = fp.match("volume up")
        assert result.matched
        assert result.tool_name == "volumeUp"

    def test_time(self):
        fp = FastPath()
        result = fp.match("what time is it")
        assert result.matched
        assert result.tool_name == "currentDateTime"

    def test_no_match(self):
        fp = FastPath()
        result = fp.match("do something complex with multiple steps")
        assert not result.matched

    def test_custom_pattern(self):
        fp = FastPath()
        fp.add_pattern(r"^custom (\w+)$", "customTool",
                       lambda m: {"param": m.group(1)}, 0.9)
        result = fp.match("custom hello")
        assert result.matched
        assert result.tool_name == "customTool"
        assert result.args["param"] == "hello"

    def test_performance(self):
        fp = FastPath()
        start = time.perf_counter()
        for _ in range(1000):
            fp.match("open notepad")
        elapsed = (time.perf_counter() - start) * 1000
        assert elapsed < 100  # 1000 matches in < 100ms


# ============================================================
# PerformanceTelemetry
# ============================================================

class TestPerformanceTelemetry:
    def setup_method(self):
        PerformanceTelemetry.reset_singleton()

    def teardown_method(self):
        PerformanceTelemetry.reset_singleton()

    def test_record_and_report(self):
        tel = PerformanceTelemetry()
        report = tel.build_report(
            stage_latencies={"perception": 45.0},
            total_ms=100.0, cache_hit_rate=0.8,
            fast_path_hit=True, model_tier="fast",
        )
        assert report.total_ms == 100.0
        assert report.fast_path_hit
        assert "100.0ms" in report.summary

    def test_is_degraded(self):
        tel = PerformanceTelemetry()
        for _ in range(5):
            tel.build_report({}, 100.0, degraded=True)
        assert tel.is_degraded()

    def test_summary(self):
        tel = PerformanceTelemetry()
        tel.build_report({}, 50.0)
        s = tel.summary()
        assert s["total_requests"] == 1
        assert s["status"] in ("healthy", "degraded")

    def test_fast_path_ratio(self):
        tel = PerformanceTelemetry()
        tel.build_report({}, 10.0, fast_path_hit=True)
        tel.build_report({}, 10.0, fast_path_hit=False)
        assert tel.fast_path_ratio() == 0.5
