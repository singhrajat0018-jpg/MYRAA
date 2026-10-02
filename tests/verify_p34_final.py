"""Check startup logs for architecture verification."""
import time, sys, os, subprocess, urllib.request

PORT = 8783
proc = subprocess.Popen(
    [sys.executable, '-c',
     'import uvicorn; uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port=%d, log_level="error")' % PORT],
    stdout=open(os.path.join(os.getcwd(), 'runtime', 'p34_final_stdout'), 'w'),
    stderr=open(os.path.join(os.getcwd(), 'runtime', 'p34_final_stderr'), 'w'),
    cwd=os.getcwd()
)
start = time.time()
while time.time() - start < 30:
    time.sleep(1)
    try:
        resp = urllib.request.urlopen('http://127.0.0.1:%d/health' % PORT, timeout=2)
        if resp.status == 200:
            break
    except:
        pass
time.sleep(2)
print("Agent ready after %.1fs" % (time.time() - start))
with open(os.path.join(os.getcwd(), 'runtime', 'p34_final_stderr'), 'r', errors='replace') as f:
    stderr = f.read()
for line in stderr.split('\n'):
    if any(k in line.lower() for k in ['screen share', 'continuous vision', 'runtime', 'vision', 'capture', 'screen observer']):
        print(line)
proc.terminate()
proc.wait(timeout=5)
