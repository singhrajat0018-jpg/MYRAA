"""
Launcher readiness contract tests.

Verifies the shared definition of "the Desktop Agent is running":

    GET http://127.0.0.1:8765/health/live -> HTTP 200   == process alive

Covers:
1.  agent starts (/health/live == 200)
2.  /health returning 500 does NOT mark the process dead
3.  launcher-style probe detects readiness immediately (no full-timeout wait)
4.  delayed startup still detected within budget
5.  genuine startup failure produces a clear bounded timeout
6.  start-myraa.bat polls /health/live (source-level contract check)
7.  Node boot probe (services/desktop/desktop_agent.ts) uses /health/live
8.  HealthMonitor.get_stats never raises even if aggregation fails internally
"""

from __future__ import annotations

import sys
import time
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from desktop_agent.main import HealthMonitor, app


AGENT_URL = "http://127.0.0.1:8765"
LIVE_URL = f"{AGENT_URL}/health/live"

# Mirrors the polling loop embedded in start-myraa.bat.
PROBE_MAX_ATTEMPTS = 15
PROBE_INTERVAL_S = 1.0
PROBE_HTTP_TIMEOUT_S = 2.0


# ---------------------------------------------------------------------------
# Probe implementation (same semantics as the PowerShell loop in the .bat)
# ---------------------------------------------------------------------------

def probe_once(url: str, timeout: float = PROBE_HTTP_TIMEOUT_S):
    """Single readiness probe. Returns the HTTP status int (0 = no connection)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def wait_until_ready(url: str, max_attempts: int = PROBE_MAX_ATTEMPTS):
    """Poll until ready. Returns (ready, attempts_used, last_status)."""
    last = 0
    for i in range(1, max_attempts + 1):
        last = probe_once(url)
        if last == 200:
            return True, i, last
        time.sleep(PROBE_INTERVAL_S)
    return False, max_attempts, last


def wait_until_ready_fast(url: str, max_attempts: int = PROBE_MAX_ATTEMPTS,
                          interval: float = PROBE_INTERVAL_S):
    """Like wait_until_ready but without the trailing sleep after success."""
    last = 0
    start = time.monotonic()
    for i in range(1, max_attempts + 1):
        last = probe_once(url)
        if last == 200:
            return True, i, last, time.monotonic() - start
        time.sleep(interval)
    return False, max_attempts, last, time.monotonic() - start


# ---------------------------------------------------------------------------
# Embedded HTTP server helpers (simulates the agent without importing uvicorn)
# ---------------------------------------------------------------------------

class _FakeAgentHandler(BaseHTTPRequestHandler):
    routes: dict = {}          # path -> (status, body)
    delay_before_serving = 0.0

    def do_GET(self):
        if self.delay_before_serving > 0:
            time.sleep(self.delay_before_serving)
        status, body = self.routes.get(self.path, (404, b"{}"))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence
        pass


@pytest.fixture()
def fake_agent():
    handler = type("H", (_FakeAgentHandler,), {
        "routes": {"/health/live": (200, b'{"status":"ok"}'),
                   "/health": (200, b'{"status":"ok","tool_count":89}')},
        "delay_before_serving": 0.0,
    })
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", handler
    srv.shutdown()


# ---------------------------------------------------------------------------
# 1. Real agent liveness (skipped when the agent isn't running)
# ---------------------------------------------------------------------------

def test_real_agent_live_if_running():
    status = probe_once(LIVE_URL)
    if status == 0:
        pytest.skip("Desktop Agent not running on :8765")
    assert status == 200


def test_app_health_live_ok():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    r = client.get("/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


# ---------------------------------------------------------------------------
# 2. /health failing must NOT mark the process dead
# ---------------------------------------------------------------------------

def test_health_500_does_not_mark_dead(fake_agent):
    base, handler = fake_agent
    handler.routes["/health"] = (500, b'{"error":"NameError: boom"}')
    ready, attempts, last = wait_until_ready(f"{base}/health/live",
                                             max_attempts=3)
    assert ready, "liveness probe failed while /health returned 500"
    assert attempts == 1  # first attempt already succeeded


def test_health_endpoint_never_500s(monkeypatch):
    def _boom():
        raise RuntimeError("simulated aggregation failure")
    monkeypatch.setattr(HealthMonitor, "_collect_stats", staticmethod(_boom))
    stats = HealthMonitor.get_stats()  # must not raise
    assert isinstance(stats, dict)
    assert stats["status"] == "degraded"
    assert "error" in stats


# ---------------------------------------------------------------------------
# 3+4. Readiness detected fast — no full-timeout wait
# ---------------------------------------------------------------------------

def test_probe_detects_ready_immediately(fake_agent):
    base, _ = fake_agent
    ready, attempts, last, elapsed = wait_until_ready_fast(f"{base}/health/live")
    assert ready
    assert attempts == 1
    # Must NOT have waited anything close to the full timeout window.
    assert elapsed < PROBE_INTERVAL_S + 1.0


def test_delayed_startup_still_detected(fake_agent):
    base, handler = fake_agent
    # Simulate slow bind: first requests fail (connection refused), then OK.
    handler.delay_before_serving = 0.0
    original_do_GET = handler.do_GET

    state = {"down_for": 1.6}
    start_time = time.monotonic()

    def do_GET(self):
        if time.monotonic() - start_time < state["down_for"]:
            self.close_connection = True
            return
        original_do_GET(self)

    handler.do_GET = do_GET
    interval = 0.3
    ready, attempts, last, elapsed = wait_until_ready_fast(
        f"{base}/health/live", max_attempts=15, interval=interval)
    assert ready
    assert elapsed >= state["down_for"] - 0.05  # it really waited for startup
    assert elapsed < PROBE_MAX_ATTEMPTS * interval  # but far less than worst case


# ---------------------------------------------------------------------------
# 5. Genuine failure: clear bounded timeout
# ---------------------------------------------------------------------------

def test_startup_failure_times_out_clearly():
    # Nothing listens on this ephemeral port (bound then closed).
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    dead_url = f"http://127.0.0.1:{port}/health/live"

    ready, attempts, last = wait_until_ready(dead_url, max_attempts=2)
    assert not ready
    assert attempts == 2
    assert last == 0  # connection refused — unambiguous "not up" signal


# ---------------------------------------------------------------------------
# 6+7. Contract consistency across launcher / Node / agent
# ---------------------------------------------------------------------------

def test_bat_launcher_polls_health_live():
    root = __file__.rsplit("\\tests\\", 1)[0] if "\\tests\\" in __file__ else "."
    with open(f"{root}\\start-myraa.bat", "r", encoding="utf-8", errors="ignore") as f:
        bat = f.read()
    assert "/health/live" in bat
    assert "Invoke-WebRequest" in bat
    # The launcher must NOT gate on the detailed health report.
    assert "'http://127.0.0.1:8765/health'" not in bat


def test_node_boot_probe_uses_liveness():
    import glob as _glob
    root = __file__.rsplit("\\tests\\", 1)[0] if "\\tests\\" in __file__ else "."
    with open(f"{root}\\services\\desktop\\desktop_agent.ts", "r",
              encoding="utf-8", errors="ignore") as f:
        ts = f.read()
    assert "`${DESKTOP_AGENT_URL}/health/live`" in ts
    # ensureDesktopAgent's liveness check must not use detailed /health.
    assert "`${DESKTOP_AGENT_URL}/health`" not in ts.split("callDesktopAgent")[0]

    # /api/agent-health bases `online` on /health/live.
    # After route decomposition, this lives in server/routes/system.ts.
    server_files = [f"{root}\\server.ts"] + _glob.glob(f"{root}\\server\\routes\\*.ts")
    combined = ""
    for fp in server_files:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                combined += f.read()
        except FileNotFoundError:
            pass
    assert "/health/live" in combined


# ---------------------------------------------------------------------------
# Windows integration: run the EXACT PowerShell snippet from start-myraa.bat
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
def test_powershell_snippet_from_bat_detects_readiness(fake_agent):
    base, handler = fake_agent
    handler.routes["/health"] = (500, b'{"error":"subsystem down"}')
    ps_url = f"{base}/health/live"
    snippet = (
        "$u='%s'; $max=5; $code=0; "
        "for($i=1;$i -le $max;$i++){ "
        "try{ $r=Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 2; "
        "$code=[int]$r.StatusCode }catch{ "
        "if($_.Exception.Response){ $code=[int]$_.Exception.Response.StatusCode } "
        "else { $code=0 } }; "
        "if($code -eq 200){ Write-Host 'READY'; exit 0 }; "
        "Start-Sleep -Milliseconds 200 }; exit 1" % ps_url
    )
    import subprocess
    p = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", snippet],
        capture_output=True, text=True, timeout=30,
    )
    assert p.returncode == 0, (
        "launcher PowerShell snippet failed even though /health/live=200 "
        f"(stderr: {p.stderr[:300]})"
    )
    assert "READY" in p.stdout
