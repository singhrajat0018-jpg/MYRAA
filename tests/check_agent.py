"""Quick agent health check."""
import subprocess, time, sys, os, urllib.request

proc = subprocess.Popen(
    [sys.executable, '-c',
     'import uvicorn; uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port=8767, log_level="warning")'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
)
print(f'Agent PID: {proc.pid}')
time.sleep(20)

# Health check
try:
    resp = urllib.request.urlopen('http://127.0.0.1:8767/health', timeout=5)
    print(f'Health: {resp.status} {resp.read().decode()[:200]}')
except Exception as e:
    print(f'Health check: {e}')

# Thread count
try:
    out = subprocess.check_output(
        ['wmic', 'process', 'where', f'ProcessId={proc.pid}', 'get', 'ThreadCount', '/VALUE'],
        timeout=5
    )
    for line in out.decode().split('\n'):
        if 'ThreadCount' in line and '=' in line:
            print(f'ThreadCount: {line.split("=")[1].strip()}')
except Exception as e:
    print(f'ThreadCount error: {e}')

# Memory
try:
    out = subprocess.check_output(
        ['tasklist', '/FI', f'PID eq {proc.pid}', '/FO', 'CSV', '/NH'],
        timeout=5
    )
    parts = out.decode().strip().strip('"').split('","')
    print(f'Memory: {parts[4]}  Threads: {parts[3]}')
except Exception as e:
    print(f'Memory error: {e}')

# Test /tools endpoint
try:
    resp = urllib.request.urlopen('http://127.0.0.1:8767/tools', timeout=5)
    data = resp.read().decode()
    print(f'Tools endpoint: {len(data)} bytes')
except Exception as e:
    print(f'Tools: {e}')

proc.terminate()
proc.wait(timeout=5)
print('Done')
