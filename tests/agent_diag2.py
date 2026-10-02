"""Diagnose agent startup hang."""
import time
import sys
import os
import subprocess

PORT = 8774

proc = subprocess.Popen(
    [sys.executable, '-c', f'''
import uvicorn
uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port={PORT}, log_level="info")
'''],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=os.getcwd()
)
print(f"PID: {proc.pid}")

# Wait and collect stderr in real-time
start = time.time()
while time.time() - start < 50:
    if proc.poll() is not None:
        print(f"Process exited with code {proc.returncode}")
        break
    time.sleep(2)
    # Read available stderr
    import msvcrt
    elapsed = time.time() - start
    print(f"[{elapsed:.0f}s] running...")

    # Try health
    import urllib.request
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=1)
        print(f"[{elapsed:.0f}s] HEALTH: {resp.status}")
        break
    except:
        pass

proc.terminate()
proc.wait(timeout=5)

stderr = proc.stderr.read().decode(errors='replace')
# Print last 5000 chars
print("\n=== STDERR (last 5000) ===")
print(stderr[-5000:])
