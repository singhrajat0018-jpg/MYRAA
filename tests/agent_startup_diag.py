"""Quick agent startup diagnostic."""
import time
import sys
import os
import subprocess

PORT = 8772

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

# Collect output for 45 seconds
start = time.time()
while time.time() - start < 45:
    if proc.poll() is not None:
        print(f"Process exited with code {proc.returncode}")
        break
    time.sleep(1)
    elapsed = time.time() - start
    # Try health check
    import urllib.request
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=1)
        print(f"[{elapsed:.0f}s] HEALTH: {resp.status}")
        break
    except Exception as e:
        err = str(e)[:80]
        print(f"[{elapsed:.0f}s] no health: {err}")

# Read stderr
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()

stderr = proc.stderr.read().decode(errors='replace')
# Print last 3000 chars
print("\n=== STDERR (last 3000 chars) ===")
print(stderr[-3000:])
