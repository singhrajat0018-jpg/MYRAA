"""Phase 3.1 — Restart test (file-based logging to avoid buffer deadlock)."""
import time
import sys
import os
import subprocess
import urllib.request
import json

sys.path.insert(0, os.getcwd())

PORT = 8776
LOG_DIR = os.path.join(os.getcwd(), 'runtime')

def wait_for_agent(port, timeout=45):
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2)
            if resp.status == 200:
                return True, time.time() - start
        except:
            pass
        time.sleep(1)
    return False, time.time() - start

def test_restart():
    print("=" * 70)
    print("RESTART TEST")
    print("=" * 70)

    results = []
    for cycle in range(2):
        print(f"\n--- Cycle {cycle+1} ---")

        stdout_log = open(os.path.join(LOG_DIR, f'restart_c{cycle}.stdout'), 'w')
        stderr_log = open(os.path.join(LOG_DIR, f'restart_c{cycle}.stderr'), 'w')

        proc = subprocess.Popen(
            [sys.executable, '-c', f'''
import uvicorn
uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port={PORT}, log_level="error")
'''],
            stdout=stdout_log,
            stderr=stderr_log,
            cwd=os.getcwd()
        )
        print(f"  PID: {proc.pid}")

        ready, elapsed = wait_for_agent(PORT, timeout=45)
        if ready:
            print(f"  Ready in {elapsed:.1f}s")
        else:
            print(f"  TIMEOUT after {elapsed:.1f}s")
            proc.terminate()
            proc.wait(timeout=10)
            stdout_log.close()
            stderr_log.close()
            continue

        # Tool test
        tool_ok = False
        try:
            data = json.dumps({"tool": "systemInfo", "args": {}}).encode()
            req = urllib.request.Request(
                f'http://127.0.0.1:{PORT}/execute',
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read().decode())
            tool_ok = 'result' in result
            print(f"  Tool test: {'OK' if tool_ok else 'FAIL'}")
        except Exception as e:
            print(f"  Tool test: ERROR ({str(e)[:60]})")

        # Stop
        t0 = time.perf_counter()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except:
            proc.kill()
            proc.wait()
        stop_ms = (time.perf_counter() - t0) * 1000
        print(f"  Stopped in {stop_ms:.0f}ms (exit={proc.returncode})")

        stdout_log.close()
        stderr_log.close()

        results.append({"cycle": cycle+1, "ready_s": elapsed, "stop_ms": stop_ms, "tool_ok": tool_ok})

        time.sleep(2)

    print("\n" + "=" * 70)
    print("RESTART TEST RESULTS")
    print("=" * 70)
    for r in results:
        print(f"  Cycle {r['cycle']}: ready={r['ready_s']:.1f}s  stop={r['stop_ms']:.0f}ms  tool={'OK' if r['tool_ok'] else 'FAIL'}")
    print(f"  All cycles clean: {'YES' if len(results) == 2 else 'INCOMPLETE'}")
    print("=" * 70)

if __name__ == "__main__":
    test_restart()
