"""Phase 3.2 — Verify agent starts with ScreenShareEngine."""
import time
import sys
import os
import subprocess
import urllib.request

PORT = 8778

proc = subprocess.Popen(
    [sys.executable, '-c', f'''
import uvicorn
uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port={PORT}, log_level="info")
'''],
    stdout=open(os.path.join(os.getcwd(), 'runtime', 'p32_startup.stdout'), 'w'),
    stderr=open(os.path.join(os.getcwd(), 'runtime', 'p32_startup.stderr'), 'w'),
    cwd=os.getcwd()
)
print(f"PID: {proc.pid}")

start = time.time()
ready = False
while time.time() - start < 45:
    time.sleep(1)
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2)
        if resp.status == 200:
            ready = True
            break
    except:
        pass

elapsed = time.time() - start
if ready:
    print(f"Agent ready in {elapsed:.1f}s")
else:
    print(f"TIMEOUT after {elapsed:.1f}s")

proc.terminate()
proc.wait(timeout=5)

# Check stderr for ScreenShareEngine
with open(os.path.join(os.getcwd(), 'runtime', 'p32_startup.stderr'), 'r', errors='replace') as f:
    stderr = f.read()

if 'ScreenShareEngine started' in stderr:
    print("ScreenShareEngine: STARTED")
elif 'screen share engine' in stderr.lower():
    print("ScreenShareEngine: mentioned in startup")
else:
    print("ScreenShareEngine: NOT FOUND in startup logs")

if 'ScreenShare capture thread started' in stderr:
    print("ScreenShare capture thread: RUNNING")

# Check for old vision pipeline
if 'start vision pipeline' in stderr:
    print("WARNING: Old vision pipeline still in startup")
else:
    print("Old vision pipeline: REMOVED from startup")

print(f"\nStartup duration: {elapsed:.1f}s")
