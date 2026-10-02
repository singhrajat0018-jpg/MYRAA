"""
F9 tests: health & readiness endpoints.

Verifies /health, /health/live, /health/ready:
- /health/live is provider-independent (process alive only)
- /health/ready reports dependency status (node, python agent, memory, AI
  providers, browser, tool dispatcher, storage) and an overall
  HEALTHY/DEGRADED/UNAVAILABLE status
- provider health separates configured/available/state/rate_limited/degraded
- no secrets (API keys) are ever exposed in health payloads
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from desktop_agent.main import app

client = TestClient(app)


def test_health_live_ok():
    resp = client.get("/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["name"]
    assert body["version"]
    assert body["uptime_seconds"] >= 0


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["tool_count"] > 0
    assert "subsystems" in body


def test_health_ready_shape():
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("HEALTHY", "DEGRADED", "UNAVAILABLE")
    deps = body["dependencies"]
    for key in ["python_agent", "node", "memory", "ai_providers", "browser", "tool_dispatcher", "storage"]:
        assert key in deps, key
        assert deps[key]["status"] in ("HEALTHY", "DEGRADED", "UNAVAILABLE", "FAILED")
    assert body["tool_count"] > 0
    assert "version" in body
    assert "uptime_seconds" in body


def test_health_ready_tool_dispatcher():
    resp = client.get("/health/ready")
    deps = resp.json()["dependencies"]
    assert deps["tool_dispatcher"]["status"] == "HEALTHY"
    assert "tools" in deps["tool_dispatcher"]["detail"] or "registered" in deps["tool_dispatcher"]["detail"]


def test_health_ready_python_agent():
    resp = client.get("/health/ready")
    assert resp.json()["dependencies"]["python_agent"]["status"] == "HEALTHY"


def test_health_ready_providers_shape():
    resp = client.get("/health/ready")
    providers = resp.json()["dependencies"]["ai_providers"]["detail"]
    assert isinstance(providers, list)
    assert len(providers) == 3
    for p in providers:
        assert p["provider"] in ("nim", "gemini", "ollama")
        for key in ["configured", "available", "model", "state", "degraded", "rate_limited"]:
            assert key in p, key
        assert p["state"] in ("HEALTHY", "DEGRADED", "COOLDOWN", "UNAVAILABLE")


def test_health_never_exposes_secrets():
    for endpoint in ("/health", "/health/live", "/health/ready"):
        blob = str(client.get(endpoint).json()).lower()
        for secret in ["api_key", "apikey", "sk-", "aiza", "bearer ", "password", "authorization"]:
            assert secret not in blob, f"{endpoint} leaked '{secret}'"


def test_health_ready_browser_state():
    from desktop_agent.brain.failure_containment import failure_containment_manager
    resp = client.get("/health/ready")
    browser_status = resp.json()["dependencies"]["browser"]["status"]
    assert browser_status in ("HEALTHY", "DEGRADED", "FAILED")


def test_health_live_is_provider_independent():
    """Liveness must not depend on providers being configured."""
    import desktop_agent.main as main_mod
    original = dict(main_mod._PROVIDER_FACTORIES)
    try:
        main_mod._PROVIDER_FACTORIES.clear()  # even with no providers...
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    finally:
        main_mod._PROVIDER_FACTORIES.update(original)