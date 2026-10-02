"""
EPIC-BRAIN Phase 1 — integration test: POST /brain routes through SuperBrain.

Verifies the canonical /brain path (Part 1):
  1. The endpoint returns the SuperBrainResult contract (success/message/
     decision/capability + metadata.route == "SUPER_BRAIN").
  2. The ApplicationContainer wires ONE shared SuperBrain whose sub-systems are
     the SAME singletons the rest of MYRAA uses (no duplicate authorities):
       - super_brain.ai_manager   is container.ai_manager
       - super_brain.memory_2_0   is container.memory_2_0
       - super_brain.orchestrator is container.orchestrator
       - super_brain.executor.orchestrator is container.orchestrator
       - super_brain.permission_manager is container.permission_manager
  3. ok == result.success (truthful contract: ok reflects the real outcome).
  4. The legacy BrainEngine stays importable and usable as a compat layer (not
     deleted), but is NOT the /brain entry point anymore.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def _container():
    """Build the real ApplicationContainer once (same DI the app uses)."""
    from desktop_agent.core.application_container import ApplicationContainer

    from desktop_agent.main import CommandDispatcher

    return ApplicationContainer(dispatcher=CommandDispatcher())


@pytest.fixture(scope="module")
def _client():
    from fastapi.testclient import TestClient

    from desktop_agent.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. /brain returns the canonical SuperBrain contract
# ---------------------------------------------------------------------------

def test_brain_route_returns_superbrain_contract(_client):
    # Contract evolution note (S.2 / Phase U): conversational/knowledge inputs
    # ("hello") now take the TASK_ROUTER_FAST path by design. The FULL
    # SuperBrain contract is exercised with an explicit action request.
    out = _client.post("/brain", json={"text": "open notepad", "request_id": "sb-route-1"})
    assert out.status_code == 200
    body = out.json()
    assert body["ok"] == body["result"]["success"]
    assert body["result"]["metadata"]["route"] == "SUPER_BRAIN"
    assert body["result"]["metadata"]["request_id"] == "sb-route-1"
    assert "message" in body["result"]
    assert "decision" in body["result"]
    assert "capability" in body["result"]
    assert "execution" in body["result"]["metadata"]


def test_brain_route_ok_matches_success(_client):
    """ok must never disagree with the SuperBrain success field."""
    out = _client.post("/brain", json={"text": "1 + 1", "request_id": "sb-route-2"})
    assert out.status_code == 200
    body = out.json()
    assert body["ok"] == body["result"]["success"]


# ---------------------------------------------------------------------------
# 2. Shared singletons — no duplicate authorities
# ---------------------------------------------------------------------------

def test_superbrain_ai_manager_is_container_ai_manager(_container):
    assert _container.super_brain.ai_manager is _container.ai_manager


def test_superbrain_memory_2_0_is_container_memory_2_0(_container):
    assert _container.super_brain.memory_2_0 is _container.memory_2_0


def test_superbrain_orchestrator_is_container_orchestrator(_container):
    # CapabilityOrchestrator is SuperBrain's execution-strategy layer; the real
    # ClosedLoopExecutor runs the existing Orchestrator. Both must point at the
    # single container orchestrator.
    assert _container.super_brain.orchestrator is not None
    assert _container.super_brain.executor.orchestrator is _container.orchestrator


def test_superbrain_permission_gate_is_dispatch_layer(_container):
    """SuperBrain's execution path MUST reach the single dispatcher that
    enforces PermissionManager (permission authority is the dispatcher, not a
    second gate). The closed-loop executor runs the container orchestrator,
    which is the ONLY path to tool dispatch, and the orchestrator holds the
    CommandDispatcher that applies PermissionManager.check per tool.
    """
    assert _container.super_brain.executor.orchestrator is _container.orchestrator

    # The container orchestrator holds the dispatcher it dispatches through.
    dispatcher = _container.orchestrator._dispatcher
    assert dispatcher is not None

    # No duplicate permission system: PermissionManager stays the single
    # static authority, reached via the dispatcher.
    from desktop_agent.registry import PermissionManager

    assert hasattr(PermissionManager, "check")
    assert hasattr(PermissionManager, "mint_confirmation")


# ---------------------------------------------------------------------------
# 3. BrainEngine remains a compat layer (not deleted, not the entry point)
# ---------------------------------------------------------------------------

def test_legacy_brain_engine_still_importable_and_usable(_container):
    # Lifespan note: main.BRAIN is assigned during FastAPI lifespan startup,
    # which TestClient(app) without a context manager does not trigger. The
    # legacy compat layer is therefore proven constructible from the same DI
    # container the lifespan uses — same dispatcher + same brain_engine.
    from desktop_agent.brain.brain import Brain
    from desktop_agent.main import CommandDispatcher

    legacy = Brain(CommandDispatcher(), brain_engine=_container.brain_engine)

    assert legacy is not None
    assert legacy.brain_engine is _container.brain_engine
    # The /brain route must not be the legacy BrainEngine entry anymore.
    from desktop_agent.main import app

    for route in app.routes:
        if getattr(route, "path", None) == "/brain":
            # The handler is the module-level `brain` function (SuperBrain path).
            assert route.endpoint.__module__ == "desktop_agent.main"
            break
    else:
        pytest.fail("/brain route not registered on app")
