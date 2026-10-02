"""Test Desktop Agent startup to isolate the hang."""
import sys
import time

print("=" * 60)
print("TESTING DESKTOP AGENT STARTUP")
print("=" * 60)

print("\n1. Testing module import...")
t0 = time.time()
from desktop_agent.main import app
print(f"   + Import took {time.time() - t0:.2f}s")

print("\n2. Testing lifespan startup...")
import asyncio
from contextlib import asynccontextmanager

async def test_lifespan():
    print("   Starting lifespan context...")
    t0 = time.time()

    # Get the lifespan function
    lifespan_func = app.router.lifespan_context

    try:
        async with lifespan_func(app) as state:
            elapsed = time.time() - t0
            print(f"   + Lifespan startup completed in {elapsed:.2f}s")
            print(f"   Waiting 2 seconds to verify stability...")
            await asyncio.sleep(2)
            print(f"   + Stable")
    except Exception as e:
        print(f"   x Lifespan startup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

print("\n3. Running lifespan test...")
asyncio.run(test_lifespan())

print("\n" + "=" * 60)
print("+ ALL TESTS PASSED")
print("=" * 60)
