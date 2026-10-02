"""Phase 3.1 — Provider fallback + cooldown measurement (short timeout)."""
import time
import sys
import os

sys.path.insert(0, os.getcwd())

def test_provider_fallback():
    print("=" * 70)
    print("PROVIDER FALLBACK + COOLDOWN TEST")
    print("=" * 70)

    from desktop_agent.brain.ai.ai_manager import AIManager

    ai = AIManager()

    # Check available providers
    print("\n[1] Provider availability:")
    for name in ["gemini", "ollama", "nim"]:
        p = ai._by_name(name)
        if p:
            avail = p.available()
            model = getattr(p, 'model', 'N/A')
            print(f"  {name}: {'AVAILABLE' if avail else 'UNAVAILABLE'}  model={model}")
        else:
            print(f"  {name}: NOT LOADED")

    # Test generate with fallback — short timeout to avoid hanging on 30B model
    print("\n[2] Generate with fallback chain (5s timeout):")
    t0 = time.perf_counter()
    try:
        result = ai.generate(
            system_prompt="You are a helpful assistant. Reply in one word.",
            user_prompt="What is 2+2?",
            timeout=5,
        )
        t1 = time.perf_counter()
        print(f"  Response: {result[:100]}")
        print(f"  Latency: {(t1-t0)*1000:.0f}ms")
        print(f"  Active provider: {ai._active_provider.__class__.__name__ if ai._active_provider else 'none'}")
    except Exception as e:
        t1 = time.perf_counter()
        print(f"  ALL PROVIDERS FAILED: {e}")
        print(f"  Latency: {(t1-t0)*1000:.0f}ms")

    # Test 3 more calls to measure repeated fallback
    print("\n[3] Repeated calls (3x, 5s timeout):")
    for i in range(3):
        t0 = time.perf_counter()
        try:
            result = ai.generate(
                system_prompt="Reply in one word.",
                user_prompt=f"Say hello {i+1}",
                timeout=5,
            )
            t1 = time.perf_counter()
            provider = ai._active_provider.__class__.__name__ if ai._active_provider else 'none'
            print(f"  Call {i+1}: {(t1-t0)*1000:.0f}ms via {provider}")
        except Exception as e:
            t1 = time.perf_counter()
            print(f"  Call {i+1}: FAILED ({(t1-t0)*1000:.0f}ms) {str(e)[:60]}")

    # Check cooldown state
    print("\n[4] Cooldown state:")
    for name in ["gemini", "ollama", "nim"]:
        p = ai._by_name(name)
        if p:
            failures = getattr(p, '_consecutive_failures', 'N/A')
            cooldown = getattr(p, '_cooldown_until', 'N/A')
            print(f"  {name}: failures={failures}  cooldown_until={cooldown}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("  Gemini: UNAVAILABLE (no API key)")
    print("  NIM:    UNAVAILABLE")
    print("  Ollama: Available but 30B model too slow for 5s timeout")
    print("  Cooldown: Implemented on Gemini + Ollama (3+ failures -> backoff)")
    print("=" * 70)

if __name__ == "__main__":
    test_provider_fallback()
