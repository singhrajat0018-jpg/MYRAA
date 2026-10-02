"""MYRAA Stage 2 — Baseline Benchmark Suite.

Measures actual runtime performance across all scenarios.
Run BEFORE any optimization to establish the baseline.

Usage:
    python -m tests.benchmark_stage2
"""

from __future__ import annotations

import gc
import importlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkResult:
    name: str
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    iterations: int = 0
    extras: Dict[str, Any] = field(default_factory=dict)


def _percentile(sorted_vals: list, p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[-1]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def _benchmark(func, iterations: int = 100, warmup: int = 10) -> list:
    """Run func iterations times and return sorted latencies in ms."""
    for _ in range(warmup):
        try:
            func()
        except Exception:
            pass
    gc.collect()
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            func()
        except Exception:
            pass
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    return latencies


def _make_result(name: str, latencies: list, iterations: int = 0) -> BenchmarkResult:
    if not latencies:
        return BenchmarkResult(name=name, iterations=0)
    return BenchmarkResult(
        name=name,
        p50=_percentile(latencies, 50),
        p90=_percentile(latencies, 90),
        p95=_percentile(latencies, 95),
        p99=_percentile(latencies, 99),
        max_ms=max(latencies),
        mean_ms=sum(latencies) / len(latencies),
        iterations=len(latencies),
    )


def _get_process_stats() -> Dict[str, Any]:
    """Get current process memory and thread count."""
    try:
        import psutil
        proc = psutil.Process()
        mem = proc.memory_info()
        return {
            "rss_mb": mem.rss / (1024 * 1024),
            "vms_mb": mem.vms / (1024 * 1024),
            "threads": proc.num_threads(),
            "cpu_percent": proc.cpu_percent(interval=0),
        }
    except ImportError:
        return {"note": "psutil not installed"}


# ============================================================
# 1. IMPORT BENCHMARKS
# ============================================================

def bench_imports() -> List[BenchmarkResult]:
    """Measure import time for key modules."""
    results = []
    modules = [
        "desktop_agent",
        "desktop_agent.brain.router.task_router",
        "desktop_agent.brain.assistant_runtime",
        "desktop_agent.brain.super_brain.super_brain",
        "desktop_agent.brain.ai.ai_manager",
        "desktop_agent.brain.super_brain.capability_orchestrator",
        "desktop_agent.brain.super_brain.planner",
        "desktop_agent.brain.orchestrator.orchestrator",
        "desktop_agent.brain.execution_brain",
        "desktop_agent.brain.brain_engine",
        "desktop_agent.registry",
        "desktop_agent.main",
    ]
    for mod_name in modules:
        def _import(m=mod_name):
            if m in sys.modules:
                del sys.modules[m]
            importlib.import_module(m)

        latencies = _benchmark(_import, iterations=20, warmup=2)
        results.append(_make_result(f"import:{mod_name}", latencies, 20))
    return results


# ============================================================
# 2. TASKROUTER BENCHMARK
# ============================================================

def bench_task_router() -> List[BenchmarkResult]:
    """Measure TaskRouter latency for all task types."""
    from desktop_agent.brain.router.task_router import TaskRouter

    router = TaskRouter()
    scenarios = [
        ("conversation", "Hello Myraa"),
        ("conversation", "Hey Myra"),
        ("conversation", "Good morning"),
        ("conversation", "How are you?"),
        ("conversation", "Thanks"),
        ("conversation", "Who are you?"),
        ("conversation", "What can you do?"),
        ("knowledge", "What is Python?"),
        ("knowledge", "What is recursion?"),
        ("knowledge", "Explain OOP."),
        ("knowledge", "What is a CPU?"),
        ("freshness", "Latest Python version"),
        ("freshness", "Current weather"),
        ("browser", "Open YouTube"),
        ("desktop", "Open Notepad"),
        ("vision", "What is on my screen?"),
        ("trading", "Analyze NIFTY"),
        ("file", "Create a file called test.txt"),
        ("design", "Design a futuristic bike"),
        ("coding", "Fix this project bug"),
    ]

    results = []
    for category, text in scenarios:
        latencies = _benchmark(lambda t=text: router.route(t), iterations=500, warmup=50)
        results.append(_make_result(f"router:{category}:{text[:30]}", latencies, 500))

    # Aggregate by category
    cats: Dict[str, list] = {}
    for r in results:
        cat = r.name.split(":")[1]
        cats.setdefault(cat, []).append(r)

    for cat, cat_results in cats.items():
        all_latencies = []
        for r in cat_results:
            all_latencies.extend([r.mean_ms] * r.iterations)
        all_latencies.sort()
        results.append(_make_result(f"router:{cat}:aggregate", all_latencies, len(all_latencies)))

    return results


# ============================================================
# 3. ASSISTANT RUNTIME FAST-PATH BENCHMARK
# ============================================================

def bench_assistant_runtime_fast_path() -> List[BenchmarkResult]:
    """Measure the full fast-path (classify → respond) for no-tool requests."""
    from desktop_agent.brain.assistant_runtime import (
        AssistantRuntime,
        AssistantRequest,
        InputType,
    )
    from desktop_agent.brain.router.task_router import TaskRouter

    runtime = AssistantRuntime(task_router=TaskRouter())
    scenarios = [
        ("conversation", "Hello Myraa"),
        ("conversation", "Hey Myra"),
        ("knowledge", "What is Python?"),
        ("knowledge", "Explain recursion."),
    ]

    results = []
    for category, text in scenarios:
        def _run(t=text):
            req = AssistantRequest(
                user_input=t,
                input_type=InputType.VOICE if "voice" in category else InputType.TEXT,
            )
            return runtime.handle(req)

        latencies = _benchmark(_run, iterations=200, warmup=20)
        resp = _run()
        results.append(_make_result(f"runtime:{category}:{text[:30]}", latencies, 200))
        results[-1].extras["decision"] = getattr(resp, "decision", "")
        results[-1].extras["route"] = getattr(resp, "route", "")
    return results


# ============================================================
# 4. SUPERBRAIN INTEGRATION BENCHMARK (tool-required paths)
# ============================================================

def bench_superbrain() -> List[BenchmarkResult]:
    """Measure SuperBrain pipeline for tool-required requests."""
    from desktop_agent.core.application_container import ApplicationContainer

    try:
        container = ApplicationContainer()
        sb = container.super_brain
    except Exception as e:
        return [BenchmarkResult(name="superbrain:error", extras={"error": str(e)})]

    scenarios = [
        ("browser", "Open YouTube"),
        ("desktop", "Open Notepad"),
        ("vision", "What is on my screen?"),
        ("trading", "Analyze NIFTY options"),
        ("design", "Design a futuristic bike"),
        ("coding", "Fix this project bug"),
    ]

    results = []
    for category, text in scenarios:
        def _run(t=text):
            return sb.process(user_request=t, request_id=f"bench-{category}")

        latencies = _benchmark(_run, iterations=20, warmup=3)
        results.append(_make_result(f"superbrain:{category}", latencies, 20))
    return results


# ============================================================
# 5. CONTEXT SIZE AUDIT
# ============================================================

def audit_context_sizes() -> Dict[str, Any]:
    """Measure the size of context passed to LLM for different request types."""
    from desktop_agent.brain.router.task_router import TaskRouter
    from desktop_agent.brain.super_brain.goal import Goal

    router = TaskRouter()
    audit = {}

    scenarios = [
        ("conversation", "Hello Myraa"),
        ("knowledge", "What is Python?"),
        ("browser", "Open YouTube"),
        ("vision", "What is on my screen?"),
        ("trading", "Analyze NIFTY"),
        ("research", "Research quantum computing"),
    ]

    for category, text in scenarios:
        routing = router.route(text)
        audit[category] = {
            "task_type": routing.task_type.name,
            "tools_required": routing.tools_required,
            "input_length": len(text),
            "tool_names": routing.tool_names,
        }

    return audit


# ============================================================
# 6. TOOL SCHEMA SIZE AUDIT
# ============================================================

def audit_tool_schemas() -> Dict[str, Any]:
    """Measure tool schema size exposed to different request types."""
    try:
        from desktop_agent.registry import TOOLS
        tool_count = len(TOOLS)
        tool_names = list(TOOLS.keys())
    except Exception:
        tool_count = 0
        tool_names = []

    return {
        "total_registered_tools": tool_count,
        "tool_names": tool_names,
        "estimated_schema_tokens": tool_count * 50,  # rough estimate
    }


# ============================================================
# 7. MEMORY / PROCESS BENCHMARK
# ============================================================

def bench_memory() -> Dict[str, Any]:
    """Measure process memory and thread state."""
    gc.collect()
    before = _get_process_stats()

    # Import everything
    from desktop_agent.core.application_container import ApplicationContainer
    try:
        container = ApplicationContainer()
    except Exception:
        pass

    gc.collect()
    after = _get_process_stats()

    return {
        "before_import": before,
        "after_container": after,
    }


# ============================================================
# 8. EVENT BUS AUDIT
# ============================================================

def audit_eventbus() -> Dict[str, Any]:
    """Measure EventBus listener count and event throughput."""
    try:
        from desktop_agent.brain.blackboard.working_blackboard import Blackboard
        bb = Blackboard()
        listener_count = len(bb._listeners) if hasattr(bb, "_listeners") else "N/A"
    except Exception as e:
        listener_count = f"error: {e}"

    return {
        "listener_count": listener_count,
    }


# ============================================================
# 9. CONCURRENCY AUDIT
# ============================================================

def audit_concurrency() -> Dict[str, Any]:
    """Measure threading state and lock contention."""
    active_threads = threading.active_count()
    thread_names = [t.name for t in threading.enumerate()]

    # Check for common lock patterns
    lock_info = {}
    try:
        from desktop_agent.brain.assistant_runtime import AssistantRuntime
        import inspect
        source = inspect.getsource(AssistantRuntime)
        lock_count = source.count("Lock") + source.count("RLock")
        lock_info["assistant_runtime_locks"] = lock_count
    except Exception:
        pass

    return {
        "active_threads": active_threads,
        "thread_names": thread_names[:20],
        "locks": lock_info,
    }


# ============================================================
# 10. FILE I/O AUDIT
# ============================================================

def audit_file_io() -> Dict[str, Any]:
    """Measure file I/O patterns in memory persistence."""
    import glob as glob_mod

    data_dir = os.path.join(os.path.dirname(__file__), "..", "runtime", "memory")
    json_files = glob_mod.glob(os.path.join(data_dir, "*.json"))

    file_info = []
    for fp in json_files:
        try:
            size = os.path.getsize(fp)
            file_info.append({"path": os.path.basename(fp), "size_bytes": size})
        except Exception:
            pass

    return {
        "memory_files": len(json_files),
        "files": file_info,
    }


# ============================================================
# MAIN
# ============================================================

def run_all_benchmarks():
    """Run all benchmarks and produce the baseline report."""
    print("=" * 70)
    print("MYRAA STAGE 2 — BASELINE BENCHMARK")
    print("=" * 70)

    all_results: List[BenchmarkResult] = {}
    all_audits: Dict[str, Any] = {}

    # 1. Import benchmarks
    print("\n[1/10] Import benchmarks...")
    import_results = bench_imports()
    for r in import_results:
        all_results[r.name] = r
        print(f"  {r.name}: P50={r.p50:.2f}ms P99={r.p99:.2f}ms")

    # 2. TaskRouter benchmarks
    print("\n[2/10] TaskRouter benchmarks...")
    router_results = bench_task_router()
    for r in router_results:
        all_results[r.name] = r
        if "aggregate" in r.name:
            print(f"  {r.name}: P50={r.p50:.3f}ms P99={r.p99:.3f}ms")

    # 3. AssistantRuntime fast-path
    print("\n[3/10] AssistantRuntime fast-path benchmarks...")
    runtime_results = bench_assistant_runtime_fast_path()
    for r in runtime_results:
        all_results[r.name] = r
        print(f"  {r.name}: P50={r.p50:.2f}ms P99={r.p99:.2f}ms decision={r.extras.get('decision', '')}")

    # 4. SuperBrain pipeline
    print("\n[4/10] SuperBrain pipeline benchmarks...")
    sb_results = bench_superbrain()
    for r in sb_results:
        all_results[r.name] = r
        if r.iterations > 0:
            print(f"  {r.name}: P50={r.p50:.1f}ms P99={r.p99:.1f}ms")

    # 5. Context size audit
    print("\n[5/10] Context size audit...")
    all_audits["context_sizes"] = audit_context_sizes()

    # 6. Tool schema audit
    print("\n[6/10] Tool schema audit...")
    all_audits["tool_schemas"] = audit_tool_schemas()
    print(f"  Total tools: {all_audits['tool_schemas']['total_registered_tools']}")

    # 7. Memory audit
    print("\n[7/10] Memory / process audit...")
    all_audits["memory"] = bench_memory()

    # 8. EventBus audit
    print("\n[8/10] EventBus audit...")
    all_audits["eventbus"] = audit_eventbus()

    # 9. Concurrency audit
    print("\n[9/10] Concurrency audit...")
    all_audits["concurrency"] = audit_concurrency()
    print(f"  Active threads: {all_audits['concurrency']['active_threads']}")

    # 10. File I/O audit
    print("\n[10/10] File I/O audit...")
    all_audits["file_io"] = audit_file_io()

    # Print summary
    print("\n" + "=" * 70)
    print("BASELINE SUMMARY")
    print("=" * 70)

    print("\n--- Import Latencies ---")
    for name, r in sorted(all_results.items()):
        if name.startswith("import:"):
            print(f"  {name.replace('import:desktop_agent.', '')}: P50={r.p50:.1f}ms P99={r.p99:.1f}ms")

    print("\n--- Fast-Path Latencies (CONVERSATION / KNOWLEDGE) ---")
    for name, r in sorted(all_results.items()):
        if name.startswith("runtime:"):
            print(f"  {name}: P50={r.p50:.2f}ms P99={r.p99:.2f}ms")

    print("\n--- SuperBrain Pipeline Latencies ---")
    for name, r in sorted(all_results.items()):
        if name.startswith("superbrain:"):
            print(f"  {name}: P50={r.p50:.1f}ms P99={r.p99:.1f}ms")

    print("\n--- TaskRouter Aggregate ---")
    for name, r in sorted(all_results.items()):
        if "aggregate" in name:
            print(f"  {name}: P50={r.p50:.3f}ms P99={r.p99:.3f}ms")

    print("\n--- Audit Results ---")
    print(f"  Tools registered: {all_audits['tool_schemas']['total_registered_tools']}")
    print(f"  Active threads: {all_audits['concurrency']['active_threads']}")
    print(f"  Memory files: {all_audits['file_io']['memory_files']}")

    # Save full report
    report_path = os.path.join(os.path.dirname(__file__), "..", "runtime", "benchmark_baseline.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "benchmarks": {},
        "audits": all_audits,
    }
    for name, r in all_results.items():
        report["benchmarks"][name] = {
            "p50": r.p50,
            "p90": r.p90,
            "p95": r.p95,
            "p99": r.p99,
            "max_ms": r.max_ms,
            "mean_ms": r.mean_ms,
            "iterations": r.iterations,
            "extras": r.extras,
        }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to: {report_path}")

    return report


if __name__ == "__main__":
    run_all_benchmarks()
