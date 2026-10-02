"""Integration tests for D/E/F/G critical fixes.

Verifies:
1. UniversalController REST endpoint calls execute_intent (not nonexistent execute_action)
2. NeuralEngine has 7 real specialists registered at runtime via ApplicationContainer
3. SelfHealingManager DiagnosticsEngine has 6 real health checks registered
4. DiagnosticsEngine periodic monitoring is enabled
5. All three subsystems are accessible from the DI container
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock


class TestUniversalControllerFix:
    """E1: REST endpoint must call execute_intent."""

    def test_execute_intent_method_exists(self):
        from desktop_agent.universal_control.universal_controller import UniversalController
        ctrl = UniversalController()
        assert hasattr(ctrl, "execute_intent")
        assert callable(ctrl.execute_intent)

    def test_rest_endpoint_uses_execute_intent(self):
        """main.py line must call execute_intent, not execute_action."""
        import pathlib
        main_py = pathlib.Path(__file__).resolve().parent.parent / "desktop_agent" / "main.py"
        source = main_py.read_text(encoding="utf-8")
        assert "ctrl.execute_intent(intent)" in source
        assert "ctrl.execute_action(" not in source

    def test_execute_intent_returns_control_result(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlResult, ControlStatus,
        )
        ctrl = UniversalController()
        result = ctrl.execute_intent("click button")
        assert isinstance(result, ControlResult)
        assert result.status == ControlStatus.NO_VISION


class TestNeuralEngineRegistration:
    """F1: NeuralEngine must have all real specialists registered.

    NOTE (documented stale expectation, §61): the Python design_specialist was
    retired — design intelligence is owned by the TypeScript DesignCore (see
    AGENTS.md). The current authoritative registry has 6 specialists; the count
    assertions were updated accordingly and no longer reference ModelDomain.DESIGN.
    """

    def test_specialists_registered_via_container(self):
        from desktop_agent.core.application_container import ApplicationContainer
        container = ApplicationContainer()
        ne = container.neural_engine
        models = ne.list_models()
        model_ids = [m.model_id for m in models]
        assert len(models) >= 6, f"Expected >=6 specialists, got {len(models)}: {model_ids}"
        assert "vision_specialist_v1" in model_ids
        assert "trading_specialist_v1" in model_ids
        assert "voice_specialist_v1" in model_ids
        assert "prediction_specialist_v1" in model_ids
        assert "personalization_specialist_v1" in model_ids
        assert "multimodal_specialist_v1" in model_ids

    def test_neural_engine_health_shows_specialists(self):
        from desktop_agent.core.application_container import ApplicationContainer
        container = ApplicationContainer()
        health = container.neural_engine.model_health()
        assert len(health) >= 6
        for model_id, info in health.items():
            assert "status" in info
            assert "health_score" in info

    def test_neural_engine_infer_smoke(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.neural_engine.model_contract import (
            InferenceRequest, ModelDomain, ModelModality,
        )
        container = ApplicationContainer()
        request = InferenceRequest(
            domain=ModelDomain.VISION,
            modality=ModelModality.MULTIMODAL,
            input_data={"visual_state": None, "screen_description": "test", "context": {}},
        )
        result = container.neural_engine.infer(request)
        assert result is not None
        assert result.model_id == "vision_specialist_v1"
        assert result.confidence >= 0.0

    def test_neural_engine_telemetry_not_empty(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.neural_engine.model_contract import (
            InferenceRequest, ModelDomain, ModelModality,
        )
        container = ApplicationContainer()
        request = InferenceRequest(
            domain=ModelDomain.VISION,
            modality=ModelModality.MULTIMODAL,
            input_data={"visual_state": None, "screen_description": "test", "context": {}},
        )
        container.neural_engine.infer(request)
        summary = container.neural_engine.telemetry_summary()
        assert summary["total_inferences"] >= 1


class TestSelfHealingDiagnostics:
    """G1: DiagnosticsEngine must have 6 real health checks wired."""

    def test_six_checks_registered(self):
        from desktop_agent.core.application_container import ApplicationContainer
        container = ApplicationContainer()
        diag = container.self_healing.diagnostics
        summary = diag.health_summary()
        checks = summary["registered_checks"]
        assert len(checks) >= 6, f"Expected >=6 checks, got {checks}"
        assert "brain_engine" in checks
        assert "memory" in checks
        assert "vision" in checks
        assert "neural_engine" in checks
        assert "trading_engine" in checks
        assert "self_healing" in checks

    def test_diagnostics_periodic_enabled(self):
        from desktop_agent.core.application_container import ApplicationContainer
        container = ApplicationContainer()
        diag = container.self_healing.diagnostics
        summary = diag.health_summary()
        assert summary["enabled"] is True

    def test_check_all_returns_results(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.self_healing.diagnostics import HealthStatus
        container = ApplicationContainer()
        diag = container.self_healing.diagnostics
        results = diag.check_all()
        assert len(results) >= 6
        for r in results:
            assert r.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.FAILING)
            assert r.confidence > 0.0

    def test_check_brain_engine_healthy(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.self_healing.diagnostics import HealthStatus
        container = ApplicationContainer()
        result = container.self_healing.diagnostics.check_one("brain_engine")
        assert result.status == HealthStatus.HEALTHY

    def test_check_memory_healthy(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.self_healing.diagnostics import HealthStatus
        container = ApplicationContainer()
        result = container.self_healing.diagnostics.check_one("memory")
        assert result.status == HealthStatus.HEALTHY

    def test_check_neural_engine_healthy(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.self_healing.diagnostics import HealthStatus
        container = ApplicationContainer()
        result = container.self_healing.diagnostics.check_one("neural_engine")
        assert result.status == HealthStatus.HEALTHY

    def test_check_self_healing_healthy(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.self_healing.diagnostics import HealthStatus
        container = ApplicationContainer()
        result = container.self_healing.diagnostics.check_one("self_healing")
        assert result.status == HealthStatus.HEALTHY

    def test_self_healing_system_status(self):
        from desktop_agent.core.application_container import ApplicationContainer
        container = ApplicationContainer()
        status = container.self_healing.get_system_status()
        assert "health" in status
        assert status["health"]["overall_status"] in ("healthy", "unknown", "degraded")


class TestContainerSingletons:
    """All three subsystems accessible as singletons from DI container."""

    def test_neural_engine_singleton(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c1 = ApplicationContainer()
        c2 = ApplicationContainer()
        assert c1.neural_engine is c2.neural_engine

    def test_self_healing_singleton(self):
        from desktop_agent.core.application_container import ApplicationContainer
        from desktop_agent.self_healing.manager import SelfHealingManager
        SelfHealingManager.reset_instance()
        c1 = ApplicationContainer()
        c2 = ApplicationContainer()
        assert c1.self_healing is c2.self_healing

    def test_all_subsystems_wired_together(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        assert c.neural_engine is not None
        assert c.self_healing is not None
        assert c.universal_controller is not None
        assert c.trading_engine is not None
        assert c.groww_advisor is not None
