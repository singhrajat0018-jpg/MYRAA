"""Phase 3.3 — Verify no duplicate capture threads."""
import time
import sys
import os
import threading
import subprocess

PORT = 8779

proc = subprocess.Popen(
    [sys.executable, '-c', f'''
import uvicorn
uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port={PORT}, log_level="error")
'''],
    stdout=open(os.path.join(os.getcwd(), 'runtime', 'p33_threads.stdout'), 'w'),
    stderr=open(os.path.join(os.getcwd(), 'runtime', 'p33_threads.stderr'), 'w'),
    cwd=os.getcwd()
)
print(f"PID: {proc.pid}")

# Wait for startup
import urllib.request
start = time.time()
while time.time() - start < 30:
    time.sleep(1)
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2)
        if resp.status == 200:
            break
    except:
        pass

time.sleep(3)  # Let threads settle

print(f"Agent ready after {time.time()-start:.1f}s")

# Count threads
import ctypes
kernel32 = ctypes.windll.kernel32

# Via PowerShell
import subprocess as sp
out = sp.check_output(
    ['powershell', '-Command', f'(Get-Process -Id {proc.pid}).Threads.Count'],
    timeout=5
)
thread_count = int(out.decode().strip())
print(f"Thread count: {thread_count}")

# Check for named threads via stderr
with open(os.path.join(os.getcwd(), 'runtime', 'p33_threads.stderr'), 'r', errors='replace') as f:
    stderr = f.read()

# Count capture-related threads
capture_threads = stderr.count('ScreenShare')
vision_threads = stderr.count('MYRAA-Vision')
observer_threads = stderr.count('screen_observer')

print(f"\nThread analysis:")
print(f"  ScreenShare (capture): {'STARTED' if capture_threads > 0 else 'NOT FOUND'}")
print(f"  MYRAA-Vision (analysis): {'STARTED' if vision_threads > 0 else 'NOT FOUND'}")
print(f"  screen_observer: {'STARTED' if observer_threads > 0 else 'NOT FOUND'}")

# Verify no LiveCapture thread
if 'Capture thread started' in stderr:
    print(f"\n  WARNING: Old LiveCapture thread still present!")
else:
    print(f"\n  Old LiveCapture thread: REMOVED")

# Check for duplicate capture
if 'ScreenObserver' in stderr and 'Capture loop' in stderr:
    print(f"  WARNING: ScreenObserver still has capture loop!")
else:
    print(f"  ScreenObserver capture loop: REMOVED")

proc.terminate()
proc.wait(timeout=5)
