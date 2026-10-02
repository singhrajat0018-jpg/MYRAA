"""Check agent stderr output."""
import subprocess, time, sys, os

proc = subprocess.Popen(
    [sys.executable, '-c',
     'import uvicorn; uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port=8768, log_level="info")'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
)
print(f'Agent PID: {proc.pid}')

# Wait and collect output
time.sleep(25)

# Check if running
poll = proc.poll()
print(f'Poll: {poll}')

# Read available output
import select
import msvcrt

# Non-blocking read from stdout/stderr
stdout_data = b''
stderr_data = b''
proc.terminate()
time.sleep(2)
try:
    stdout_data = proc.stdout.read(10000)
    stderr_data = proc.stderr.read(10000)
except:
    pass

print(f'\n=== STDOUT ({len(stdout_data)} bytes) ===')
print(stdout_data.decode(errors='replace')[-3000:])
print(f'\n=== STDERR ({len(stderr_data)} bytes) ===')
print(stderr_data.decode(errors='replace')[-3000:])
