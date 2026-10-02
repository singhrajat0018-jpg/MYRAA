"""Stage 2.1 — Smoke test: run all 10 pipeline scenarios and print results."""
import time
import logging
import sys

logging.basicConfig(level=logging.WARNING)

from desktop_agent.core.application_container import ApplicationContainer

SCENARIOS = [
    ("A_conversation", "Hello Myraa"),
    ("B_knowledge", "What is Python?"),
    ("C_freshness", "Latest Python version"),
    ("D_router_match", "open YouTube"),
    ("E_desktop_tool", "take a screenshot"),
    ("F_vision", "What's on my screen?"),
    ("G_trading", "Analyze NIFTY"),
    ("H_design", "Design a futuristic bike"),
    ("I_coding", "Fix this project bug"),
    ("J_research", "Research the latest API docs"),
]

def main():
    print("Building container...")
    t_container = time.perf_counter()
    c = ApplicationContainer()
    container_ms = (time.perf_counter() - t_container) * 1000
    print(f"Container ready in {container_ms:.0f}ms\n")

    results = []
    for name, text in SCENARIOS:
        print(f"--- {name}: '{text}' ---")
        t0 = time.perf_counter()
        try:
            result = c.brain_engine.process(text)
            elapsed = (time.perf_counter() - t0) * 1000
            rtype = type(result).__name__
            success = result.success
            message = (result.message or "")[:150]
            actions = getattr(result, "actions", [])
            meta = getattr(result, "metadata", {})
            print(f"  type={rtype} success={success} time={elapsed:.0f}ms")
            print(f"  message={message}")
            print(f"  actions={actions}")
            results.append((name, text, elapsed, success, rtype, message, actions, meta))
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"  FAILED in {elapsed:.0f}ms: {type(e).__name__}: {e}")
            results.append((name, text, elapsed, False, "ERROR", str(e), [], {}))
        print()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Scenario':<20} {'Time(ms)':>10} {'Success':>8} {'Type':<20} {'Actions'}")
    print("-" * 80)
    for name, text, elapsed, success, rtype, msg, actions, meta in results:
        action_names = [a.get("tool", "") if isinstance(a, dict) else str(a) for a in actions] if actions else []
        print(f"{name:<20} {elapsed:>10.0f} {str(success):>8} {rtype:<20} {action_names}")
    print("-" * 80)

    total = sum(r[2] for r in results)
    successes = sum(1 for r in results if r[3])
    print(f"Total: {total:.0f}ms | {successes}/{len(results)} succeeded")

if __name__ == "__main__":
    main()
