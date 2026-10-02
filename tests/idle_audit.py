"""Phase 3 — Idle resource audit: measure CPU/RAM/threads/background activity."""
import time
import os
import threading
import logging
import json
import ctypes

logging.basicConfig(level=logging.WARNING)

# Force GC before measurement
import gc
gc.collect()

t0 = time.perf_counter()
from desktop_agent.core.application_container import ApplicationContainer
import_time = (time.perf_counter() - t0) * 1000
print(f"Container import+build: {import_time:.0f}ms")

# Get baseline process info
proc = os.times()
pid = os.getpid()

def get_process_memory():
    """Get RSS in MB via Windows API."""
    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if handle:
            try:
                import ctypes.wintypes
                mem_info = ctypes.wintypes.SIZE_T()
                kernel32.GetProcessWorkingSetSize(handle, ctypes.byref(ctypes.wintypes.SIZE_T()), ctypes.byref(mem_info))
                # Alternative: use psutil-style
            except:
                pass
    except:
        pass
    # Fallback: use tasklist
    import subprocess
    try:
        out = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'], timeout=5)
        parts = out.decode().strip().strip('"').split('","')
        if len(parts) >= 5:
            return float(parts[4].replace(' K', '').replace(',', '')) / 1024
    except:
        pass
    return 0.0

def get_thread_count():
    return threading.active_count()

def list_threads():
    """List non-daemon/non-main threads."""
    threads = []
    for t in threading.enumerate():
        if t.daemon and t != threading.main_thread():
            continue
        if t == threading.main_thread():
            continue
        threads.append((t.name, t.daemon, t.is_alive()))
    return threads

# Build container
c = ApplicationContainer()

# Measure idle state
print("\n=== IDLE RESOURCE AUDIT ===\n")
print("Waiting 3s for idle stabilization...")
time.sleep(3)

# Take measurements
mem_mb = get_process_memory()
n_threads = get_thread_count()
all_threads = list_threads()

print(f"PID: {pid}")
print(f"RSS Memory: {mem_mb:.1f} MB")
print(f"Thread count: {n_threads}")
print(f"Active threads (non-daemon): {len(all_threads)}")
for name, daemon, alive in all_threads[:30]:
    print(f"  [{name}] daemon={daemon} alive={alive}")

# Check for background timers
print("\n--- Background Activity Detection ---")

# Check for running timers
import sched
print(f"Python sched queue: {len(sched._scheduler._queue) if hasattr(sched, '_scheduler') else 'N/A'}")

# Check asyncio loops
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        print("Asyncio loop: RUNNING")
    else:
        print("Asyncio loop: stopped")
except:
    print("Asyncio loop: N/A")

# Check background threads doing work
print(f"\nThread enumeration after 3s idle:")
for t in sorted(threading.enumerate(), key=lambda x: x.name):
    if t != threading.main_thread():
        print(f"  {t.name} daemon={t.daemon} alive={t.is_alive()}")

# Monitor for 5 seconds
print("\n--- Monitoring CPU for 5s ---")
times = []
for i in range(5):
    t_start = time.perf_counter()
    cpu_times = os.times()
    times.append((time.time(), cpu_times))
    time.sleep(1)

cpu_user = sum(t[1][0] for t in times) / len(times)
cpu_sys = sum(t[1][1] for t in times) / len(times)
cpu_children = sum(t[1][2] for t in times) / len(times)
print(f"Avg CPU user: {cpu_user:.3f}s")
print(f"Avg CPU sys: {cpu_sys:.3f}s")
print(f"Avg CPU children: {cpu_children:.3f}s")

# Check memory file size
import os
mem_files = []
for root, dirs, files in os.walk('runtime'):
    for f in files:
        if f.endswith('.json'):
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            mem_files.append((fp, sz))
mem_files.sort(key=lambda x: -x[1])
print(f"\n--- Memory Files ---")
for fp, sz in mem_files[:5]:
    print(f"  {fp}: {sz:,} bytes ({sz/1024:.1f} KB)")

print(f"\nTotal memory file size: {sum(s for _, s in mem_files):,} bytes ({sum(s for _, s in mem_files)/1024:.1f} KB)")
