"""Phase 3.1 — Real runtime idle baseline with proper uvicorn startup."""
import subprocess
import time
import os
import sys
import json

MEASUREMENT_DURATION = 30
SAMPLE_INTERVAL = 2

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

def get_child_pids(pid):
    try:
        out = subprocess.check_output(
            ['wmic', 'process', 'where', f'ParentProcessId={pid}', 'get', 'ProcessId'],
            timeout=5
        )
        return [int(l.strip()) for l in out.decode().strip().split('\n') if l.strip().isdigit()]
    except:
        return []

def main():
    print("=" * 70)
    print("MYRAA PHASE 3.1 — REAL RUNTIME IDLE BASELINE (uvicorn)")
    print("=" * 70)

    # Start uvicorn directly
    print("\n[1] Starting desktop agent via uvicorn...")
    proc = subprocess.Popen(
        [sys.executable, '-c', '''
import uvicorn
import os
os.environ.setdefault("MYRAA_AGENT_HOST", "127.0.0.1")
os.environ.setdefault("MYRAA_AGENT_PORT", "8765")
uvicorn.run("desktop_agent.main:app", host="127.0.0.1", port=8765, log_level="warning")
'''],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd()
    )
    print(f"    PID: {proc.pid}")

    # Wait for startup
    print("[2] Waiting 20s for agent initialization...")
    time.sleep(20)

    if proc.poll() is not None:
        print(f"    ERROR: Agent exited with code {proc.returncode}")
        stderr = proc.stderr.read().decode(errors='replace')[-1000:]
        print(f"    STDERR: {stderr}")
        return

    print("[3] Agent running. Measuring idle for 30s...\n")

    # Get all Python processes (agent + children)
    all_pids = [proc.pid] + get_child_pids(proc.pid)
    print(f"    Monitoring PIDs: {all_pids}")

    measurements = []
    for i in range(MEASUREMENT_DURATION // SAMPLE_INTERVAL):
        total_mem = 0
        total_threads = 0
        for pid in all_pids:
            info = get_process_info(pid)
            total_mem += info['mem_mb']
            total_threads += info['threads']

        # Check for new children
        new_children = get_child_pids(proc.pid)
        for nc in new_children:
            if nc not in all_pids:
                all_pids.append(nc)
                print(f"    New child PID: {nc}")

        measurements.append({
            'time': i * SAMPLE_INTERVAL,
            'mem_mb': total_mem,
            'threads': total_threads,
            'pids': list(all_pids),
        })

        print(f"    [{i*SAMPLE_INTERVAL:>3}s] Total={total_mem:>6.1f}MB  Threads={total_threads}  PIDs={len(all_pids)}")
        time.sleep(SAMPLE_INTERVAL)

    # Stop
    print("\n[4] Stopping agent...")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except:
        proc.kill()
        proc.wait()
    print(f"    Stopped (exit code: {proc.returncode})")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if measurements:
        mems = [m['mem_mb'] for m in measurements]
        threads = [m['threads'] for m in measurements]
        print(f"  RAM:  min={min(mems):.1f}MB  max={max(mems):.1f}MB  avg={sum(mems)/len(mems):.1f}MB")
        print(f"  Threads: min={min(threads)}  max={max(threads)}  avg={sum(threads)/len(threads):.1f}")

    with open('runtime/phase3_1_idle_baseline.json', 'w') as f:
        json.dump(measurements, f, indent=2, default=str)
    print(f"\nResults saved to runtime/phase3_1_idle_baseline.json")

if __name__ == "__main__":
    main()
