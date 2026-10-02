"""Stage 2.1 — Full E2E Pipeline Benchmark."""
import time
import logging
import statistics
import json

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

def run_scenario(c, text, runs=2):
    """Run a scenario and return timing + result."""
    timings = []
    last_result = None
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            result = c.brain_engine.process(text)
            elapsed = (time.perf_counter() - t0) * 1000
            timings.append(elapsed)
            last_result = result
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            timings.append(elapsed)
            last_result = type('Error', (), {'success': False, 'message': str(e), 'metadata': {'route': 'ERROR'}})()
    return timings, last_result

def main():
    print("Building container...")
    t0 = time.perf_counter()
    c = ApplicationContainer()
    container_ms = (time.perf_counter() - t0) * 1000
    print(f"Container ready in {container_ms:.0f}ms\n")

    # Warm up (first call may be slower)
    c.brain_engine.process("test")

    results = []
    for name, text in SCENARIOS:
        timings, result = run_scenario(c, text, runs=2)
        p50 = statistics.median(timings)
        route = getattr(result, 'metadata', {}).get('route', '?')
        success = getattr(result, 'success', False)
        message = (getattr(result, 'message', '') or '')[:100]
        actions = getattr(result, 'actions', [])
        print(f"{name:<22} P50={p50:>8.0f}ms  route={route:<20} success={success}")
        if message:
            print(f"{'':22} msg={message[:80]}")
        results.append({
            'name': name,
            'text': text,
            'p50': p50,
            'route': route,
            'success': success,
            'message': message,
            'actions': actions,
        })

    # Save results
    with open('runtime/stage2_1_benchmark.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary table
    print("\n" + "=" * 90)
    print(f"{'Scenario':<22} {'P50(ms)':>10} {'Route':<22} {'Success':>7} {'Message'}")
    print("-" * 90)
    for r in results:
        print(f"{r['name']:<22} {r['p50']:>10.0f} {r['route']:<22} {str(r['success']):>7} {r['message'][:30]}")
    print("-" * 90)
    total = sum(r['p50'] for r in results)
    print(f"{'Total P50':<22} {total:>10.0f}")

if __name__ == "__main__":
    main()
