"""Phase E: Ultra-Fast Execution Engine — Performance Infrastructure.

Uses lazy imports to avoid creating thread pools at import time.
"""

def __getattr__(name):
    if name == "LatencyTracker":
        from .latency_tracker import LatencyTracker
        return LatencyTracker
    if name == "LatencyBudget":
        from .latency_tracker import LatencyBudget
        return LatencyBudget
    if name == "ContextCache":
        from .context_cache import ContextCache
        return ContextCache
    if name == "CacheTier":
        from .context_cache import CacheTier
        return CacheTier
    if name == "ParallelExecutor":
        from .parallel_executor import ParallelExecutor
        return ParallelExecutor
    if name == "ExecutionPool":
        from .parallel_executor import ExecutionPool
        return ExecutionPool
    if name == "StreamProcessor":
        from .streaming import StreamProcessor
        return StreamProcessor
    if name == "StreamChunk":
        from .streaming import StreamChunk
        return StreamChunk
    if name == "ContextCompressor":
        from .compression import ContextCompressor
        return ContextCompressor
    if name == "CompressionResult":
        from .compression import CompressionResult
        return CompressionResult
    if name == "RequestDeduplicator":
        from .dedup import RequestDeduplicator
        return RequestDeduplicator
    if name == "DedupResult":
        from .dedup import DedupResult
        return DedupResult
    if name == "FastPath":
        from .fast_path import FastPath
        return FastPath
    if name == "FastPathResult":
        from .fast_path import FastPathResult
        return FastPathResult
    if name == "PerformanceTelemetry":
        from .telemetry import PerformanceTelemetry
        return PerformanceTelemetry
    if name == "LatencyReport":
        from .telemetry import LatencyReport
        return LatencyReport
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LatencyTracker", "LatencyBudget",
    "ContextCache", "CacheTier",
    "ParallelExecutor", "ExecutionPool",
    "StreamProcessor", "StreamChunk",
    "ContextCompressor", "CompressionResult",
    "RequestDeduplicator", "DedupResult",
    "FastPath", "FastPathResult",
    "PerformanceTelemetry", "LatencyReport",
]
