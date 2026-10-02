"""Instrumented pipeline trace for 'Hello Myraa'."""
import time
import logging
logging.basicConfig(level=logging.WARNING)

from desktop_agent.core.application_container import ApplicationContainer

c = ApplicationContainer()
print("Container ready\n")

text = "Hello Myraa"
t_start = time.perf_counter()

# Step 1: resolve_input
t0 = time.perf_counter()
resolved = c.brain_engine._resolve_input(text)
t1 = time.perf_counter()
print(f"[STEP 1] _resolve_input: {(t1-t0)*1000:.1f}ms  resolved='{resolved}'")

# Step 2: semantic parse
t2 = time.perf_counter()
semantic_task = c.brain_engine.semantic_parser.parse(resolved, None)
t3 = time.perf_counter()
print(f"[STEP 2] semantic_parser.parse: {(t3-t2)*1000:.1f}ms  intent={semantic_task.intent}")

# Step 3: response route
t4 = time.perf_counter()
response_route = c.brain_engine.response_router.route(semantic_task)
t5 = time.perf_counter()
print(f"[STEP 3] response_router.route: {(t5-t4)*1000:.1f}ms  route={response_route.route.value}")

# Step 4: memory retrieval
t6 = time.perf_counter()
memory_result = c.brain_engine.memory_retrieval.resolve(resolved, c.brain_engine.working_memory)
t7 = time.perf_counter()
print(f"[STEP 4] memory_retrieval.resolve: {(t7-t6)*1000:.1f}ms  handled={memory_result.handled}")

total = (time.perf_counter()-t_start)*1000
print(f"\n[TOTAL] pipeline: {total:.1f}ms")
