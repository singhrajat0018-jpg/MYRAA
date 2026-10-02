"""MYRAA Stage 2 — Focused Baseline Benchmark (no SuperBrain pipeline)."""

from __future__ import annotations

import gc
import importlib
import json
import os
import sys
import threading
import time
from typing import Any, Dict, List


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def _bench(func, iters=500, warmup=50):
    for _ in range(warmup):
        try:
            func()
        except Exception:
            pass
    gc.collect()
    lats = []
    for _ in range(iters):
        t0 = time.perf_counter()
        try:
            func()
        except Exception:
            pass
        lats.append((time.perf_counter() - t0) * 1000)
    lats.sort()
    return lats


def _stats(lats):
    if not lats:
        return {}
    return {
        "p50": round(_percentile(lats, 50), 4),
        "p90": round(_percentile(lats, 90), 4),
        "p95": round(_percentile(lats, 95), 4),
        "p99": round(_percentile(lats, 99), 4),
        "max": round(max(lats), 4),
        "mean": round(sum(lats) / len(lats), 4),
        "n": len(lats),
    }


def _mem():
    try:
        import psutil
        p = psutil.Process()
        m = p.memory_info()
        return {"rss_mb": round(m.rss / 1048576, 1), "threads": p.num_threads()}
    except ImportError:
        return {}


def main():
    report: Dict[str, Any] = {}
    gc.collect()

    # ── 1. IMPORT LATENCIES ──
    print("=== IMPORT LATENCIES ===")
    report["imports"] = {}
    mods = [
        "desktop_agent",
        "desktop_agent.brain.router.task_router",
        "desktop_agent.brain.assistant_runtime",
        "desktop_agent.brain.super_brain.super_brain",
        "desktop_agent.brain.ai.ai_manager",
        "desktop_agent.brain.super_brain.capability_orchestrator",
        "desktop_agent.brain.super_brain.planner",
        "desktop_agent.brain.execution_brain",
        "desktop_agent.brain.brain_engine",
        "desktop_agent.registry",
    ]
    for m in mods:
        short = m.replace("desktop_agent.", "")
        def _imp(mod=m):
            sys.modules.pop(mod, None)
            importlib.import_module(mod)
        lats = _bench(_imp, iters=10, warmup=1)
        s = _stats(lats)
        report["imports"][short] = s
        print(f"  {short}: P50={s.get('p50',0):.2f}ms P99={s.get('p99',0):.2f}ms")

    # ── 2. TASKROUTER LATENCIES ──
    print("\n=== TASKROUTER LATENCIES ===")
    from desktop_agent.brain.router.task_router import TaskRouter
    router = TaskRouter()
    report["router"] = {}
    scenarios = {
        "conversation_hello": "Hello Myraa",
        "conversation_hey": "Hey Myra",
        "conversation_morning": "Good morning",
        "conversation_howareyou": "How are you?",
        "conversation_thanks": "Thanks",
        "conversation_whoru": "Who are you?",
        "conversation_whatcanyoudo": "What can you do?",
        "knowledge_python": "What is Python?",
        "knowledge_recursion": "What is recursion?",
        "knowledge_oop": "Explain OOP.",
        "freshness_latest": "Latest Python version",
        "freshness_weather": "Current weather",
        "browser_youtube": "Open YouTube",
        "desktop_notepad": "Open Notepad",
        "vision_screen": "What is on my screen?",
        "trading_nifty": "Analyze NIFTY",
        "file_create": "Create a file called test.txt",
        "design_bike": "Design a futuristic bike",
        "coding_fix": "Fix this project bug",
    }
    for name, text in scenarios.items():
        lats = _bench(lambda t=text: router.route(t), iters=500, warmup=50)
        s = _stats(lats)
        report["router"][name] = s
    # Print aggregates by category
    cats = {}
    for name, s in report["router"].items():
        cat = name.split("_")[0]
        cats.setdefault(cat, []).append(s["mean"])
    for cat, means in cats.items():
        avg = sum(means) / len(means) if means else 0
        print(f"  {cat}: avg_mean={avg:.4f}ms (n={len(means)} scenarios)")

    # ── 3. ASSISTANT RUNTIME FAST PATH ──
    print("\n=== ASSISTANT RUNTIME FAST PATH ===")
    from desktop_agent.brain.assistant_runtime import (
        AssistantRuntime, AssistantRequest, InputType,
    )
    runtime = AssistantRuntime(task_router=TaskRouter())
    report["fast_path"] = {}
    fast_scenarios = {
        "conversation": "Hello Myraa",
        "knowledge": "What is Python?",
    }
    for name, text in fast_scenarios.items():
        def _run(t=text):
            req = AssistantRequest(user_input=t, input_type=InputType.TEXT)
            return runtime.handle(req)
        lats = _bench(_run, iters=200, warmup=20)
        s = _stats(lats)
        resp = _run()
        s["decision"] = getattr(resp, "decision", "")
        s["route"] = getattr(resp, "route", "")
        report["fast_path"][name] = s
        print(f"  {name}: P50={s['p50']:.2f}ms P99={s['p99']:.2f}ms decision={s['decision']}")

    # ── 4. IMPORT TIME: TOTAL ──
    print("\n=== TOTAL IMPORT TIME ===")
    gc.collect()
    t0 = time.perf_counter()
    # Reload key modules
    for m in ["desktop_agent.brain.router.task_router",
              "desktop_agent.brain.assistant_runtime"]:
        sys.modules.pop(m, None)
        importlib.import_module(m)
    total_import = (time.perf_counter() - t0) * 1000
    report["total_import_ms"] = round(total_import, 2)
    print(f"  Total import: {total_import:.2f}ms")

    # ── 5. MEMORY ──
    print("\n=== MEMORY ===")
    gc.collect()
    report["memory"] = _mem()
    print(f"  RSS: {report['memory'].get('rss_mb', '?')} MB, Threads: {report['memory'].get('threads', '?')}")

    # ── 6. THREAD AUDIT ──
    print("\n=== THREAD AUDIT ===")
    threads = [(t.name, t.is_alive()) for t in threading.enumerate()]
    report["threads"] = {"count": len(threads), "names": [t[0] for t in threads[:20]]}
    print(f"  Active threads: {len(threads)}")
    for name, alive in threads[:10]:
        print(f"    {'[alive]' if alive else '[dead]'} {name}")

    # ── 7. TOOL SCHEMA SIZE ──
    print("\n=== TOOL SCHEMA SIZE ===")
    try:
        from desktop_agent.registry import TOOLS
        tool_count = len(TOOLS)
        tool_names = sorted(TOOLS.keys())
    except Exception:
        tool_count = 0
        tool_names = []
    report["tools"] = {"count": tool_count, "names": tool_names}
    print(f"  Registered tools: {tool_count}")

    # ── 8. EVENTBUS ──
    print("\n=== EVENTBUS ===")
    try:
        from desktop_agent.brain.blackboard.working_blackboard import Blackboard
        bb = Blackboard()
        n_listeners = len(bb._listeners) if hasattr(bb, "_listeners") else "N/A"
    except Exception as e:
        n_listeners = f"error: {e}"
    report["eventbus"] = {"listeners": n_listeners}
    print(f"  Listeners: {n_listeners}")

    # ── 9. FILE I/O ──
    print("\n=== FILE I/O ===")
    import glob as g
    mem_dir = os.path.join(os.path.dirname(__file__), "..", "runtime", "memory")
    jsons = g.glob(os.path.join(mem_dir, "*.json"))
    file_info = []
    for fp in jsons:
        try:
            sz = os.path.getsize(fp)
            file_info.append({"name": os.path.basename(fp), "bytes": sz})
        except Exception:
            pass
    report["file_io"] = {"memory_files": len(jsons), "files": file_info}
    print(f"  Memory files: {len(jsons)}")
    for fi in file_info:
        print(f"    {fi['name']}: {fi['bytes']:,} bytes")

    # Save report
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "runtime"), exist_ok=True)
    path = os.path.join(os.path.dirname(__file__), "..", "runtime", "benchmark_baseline.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {path}")


if __name__ == "__main__":
    main()
