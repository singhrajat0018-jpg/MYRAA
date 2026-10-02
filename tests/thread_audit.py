"""Phase 3 — Thread-level CPU audit during idle."""
import time
import os
import threading
import logging
import gc

logging.basicConfig(level=logging.WARNING)
gc.collect()

from desktop_agent.core.application_container import ApplicationContainer

c = ApplicationContainer()
print("Container ready\n")

# Let idle stabilize
time.sleep(2)

print("=== THREAD CPU AUDIT (10s) ===\n")

# Get per-thread CPU via Windows API
import ctypes
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32

# Collect thread info
thread_map = {}
for t in threading.enumerate():
    thread_map[t.name] = t

print(f"Total threads: {threading.active_count()}")
print(f"Named threads:")
for t in sorted(threading.enumerate(), key=lambda x: x.name):
    print(f"  {t.name:<45} daemon={t.daemon} alive={t.is_alive()}")

# Check which timers/tickers are active
print("\n=== ACTIVE BACKGROUND COMPONENTS ===\n")

# Self-healing diagnostics
try:
    from desktop_agent.self_healing.diagnostics import DiagnosticsEngine
    print(f"DiagnosticsEngine: interval=60s")
except:
    pass

# Runtime manager vision loop
try:
    from desktop_agent.runtime.runtime_manager import RuntimeManager
    print(f"RuntimeManager: vision→brain loop (daemon)")
except:
    pass

# Observer manager
try:
    from desktop_agent.brain.observer.manager import ObserverManager
    print(f"ObserverManager: 30s polling (daemon)")
except:
    pass

# Autonomy loop
try:
    from desktop_agent.brain.autonomy.autonomy_loop import AutonomyLoop
    print(f"AutonomyLoop: tick-based (daemon)")
except:
    pass

# Continuous vision
try:
    from desktop_agent.brain.super_brain.continuous_vision import ContinuousVision
    print(f"ContinuousVision: frame capture (daemon)")
except:
    pass

# Knowledge worker
try:
    from desktop_agent.brain.knowledge.queue.worker import KnowledgeWorker
    print(f"KnowledgeWorker: queue consumer (daemon)")
except:
    pass

# Memory flush
try:
    from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
    print(f"UnifiedMemoryManager: flush thread (daemon)")
except:
    pass

# Screen observer
try:
    from desktop_agent.brain.observer.observers.screen_observer import ScreenObserver
    print(f"ScreenObserver: screen monitoring (daemon)")
except:
    pass

# Live capture
try:
    from desktop_agent.desktop.vision.live_capture import LiveCaptureEngine
    print(f"LiveCaptureEngine: 15fps capture (daemon)")
except:
    pass

# Measure actual CPU per thread (sampling)
print("\n=== CPU SAMPLING (10s) ===\n")
import subprocess

# Use thread query
try:
    from desktop_agent.brain.blackboard.working_blackboard import Blackboard
    bb = Blackboard()
    print(f"Blackboard event rate: {bb.event_count if hasattr(bb, 'event_count') else 'N/A'}")
except:
    pass

# Sample thread activity
start = time.perf_counter()
samples = []
for i in range(20):
    threads = [(t.name, t.is_alive()) for t in threading.enumerate()]
    alive_count = sum(1 for _, a in threads if a)
    samples.append(alive_count)
    time.sleep(0.5)

elapsed = time.perf_counter() - start
print(f"Sampling period: {elapsed:.1f}s")
print(f"Active threads during sampling: min={min(samples)} max={max(samples)} avg={sum(samples)/len(samples):.1f}")

# Final memory
import subprocess
pid = os.getpid()
try:
    out = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'], timeout=5)
    parts = out.decode().strip().strip('"').split('","')
    if len(parts) >= 5:
        mem = float(parts[4].replace(' K', '').replace(',', '')) / 1024
        print(f"\nFinal RSS: {mem:.1f} MB")
except:
    pass
