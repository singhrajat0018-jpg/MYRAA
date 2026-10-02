"""Phase 3.4 — Verify full screen architecture."""
import time
import sys
import os
import subprocess
import urllib.request

PORT = 8781

proc = subprocess.Popen(
    [sys.executable, '-c',
     f'import uvicorn; uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port={PORT}, log_level="error")'],
    stdout=open(os.path.join(os.getcwd(), 'runtime', 'p34_stdout'), 'w'),
    stderr=open(os.path.join(os.getcwd(), 'runtime', 'p34_stderr'), 'w'),
    cwd=os.getcwd()
)
print(f"PID: {proc.pid}")

start = time.time()
while time.time() - start < 30:
    time.sleep(1)
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2)
        if resp.status == 200:
            break
    except:
        pass

time.sleep(2)
print(f"Agent ready after {time.time()-start:.1f}s")

with open(os.path.join(os.getcwd(), 'runtime', 'p34_stderr'), 'r', errors='replace') as f:
    stderr = f.read()

print("\n--- Screen Architecture ---")

checks = [
    ("ScreenShareEngine", "ScreenShare capture thread started"),
    ("ContinuousVisionController", "Continuous vision controller started"),
    ("VisionManager", "Vision loop started"),
    ("ScreenObserver", "screen_observer"),
]

for name, pattern in checks:
    if pattern in stderr:
        print(f"  {name}: STARTED")
    else:
        print(f"  {name}: NOT FOUND")

# Duplicate capture check
if "Capture thread started" in stderr:
    print("\n  WARNING: Old LiveCapture thread present!")
else:
    print("\n  Old LiveCapture: REMOVED")

if "ScreenObserver" in stderr and "Capture loop" in stderr:
    print("  WARNING: ScreenObserver capture loop present!")
else:
    print("  ScreenObserver capture loop: REMOVED")

# Thread count
import ctypes
out = subprocess.check_output(
    ['powershell', '-Command', f'(Get-Process -Id {proc.pid}).Threads.Count'],
    timeout=5
)
thread_count = int(out.decode().strip())
print(f"\nThread count: {thread_count}")

proc.terminate()
proc.wait(timeout=5)
