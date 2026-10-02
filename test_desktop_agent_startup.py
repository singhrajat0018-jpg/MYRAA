"""
Test Desktop Agent Startup and Functionality
Verifies that the startup blocker is fully resolved.
"""
import subprocess
import time
import requests
import sys
import json

def print_status(msg, status="INFO"):
    prefix = {
        "INFO": "[INFO]",
        "PASS": "[✓ PASS]",
        "FAIL": "[✗ FAIL]",
        "WARN": "[! WARN]"
    }
    print(f"{prefix.get(status, '[INFO]')} {msg}")

def test_import_speed():
    """Test that import completes in under 2 seconds."""
    print_status("Testing import speed...")
    start = time.time()
    result = subprocess.run(
        ["python", "-c", "import desktop_agent.main"],
        capture_output=True,
        timeout=5
    )
    elapsed = time.time() - start

    if result.returncode == 0 and elapsed < 2.0:
        print_status(f"Import completed in {elapsed:.2f}s", "PASS")
        return True
    else:
        print_status(f"Import took {elapsed:.2f}s (expected < 2.0s)", "FAIL")
        return False

def start_agent():
    """Start the Desktop Agent in background."""
    print_status("Starting Desktop Agent...")
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "desktop_agent.main:app",
         "--host", "127.0.0.1", "--port", "8765"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    return proc

def wait_for_ready(max_wait=30):
    """Wait for /health/live to respond."""
    print_status(f"Waiting for /health/live (max {max_wait}s)...")
    start = time.time()

    while time.time() - start < max_wait:
        try:
            resp = requests.get("http://127.0.0.1:8765/health/live", timeout=2)
            if resp.status_code == 200:
                elapsed = time.time() - start
                print_status(f"/health/live ready in {elapsed:.2f}s", "PASS")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)

    print_status(f"/health/live not ready after {max_wait}s", "FAIL")
    return False

def test_health_live():
    """Test /health/live endpoint."""
    print_status("Testing /health/live...")
    try:
        resp = requests.get("http://127.0.0.1:8765/health/live", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_status(f"/health/live: {json.dumps(data, indent=2)}", "PASS")
            return True
        else:
            print_status(f"/health/live returned {resp.status_code}", "FAIL")
            return False
    except Exception as e:
        print_status(f"/health/live failed: {e}", "FAIL")
        return False

def test_health_ready():
    """Test /health/ready endpoint."""
    print_status("Testing /health/ready...")
    try:
        resp = requests.get("http://127.0.0.1:8765/health/ready", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "UNKNOWN")
            print_status(f"/health/ready: status={status}",
                        "PASS" if status in ["HEALTHY", "DEGRADED"] else "WARN")
            return True
        else:
            print_status(f"/health/ready returned {resp.status_code}", "FAIL")
            return False
    except Exception as e:
        print_status(f"/health/ready failed: {e}", "FAIL")
        return False

def test_tool_execution():
    """Test executing a safe tool."""
    print_status("Testing tool execution (systemInfo)...")
    try:
        resp = requests.post(
            "http://127.0.0.1:8765/execute",
            json={"tool": "systemInfo", "args": {}},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                print_status(f"Tool execution successful", "PASS")
                return True
            else:
                print_status(f"Tool execution failed: {data.get('error')}", "FAIL")
                return False
        else:
            print_status(f"/execute returned {resp.status_code}", "FAIL")
            return False
    except Exception as e:
        print_status(f"Tool execution failed: {e}", "FAIL")
        return False

def test_tools_list():
    """Test /tools endpoint."""
    print_status("Testing /tools endpoint...")
    try:
        resp = requests.get("http://127.0.0.1:8765/tools", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            count = data.get("count", 0)
            print_status(f"/tools: {count} tools registered", "PASS")
            return True
        else:
            print_status(f"/tools returned {resp.status_code}", "FAIL")
            return False
    except Exception as e:
        print_status(f"/tools failed: {e}", "FAIL")
        return False

def main():
    print("=" * 60)
    print("MYRAA DESKTOP AGENT STARTUP TEST")
    print("=" * 60)

    results = {}
    agent_proc = None

    try:
        # Test 1: Import speed
        results["import_speed"] = test_import_speed()
        print()

        # Test 2: Start agent
        agent_proc = start_agent()
        time.sleep(2)  # Give it a moment to start
        print()

        # Test 3: Wait for ready
        results["startup"] = wait_for_ready(30)
        if not results["startup"]:
            print_status("Startup failed - aborting remaining tests", "FAIL")
            return False
        print()

        # Test 4: Health live
        results["health_live"] = test_health_live()
        print()

        # Test 5: Health ready
        results["health_ready"] = test_health_ready()
        print()

        # Test 6: Tools list
        results["tools_list"] = test_tools_list()
        print()

        # Test 7: Tool execution
        results["tool_execution"] = test_tool_execution()
        print()

    finally:
        if agent_proc:
            print_status("Stopping Desktop Agent...")
            agent_proc.terminate()
            try:
                agent_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent_proc.kill()
            print_status("Desktop Agent stopped")

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print_status(f"{test_name}: {status}", status)

    print()
    print_status(f"Total: {passed}/{total} tests passed",
                "PASS" if passed == total else "FAIL")
    print("=" * 60)

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
