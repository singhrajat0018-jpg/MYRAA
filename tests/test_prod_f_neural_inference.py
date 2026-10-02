"""F Production Closure — Prove Real NeuralEngine Inference.

Verifies REAL runtime inference across all 7 specialists.
Labels: REAL / MOCK / UNAVAILABLE.

Tests:
1. Vision specialist — analyzes screen description → VisionAnalysis
2. Trading specialist — analyzes OHLCV/features → trading signals
3. Voice specialist — analyzes transcript → intent cues + emotion
4. Prediction specialist — temporal pattern → forecast
5. Personalization specialist — user context → workflow recommendations
6. Design specialist — requirements → DesignConcept
7. Multimodal specialist — cross-modal fusion → insights
8. Model registry — all 7 registered, health_score > 0
9. Fallback — failed model triggers fallback path
10. Fusion — parallel inference across domains
11. Confidence/uncertainty — all results have confidence in [0,1]
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock

from desktop_agent.neural_engine.engine import NeuralEngine
from desktop_agent.neural_engine.model_contract import (
    ModelSpec, ModelResult, InferenceRequest, FusionResult,
    ModelDomain, ModelModality, ModelStatus, ModelDeployment, LatencyClass,
)


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_neural():
    NeuralEngine.reset_singleton()
    yield
    NeuralEngine.reset_singleton()


def _make_request(domain, modality=ModelModality.TEXT, input_data=None, context=None):
    return InferenceRequest(
        domain=domain,
        modality=modality,
        input_data=input_data or {},
        context=context or {},
    )


# ============================================================
# 1. Vision Specialist — REAL
# ============================================================

class TestVisionSpecialist:

    def test_inference_real(self):
        """REAL: Vision specialist analyzes screen description."""
        from desktop_agent.neural_engine.specialists.vision_specialist import VisionSpecialist
        spec = VisionSpecialist.SPEC
        specialist = VisionSpecialist(ai_manager=None)
        engine = NeuralEngine()
        engine.register_model(spec, specialist.inference)

        request = _make_request(
            ModelDomain.VISION,
            ModelModality.MULTIMODAL,
            input_data={"visual_state": None, "screen_description": "A browser with a search bar", "context": {}},
        )
        result = engine.infer(request)
        assert result.model_id == "vision_specialist_v1"
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
        assert result.output is not None
        assert hasattr(result.output, "objects") or isinstance(result.output, dict)

    def test_inference_no_visual_state(self):
        """REAL: Vision specialist handles missing visual state gracefully."""
        from desktop_agent.neural_engine.specialists.vision_specialist import VisionSpecialist
        specialist = VisionSpecialist(ai_manager=None)
        request = _make_request(
            ModelDomain.VISION,
            ModelModality.MULTIMODAL,
            input_data={"visual_state": None, "screen_description": "", "context": {}},
        )
        result = specialist.inference(request)
        assert result.confidence >= 0.0


# ============================================================
# 2. Trading Specialist — REAL
# ============================================================

class TestTradingSpecialist:

    def test_inference_real_with_features(self):
        """REAL: Trading specialist analyzes structured market features."""
        from desktop_agent.neural_engine.specialists.trading_specialist import TradingSpecialist
        engine = NeuralEngine()
        specialist = TradingSpecialist(trading_engine=MagicMock())
        engine.register_model(TradingSpecialist.SPEC, specialist.inference)

        request = _make_request(
            ModelDomain.TRADING,
            ModelModality.STRUCTURED,
            input_data={
                "symbol": "RELIANCE",
                "features": {
                    "price": 2500.0,
                    "rsi_14": 35.0,
                    "sma_20": 2480.0,
                    "sma_50": 2520.0,
                    "volume_ratio": 1.5,
                    "atr_14": 50.0,
                },
                "ohlcv": [
                    {"open": 2480, "high": 2510, "low": 2470, "close": 2500, "volume": 1000000},
                    {"open": 2490, "high": 2520, "low": 2485, "close": 2510, "volume": 1100000},
                    {"open": 2510, "high": 2530, "low": 2490, "close": 2495, "volume": 900000},
                ],
            },
            context={"symbol": "RELIANCE"},
        )
        result = engine.infer(request)
        assert result.model_id == "trading_specialist_v1"
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
        assert result.output is not None

    def test_inference_empty_features(self):
        """REAL: Trading specialist handles empty features gracefully."""
        from desktop_agent.neural_engine.specialists.trading_specialist import TradingSpecialist
        specialist = TradingSpecialist(trading_engine=MagicMock())
        request = _make_request(
            ModelDomain.TRADING,
            ModelModality.STRUCTURED,
            input_data={"symbol": "TCS", "features": {}, "ohlcv": []},
        )
        result = specialist.inference(request)
        assert result.confidence >= 0.0


# ============================================================
# 3. Voice Specialist — REAL
# ============================================================

class TestVoiceSpecialist:

    def test_inference_real_transcript(self):
        """REAL: Voice specialist analyzes transcript for intent + emotion."""
        from desktop_agent.neural_engine.specialists.voice_specialist import VoiceSpecialist
        engine = NeuralEngine()
        specialist = VoiceSpecialist()
        engine.register_model(VoiceSpecialist.SPEC, specialist.inference)

        request = _make_request(
            ModelDomain.VOICE,
            ModelModality.AUDIO,
            input_data={"transcript": "Open notepad and write a note"},
        )
        result = engine.infer(request)
        assert result.model_id == "voice_specialist_v1"
        assert result.confidence >= 0.0
        assert result.output is not None

    def test_inference_empty_transcript(self):
        """REAL: Voice specialist handles empty input."""
        from desktop_agent.neural_engine.specialists.voice_specialist import VoiceSpecialist
        specialist = VoiceSpecialist()
        request = _make_request(
            ModelDomain.VOICE,
            ModelModality.AUDIO,
            input_data={"transcript": ""},
        )
        result = specialist.inference(request)
        assert result.confidence >= 0.0


# ============================================================
# 4. Prediction Specialist — REAL
# ============================================================

class TestPredictionSpecialist:

    def test_inference_real_temporal(self):
        """REAL: Prediction specialist analyzes temporal pattern."""
        from desktop_agent.neural_engine.specialists.prediction_specialist import PredictionSpecialist
        engine = NeuralEngine()
        specialist = PredictionSpecialist()
        engine.register_model(PredictionSpecialist.SPEC, specialist.inference)

        request = _make_request(
            ModelDomain.PREDICTION,
            ModelModality.TIME_SERIES,
            input_data={
                "series": [10, 12, 15, 13, 18, 20, 22, 25],
                "context": {"type": "stock_price"},
            },
        )
        result = engine.infer(request)
        assert result.model_id == "prediction_specialist_v1"
        assert result.confidence >= 0.0
        assert result.output is not None


# ============================================================
# 5. Personalization Specialist — REAL
# ============================================================

class TestPersonalizationSpecialist:

    def test_inference_real_user_context(self):
        """REAL: Personalization specialist recommends workflow based on context."""
        from desktop_agent.neural_engine.specialists.personalization_specialist import PersonalizationSpecialist
        engine = NeuralEngine()
        specialist = PersonalizationSpecialist(memory_manager=None)
        engine.register_model(PersonalizationSpecialist.SPEC, specialist.inference)

        request = _make_request(
            ModelDomain.PERSONALIZATION,
            ModelModality.TEXT,
            input_data={
                "current_task": "coding",
                "time_of_day": "morning",
                "recent_actions": ["open_vscode", "run_tests"],
            },
        )
        result = engine.infer(request)
        assert result.model_id == "personalization_specialist_v1"
        assert result.confidence >= 0.0
        assert result.output is not None


# ============================================================
# 7. Multimodal Specialist — REAL
# ============================================================

class TestMultimodalSpecialist:

    def test_inference_real_cross_modal(self):
        """REAL: Multimodal specialist fuses cross-modal insights."""
        from desktop_agent.neural_engine.specialists.multimodal_specialist import MultimodalSpecialist
        engine = NeuralEngine()
        specialist = MultimodalSpecialist()
        engine.register_model(MultimodalSpecialist.SPEC, specialist.inference)

        request = _make_request(
            ModelDomain.MULTIMODAL,
            ModelModality.MULTIMODAL,
            input_data={
                "visual_state": "A trading dashboard with NIFTY chart",
                "transcript": "Show me NIFTY analysis",
                "context": {"app": "groww"},
            },
        )
        result = engine.infer(request)
        assert result.model_id == "multimodal_specialist_v1"
        assert result.confidence >= 0.0
        assert result.output is not None

    def test_inference_minimal_context(self):
        """REAL: Multimodal specialist handles minimal input."""
        from desktop_agent.neural_engine.specialists.multimodal_specialist import MultimodalSpecialist
        specialist = MultimodalSpecialist()
        request = _make_request(
            ModelDomain.MULTIMODAL,
            ModelModality.MULTIMODAL,
            input_data={},
        )
        result = specialist.inference(request)
        assert result.confidence >= 0.0


# ============================================================
# 8. Model Registry — All 7 Registered
# ============================================================

class TestModelRegistry:

    def test_container_registers_all_specialists(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        ne = c.neural_engine
        models = ne.list_models()
        model_ids = [m.model_id for m in models]
        # NOTE (documented stale expectation, §61): the Python design_specialist
        # was retired — design intelligence is owned by the TS DesignCore. The
        # authoritative registry registers 6 specialists (count updated from the
        # historical 7 that included design_specialist_v1).
        assert len(models) >= 6
        expected = [
            "vision_specialist_v1", "trading_specialist_v1", "voice_specialist_v1",
            "prediction_specialist_v1", "personalization_specialist_v1",
            "multimodal_specialist_v1",
        ]
        for eid in expected:
            assert eid in model_ids, f"{eid} not registered"

    def test_all_models_healthy(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        health = c.neural_engine.model_health()
        for model_id, info in health.items():
            assert info["status"] in ("active", "staged"), f"{model_id} status={info['status']}"
            assert info["health_score"] > 0.0, f"{model_id} health_score=0"

    def test_select_best_for_domain(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        spec = c.neural_engine.select_best_for_domain(ModelDomain.VISION)
        assert spec is not None
        assert spec.model_id == "vision_specialist_v1"

    def test_select_best_trading(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        spec = c.neural_engine.select_best_for_domain(ModelDomain.TRADING)
        assert spec is not None
        assert spec.model_id == "trading_specialist_v1"


# ============================================================
# 9. Fallback — Failed Model Triggers Fallback
# ============================================================

class TestFallback:

    def test_fallback_on_model_failure(self):
        """When primary model fails, fallback is used."""
        def failing_inference(request):
            raise RuntimeError("primary model failed")

        def fallback_inference(request):
            return ModelResult(
                model_id="test_fallback",
                output="fallback result",
                confidence=0.3,
                uncertainty=0.7,
                latency_ms=1.0,
                timestamp=time.time(),
                source="fallback",
            )

        spec = ModelSpec(
            model_id="test_model",
            domain=ModelDomain.GENERAL,
            version="1.0.0",
            modality=ModelModality.TEXT,
            capabilities=["test"],
            input_schema={"x": "str"},
            output_schema={"y": "str"},
            latency_class=LatencyClass.FAST,
            deployment=ModelDeployment.LOCAL,
            resource_requirements={},
        )
        engine = NeuralEngine()
        engine.register_model(spec, failing_inference, fallback_inference)

        request = _make_request(ModelDomain.GENERAL)
        result = engine.infer(request)
        assert result.model_id == "test_model_fallback"
        assert result.confidence == 0.3
        assert any("fallback" in w.lower() or "Fallback" in w for w in result.warnings)

    def test_no_model_returns_no_model(self):
        """When no model matches, result indicates missing model."""
        engine = NeuralEngine()
        request = _make_request(ModelDomain.VISION)
        result = engine.infer(request)
        assert result.source == "no_model"
        assert result.confidence == 0.0


# ============================================================
# 10. Fusion — Parallel Inference
# ============================================================

class TestFusion:

    def test_infer_parallel(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        requests = [
            _make_request(ModelDomain.VISION, ModelModality.MULTIMODAL,
                          input_data={"visual_state": None, "screen_description": "test", "context": {}}),
            _make_request(ModelDomain.TRADING, ModelModality.STRUCTURED,
                          input_data={"symbol": "RELIANCE", "features": {"price": 2500}, "ohlcv": []}),
            _make_request(ModelDomain.VOICE, ModelModality.AUDIO,
                          input_data={"transcript": "hello"}),
        ]
        results = c.neural_engine.infer_parallel(requests, timeout_ms=10000)
        assert len(results) == 3
        for r in results:
            assert r.confidence >= 0.0
            assert r.model_id != "timeout"


# ============================================================
# 11. Confidence / Uncertainty
# ============================================================

class TestConfidenceUncertainty:

    def test_all_results_have_confidence(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        domains = [
            (ModelDomain.VISION, ModelModality.MULTIMODAL,
             {"visual_state": None, "screen_description": "desktop", "context": {}}),
            (ModelDomain.TRADING, ModelModality.STRUCTURED,
             {"symbol": "TCS", "features": {"price": 3500}, "ohlcv": []}),
            (ModelDomain.VOICE, ModelModality.AUDIO,
             {"transcript": "test"}),
            (ModelDomain.PREDICTION, ModelModality.TIME_SERIES,
             {"series": [1, 2, 3]}),
            (ModelDomain.PERSONALIZATION, ModelModality.TEXT,
             {"current_task": "coding"}),
            # ModelDomain.DESIGN was removed when the Python design_specialist
            # retired (design is owned by the TS DesignCore) — no DESIGN case.
            (ModelDomain.MULTIMODAL, ModelModality.MULTIMODAL,
             {"visual_state": "screen", "transcript": "hello"}),
        ]
        for domain, modality, input_data in domains:
            req = _make_request(domain, modality, input_data=input_data)
            result = c.neural_engine.infer(req)
            assert 0.0 <= result.confidence <= 1.0, f"{domain.value}: confidence={result.confidence}"
            assert 0.0 <= result.uncertainty <= 1.0, f"{domain.value}: uncertainty={result.uncertainty}"

    def test_telemetry_after_inference(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        req = _make_request(
            ModelDomain.VISION, ModelModality.MULTIMODAL,
            input_data={"visual_state": None, "screen_description": "test", "context": {}},
        )
        c.neural_engine.infer(req)
        summary = c.neural_engine.telemetry_summary()
        assert summary["total_inferences"] >= 1

    def test_cache_put_and_get(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        req = _make_request(
            ModelDomain.VISION, ModelModality.MULTIMODAL,
            input_data={"visual_state": None, "screen_description": "cached", "context": {}},
        )
        req.cache_key = "test_cache_key_123"
        r1 = c.neural_engine.infer(req)
        r2 = c.neural_engine.infer(req)
        assert r2.cached is True
        assert r2.latency_ms == 0.0

    def test_cache_invalidation(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        req = _make_request(
            ModelDomain.VISION, ModelModality.MULTIMODAL,
            input_data={"visual_state": None, "screen_description": "invalidate", "context": {}},
        )
        req.cache_key = "invalidate_test"
        c.neural_engine.infer(req)
        c.neural_engine.invalidate_cache("invalidate_test")
        assert c.neural_engine.cache_stats()["size"] == 0

    def test_unregister_model(self):
        from desktop_agent.neural_engine.specialists.vision_specialist import VisionSpecialist
        engine = NeuralEngine()
        spec = VisionSpecialist.SPEC
        s = VisionSpecialist(ai_manager=None)
        engine.register_model(spec, s.inference)
        assert engine.get_model("vision_specialist_v1") is not None
        engine.unregister_model("vision_specialist_v1")
        assert engine.get_model("vision_specialist_v1") is None


# ============================================================
# 12. ModelSpec Contract
# ============================================================

class TestModelSpecContract:

    def test_spec_matches_domain(self):
        spec = ModelSpec(
            model_id="test", domain=ModelDomain.VISION, version="1.0",
            modality=ModelModality.MULTIMODAL, capabilities=[],
            input_schema={}, output_schema={},
            latency_class=None, deployment=ModelDeployment.LOCAL,
            resource_requirements={},
        )
        assert spec.matches_domain(ModelDomain.VISION)

    def test_spec_matches_modality(self):
        spec = ModelSpec(
            model_id="test", domain=ModelDomain.VISION, version="1.0",
            modality=ModelModality.MULTIMODAL, capabilities=[],
            input_schema={}, output_schema={},
            latency_class=None, deployment=ModelDeployment.LOCAL,
            resource_requirements={},
        )
        assert spec.matches_modality(ModelModality.TEXT)
        assert spec.matches_modality(ModelModality.IMAGE)
        assert spec.matches_modality(ModelModality.MULTIMODAL)
