"""Phase 3.1 — Soak test (15 min). Tracks memory, threads, file size for leak detection."""
import time
import sys
import os
import subprocess
import urllib.request
import json

sys.path.insert(0, os.getcwd())

PORT = 8777
LOG_DIR = os.path.join(os.getcwd(), 'runtime')
DURATION_S = 15 * 60  # 15 minutes
SAMPLE_INTERVAL = 30   # every 30 seconds
MEMORY_FILE = os.path.join(os.getcwd(), 'runtime', 'memory', 'myraa_brain_memory.json')

def get_process_info(pid):
    info = {'mem_mb': 0, 'threads': 0}
    try:
        out = subprocess.check_output(
            ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
            timeout=5
        )
        parts = out.decode().strip().strip('"').split('","')
        if len(parts) >= 5:
            info['mem_mb'] = float(parts[4].replace(' K', '').replace(',', '')) / 1024
            info['threads'] = int(parts[3])
    except:
        pass
    return info

def wait_for_agent(port, timeout=45):
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2)
            if resp.status == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def main():
    print("=" * 70)
    print("SOAK TEST (15 minutes)")
    print("=" * 70)

    # Start agent
    stdout_log = open(os.path.join(LOG_DIR, 'soak.stdout'), 'w')
    stderr_log = open(os.path.join(LOG_DIR, 'soak.stderr'), 'w')

    proc = subprocess.Popen(
        [sys.executable, '-c', f'''
import uvicorn
uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port={PORT}, log_level="error")
'''],
        stdout=stdout_log,
        stderr=stderr_log,
        cwd=os.getcwd()
    )
    print(f"Agent PID: {proc.pid}")

    if not wait_for_agent(PORT):
        print("Agent failed to start!")
        proc.terminate()
        return

    print("Agent ready. Starting soak measurement...\n")

    measurements = []
    start_time = time.time()

    while time.time() - start_time < DURATION_S:
        elapsed = time.time() - start_time
        t_min = elapsed / 60

        # Process info
        pinfo = get_process_info(proc.pid)

        # Memory file size
        mem_size = 0
        try:
            mem_size = os.path.getsize(MEMORY_FILE)
        except:
            pass

        sample = {
            'time': elapsed,
            'mem_mb': pinfo['mem_mb'],
            'threads': pinfo['threads'],
            'mem_file_bytes': mem_size,
        }
        measurements.append(sample)

        print(f"  [{t_min:5.1f}m] RAM={pinfo['mem_mb']:>6.1f}MB  Threads={pinfo['threads']}  MemFile={mem_size/1024:.1f}KB")

        # Send a tool request every 2 minutes to simulate activity
        if int(elapsed) % 120 == 0 and elapsed > 0:
            try:
                data = json.dumps({"tool": "systemInfo", "args": {}}).encode()
                req = urllib.request.Request(
                    f'http://127.0.0.1:{PORT}/execute',
                    data=data,
                    headers={'Content-Type': 'application/json'}
                )
                urllib.request.urlopen(req, timeout=10)
            except:
                pass

        time.sleep(SAMPLE_INTERVAL)

    # Stop agent
    print("\nStopping agent...")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except:
        proc.kill()
    stdout_log.close()
    stderr_log.close()

    # Analysis
    print("\n" + "=" * 70)
    print("SOAK TEST ANALYSIS")
    print("=" * 70)

    if len(measurements) >= 2:
        # Memory leak detection
        first_5 = [m['mem_mb'] for m in measurements[:5]]
        last_5 = [m['mem_mb'] for m in measurements[-5:]]
        avg_first = sum(first_5) / len(first_5)
        avg_last = sum(last_5) / len(last_5)
        mem_growth = avg_last - avg_first

        first_5t = [m['threads'] for m in measurements[:5]]
        last_5t = [m['threads'] for m in measurements[-5:]]
        avg_first_t = sum(first_5t) / len(first_5t)
        avg_last_t = sum(last_5t) / len(last_5t)

        first_5f = [m['mem_file_bytes'] for m in measurements[:5]]
        last_5f = [m['mem_file_bytes'] for m in measurements[-5:]]
        avg_first_f = sum(first_5f) / len(first_5f)
        avg_last_f = sum(last_5f) / len(last_5f)

        print(f"\n  Duration: {len(measurements) * SAMPLE_INTERVAL / 60:.1f} minutes ({len(measurements)} samples)")
        print(f"\n  RAM:")
        print(f"    Start (avg first 5): {avg_first:.1f} MB")
        print(f"    End (avg last 5):    {avg_last:.1f} MB")
        print(f"    Growth:              {mem_growth:+.1f} MB")
        print(f"    {'LEAK DETECTED' if mem_growth > 20 else 'STABLE'}")

        print(f"\n  Threads:")
        print(f"    Start: {avg_first_t:.0f}")
        print(f"    End:   {avg_last_t:.0f}")
        print(f"    {'LEAK DETECTED' if avg_last_t - avg_first_t > 5 else 'STABLE'}")

        print(f"\n  Memory File:")
        print(f"    Start: {avg_first_f/1024:.1f} KB")
        print(f"    End:   {avg_last_f/1024:.1f} KB")
        growth_pct = ((avg_last_f - avg_first_f) / avg_first_f * 100) if avg_first_f > 0 else 0
        print(f"    Growth: {growth_pct:+.1f}%")

    # Save results
    with open(os.path.join(LOG_DIR, 'phase3_1_soak.json'), 'w') as f:
        json.dump(measurements, f, indent=2)
    print(f"\nResults saved to runtime/phase3_1_soak.json")

if __name__ == "__main__":
    main()
