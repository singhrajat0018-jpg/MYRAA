"""Quick test: conversational fast path latency."""
import time
import logging
logging.basicConfig(level=logging.WARNING)

from desktop_agent.core.application_container import ApplicationContainer

c = ApplicationContainer()
print("Container ready\n")

tests = [
    "Hello Myraa",
    "hey myraa",
    "thank you",
    "What is Python?",
]

for text in tests:
    t0 = time.perf_counter()
    r = c.brain_engine.process(text)
    elapsed = (time.perf_counter() - t0) * 1000
    msg = (r.message or "")[:80]
    route = r.metadata.get("route", "?")
    print(f"  {elapsed:>8.0f}ms | route={route:<20} | {text}")
    if msg:
        print(f"           | msg={msg}")
