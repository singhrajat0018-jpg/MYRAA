"""Diagnose agent startup - file-based logging."""
import time
import sys
import os
import subprocess

PORT = 8775
LOG = os.path.join(os.getcwd(), 'runtime', 'agent_startup.log')

proc = subprocess.Popen(
    [sys.executable, '-c', f'''
import uvicorn
uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port={PORT}, log_level="info")
'''],
    stdout=open(LOG + '.stdout', 'w'),
    stderr=open(LOG + '.stderr', 'w'),
    cwd=os.getcwd()
)
print(f"PID: {proc.pid}")

# Monitor for 50 seconds
start = time.time()
while time.time() - start < 50:
    if proc.poll() is not None:
        print(f"Process exited with code {proc.returncode}")
        break
    time.sleep(2)
    elapsed = time.time() - start
    print(f"[{elapsed:.0f}s] running... pid={proc.pid}")

    import urllib.request
    try:
        resp = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=1)
        print(f"[{elapsed:.0f}s] HEALTH OK!")
        break
    except:
        pass

proc.terminate()
proc.wait(timeout=5)

# Read stderr
with open(LOG + '.stderr', 'r', errors='replace') as f:
    stderr = f.read()
print(f"\n=== STDERR ({len(stderr)} bytes) ===")
# Print last 5000 chars
print(stderr[-5000:])
