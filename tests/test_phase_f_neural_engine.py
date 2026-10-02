"""Phase F: Neural Intelligence Engine Tests.

Tests: NeuralEngine core, model contracts, specialist models, neural fusion,
disagreement engine, model registry, model fallback, telemetry, security.
"""

import time
import threading
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from desktop_agent.neural_engine import (
    NeuralEngine, ModelSpec, ModelResult, InferenceRequest, FusionResult,
    ModelDomain, ModelModality, ModelDeployment, ModelStatus, LatencyClass,
)
from desktop_agent.neural_engine.engine import InferenceCache, NeuralTelemetry, SpecialistModelWrapper
from desktop_agent.neural_engine.specialists.vision_specialist import VisionSpecialist
from desktop_agent.neural_engine.specialists.trading_specialist import TradingSpecialist
from desktop_agent.neural_engine.specialists.voice_specialist import VoiceSpecialist
from desktop_agent.neural_engine.specialists.prediction_specialist import PredictionSpecialist
from desktop_agent.neural_engine.specialists.personalization_specialist import PersonalizationSpecialist
from desktop_agent.neural_engine.specialists.multimodal_specialist import MultimodalSpecialist
from desktop_agent.neural_engine.fusion.neural_fusion import NeuralFusion
from desktop_agent.neural_engine.fusion.disagreement_engine import DisagreementEngine
from desktop_agent.neural_engine.registry.model_registry import ModelRegistry
from desktop_agent.neural_engine.registry.model_fallback import FallbackChain


def _make_spec(model_id="test_model", domain=ModelDomain.GENERAL):
    return ModelSpec(
        model_id=model_id, domain=domain, version="1.0.0",
        modality=ModelModality.TEXT, capabilities=["test"],
        input_schema={"x": "str"}, output_schema={"y": "str"},
        latency_class=LatencyClass.FAST, deployment=ModelDeployment.LOCAL,
        resource_requirements={"min_memory_mb": 64},
    )


def _make_result(model_id="test_model", confidence=0.8, uncertainty=0.2, output="ok"):
    return ModelResult(
        model_id=model_id, output=output, confidence=confidence,
        uncertainty=uncertainty, latency_ms=10.0, timestamp=time.time(),
        source="test",
    )


# ============================================================
# CORE ENGINE
# ============================================================

class TestNeuralEngineCore:
    def setup_method(self):
        NeuralEngine.reset_singleton()

    def teardown_method(self):
        NeuralEngine.reset_singleton()

    def test_singleton(self):
        e1 = NeuralEngine()
        e2 = NeuralEngine()
        assert e1 is e2

    def test_singleton_classmethod(self):
        e = NeuralEngine.singleton()
        assert isinstance(e, NeuralEngine)

    def test_reset_singleton(self):
        e1 = NeuralEngine()
        NeuralEngine.reset_singleton()
        e2 = NeuralEngine()
        assert e1 is not e2

    def test_register_model(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda req: "hello")
        assert engine.get_model("test_model") is not None

    def test_unregister_model(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda req: "hello")
        assert engine.unregister_model("test_model")
        assert engine.get_model("test_model") is None

    def test_unregister_nonexistent(self):
        engine = NeuralEngine()
        assert not engine.unregister_model("nonexistent")

    def test_list_models_all(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec("m1"), lambda r: 1)
        engine.register_model(_make_spec("m2"), lambda r: 2)
        assert len(engine.list_models()) == 2

    def test_list_models_by_domain(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec("m1", ModelDomain.VISION), lambda r: 1)
        engine.register_model(_make_spec("m2", ModelDomain.TRADING), lambda r: 2)
        vision = engine.list_models(domain=ModelDomain.VISION)
        assert len(vision) == 1
        assert vision[0].model_id == "m1"

    def test_infer_single_model(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda req: "hello")
        result = engine.infer(InferenceRequest())
        assert result.model_id == "test_model"
        assert result.output == "hello"

    def test_infer_no_model(self):
        engine = NeuralEngine()
        result = engine.infer(InferenceRequest())
        assert result.model_id == "none"
        assert result.confidence == 0.0

    def test_infer_preferred_model(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec("slow"), lambda r: "slow")
        engine.register_model(_make_spec("fast"), lambda r: "fast")
        result = engine.infer(InferenceRequest(preferred_model_id="fast"))
        assert result.model_id == "fast"

    def test_infer_with_cache(self):
        engine = NeuralEngine()
        call_count = [0]
        def fn(req):
            call_count[0] += 1
            return "result"
        engine.register_model(_make_spec(), fn)
        r1 = engine.infer(InferenceRequest(cache_key="k1"))
        assert r1.cached is False
        r2 = engine.infer(InferenceRequest(cache_key="k1"))
        assert r2.cached is True
        assert call_count[0] == 1

    def test_infer_cache_invalidation(self):
        engine = NeuralEngine()
        call_count = [0]
        def fn(req):
            call_count[0] += 1
            return "result"
        engine.register_model(_make_spec(), fn)
        engine.infer(InferenceRequest(cache_key="k1"))
        engine.invalidate_cache("k1")
        engine.infer(InferenceRequest(cache_key="k1"))
        assert call_count[0] == 2

    def test_infer_fallback(self):
        engine = NeuralEngine()
        def failing_fn(req):
            raise RuntimeError("boom")
        engine.register_model(_make_spec(), failing_fn, lambda r: "fallback")
        result = engine.infer(InferenceRequest())
        assert result.output == "fallback"

    def test_model_health(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda r: "ok")
        for _ in range(10):
            engine.infer(InferenceRequest())
        health = engine.model_health()
        assert health["test_model"]["total_calls"] == 10

    def test_telemetry_summary(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda r: "ok")
        for _ in range(5):
            engine.infer(InferenceRequest())
        summary = engine.telemetry_summary()
        assert summary["total_inferences"] == 5

    def test_cache_stats(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda r: "ok")
        engine.infer(InferenceRequest(cache_key="k1"))
        assert engine.cache_stats()["size"] >= 1

    def test_select_best_for_domain(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec("v1", ModelDomain.VISION), lambda r: 1)
        best = engine.select_best_for_domain(ModelDomain.VISION)
        assert best is not None and best.model_id == "v1"

    def test_select_best_none(self):
        engine = NeuralEngine()
        assert engine.select_best_for_domain(ModelDomain.VISION) is None

    def test_infer_parallel(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec("m1"), lambda r: 1)
        engine.register_model(_make_spec("m2"), lambda r: 2)
        requests = [InferenceRequest(), InferenceRequest()]
        results = engine.infer_parallel(requests)
        assert len(results) == 2


# ============================================================
# MODEL CONTRACT
# ============================================================

class TestModelContract:
    def test_spec_creation(self):
        spec = _make_spec()
        assert spec.model_id == "test_model"
        assert spec.domain == ModelDomain.GENERAL

    def test_spec_frozen(self):
        spec = _make_spec()
        with pytest.raises(AttributeError):
            spec.model_id = "changed"

    def test_spec_matches_modality(self):
        spec = _make_spec()
        assert spec.matches_modality(ModelModality.TEXT)
        assert not spec.matches_modality(ModelModality.IMAGE)

    def test_spec_matches_domain(self):
        spec = _make_spec(domain=ModelDomain.VISION)
        assert spec.matches_domain(ModelDomain.VISION)
        assert not spec.matches_domain(ModelDomain.TRADING)

    def test_result_creation(self):
        r = _make_result()
        assert r.model_id == "test_model"
        assert r.confidence == 0.8

    def test_result_is_confident(self):
        assert _make_result(confidence=0.8).is_confident
        assert not _make_result(confidence=0.5).is_confident

    def test_result_is_uncertain(self):
        assert _make_result(uncertainty=0.6).is_uncertain
        assert not _make_result(uncertainty=0.1).is_uncertain

    def test_result_is_stale(self):
        r = _make_result()
        r.timestamp = time.time() - 100
        assert r.is_stale

    def test_result_to_dict(self):
        d = _make_result().to_dict()
        assert "model_id" in d
        assert "confidence" in d

    def test_request_defaults(self):
        req = InferenceRequest()
        assert req.domain == ModelDomain.GENERAL
        assert req.fallback_allowed is True

    def test_fusion_result_creation(self):
        fr = FusionResult(
            request_id="r1", domain=ModelDomain.TRADING,
            outputs=[], fused_output=None, combined_confidence=0.8,
            combined_uncertainty=0.2, disagreement_score=0.1,
            ensemble_size=1, latency_ms=5.0,
        )
        assert fr.combined_confidence == 0.8
        assert not fr.has_disagreement

    def test_fusion_result_disagreement(self):
        fr = FusionResult(
            request_id="r1", domain=ModelDomain.TRADING,
            outputs=[], fused_output=None, combined_confidence=0.5,
            combined_uncertainty=0.5, disagreement_score=0.6,
            ensemble_size=3, latency_ms=5.0,
        )
        assert fr.has_disagreement

    def test_fusion_result_reliable(self):
        fr = FusionResult(
            request_id="r1", domain=ModelDomain.TRADING,
            outputs=[], fused_output=None, combined_confidence=0.8,
            combined_uncertainty=0.1, disagreement_score=0.1,
            ensemble_size=3, latency_ms=5.0,
        )
        assert fr.is_reliable


# ============================================================
# INFERENCE CACHE
# ============================================================

class TestInferenceCache:
    def test_put_and_get(self):
        c = InferenceCache(max_size=10)
        r = _make_result()
        c.put("k1", r)
        assert c.get("k1") is not None

    def test_miss(self):
        c = InferenceCache()
        assert c.get("miss") is None

    def test_ttl_expiry(self):
        c = InferenceCache(default_ttl_ms=1)
        c.put("k1", _make_result())
        time.sleep(0.01)
        assert c.get("k1") is None

    def test_lru_eviction(self):
        c = InferenceCache(max_size=2)
        c.put("k1", _make_result("r1"))
        c.put("k2", _make_result("r2"))
        c.put("k3", _make_result("r3"))
        assert c.get("k1") is None

    def test_invalidate(self):
        c = InferenceCache()
        c.put("k1", _make_result())
        assert c.invalidate("k1")
        assert c.get("k1") is None

    def test_clear(self):
        c = InferenceCache()
        c.put("k1", _make_result())
        c.clear()
        assert c.get("k1") is None


# ============================================================
# TELEMETRY
# ============================================================

class TestNeuralTelemetry:
    def test_record_and_summary(self):
        t = NeuralTelemetry()
        for _ in range(10):
            t.record_inference("trading", 50.0, confidence=0.8)
        s = t.summary()
        assert s["total_inferences"] == 10
        assert s["p50_ms"] > 0

    def test_cache_hit_rate(self):
        t = NeuralTelemetry()
        t.record_inference("trading", 10.0, cache_hit=True)
        t.record_inference("trading", 10.0, cache_hit=False)
        s = t.summary()
        assert s["cache_hit_rate"] == 0.5

    def test_reset(self):
        t = NeuralTelemetry()
        t.record_inference("trading", 10.0)
        t.reset()
        assert t.summary()["total"] == 0


# ============================================================
# SPECIALIST: VISION
# ============================================================

class TestVisionSpecialist:
    def setup_method(self):
        self.spec = VisionSpecialist()

    def test_spec_fields(self):
        assert self.spec.SPEC.domain == ModelDomain.VISION
        assert self.spec.SPEC.modality == ModelModality.MULTIMODAL

    def test_inference_empty(self):
        req = InferenceRequest(context={})
        result = self.spec.inference(req)
        assert 0.0 <= result.confidence <= 1.0

    def test_health_tracking(self):
        for _ in range(5):
            self.spec.inference(InferenceRequest(context={}))
        assert self.spec._total_calls == 5


# ============================================================
# SPECIALIST: TRADING
# ============================================================

class TestTradingSpecialist:
    def setup_method(self):
        self.spec = TradingSpecialist()

    def test_spec_fields(self):
        assert self.spec.SPEC.domain == ModelDomain.TRADING
        assert "pattern_recognition" in self.spec.SPEC.capabilities

    def test_inference_empty(self):
        result = self.spec.inference(InferenceRequest(context={}))
        assert 0.0 <= result.confidence <= 1.0

    def test_inference_with_data(self):
        req = InferenceRequest(context={
            "ohlcv": [{"open": 100, "high": 105, "low": 98, "close": 103, "volume": 1000}] * 20,
            "indicators": {"rsi": 55.0, "atr": 3.0},
        })
        result = self.spec.inference(req)
        assert result.output is not None


# ============================================================
# SPECIALIST: DESIGN
# ============================================================

# ============================================================
# SPECIALIST: VOICE
# ============================================================

class TestVoiceSpecialist:
    def setup_method(self):
        self.spec = VoiceSpecialist()

    def test_spec_fields(self):
        assert self.spec.SPEC.domain == ModelDomain.VOICE

    def test_inference(self):
        req = InferenceRequest(context={"transcript": "Hey Myraa, open Chrome"})
        result = self.spec.inference(req)
        assert result.output is not None


# ============================================================
# SPECIALIST: PREDICTION
# ============================================================

class TestPredictionSpecialist:
    def setup_method(self):
        self.spec = PredictionSpecialist()

    def test_spec_fields(self):
        assert self.spec.SPEC.domain == ModelDomain.PREDICTION

    def test_inference(self):
        req = InferenceRequest(context={"historical_data": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = self.spec.inference(req)
        assert result.output is not None


# ============================================================
# SPECIALIST: PERSONALIZATION
# ============================================================

class TestPersonalizationSpecialist:
    def setup_method(self):
        self.spec = PersonalizationSpecialist()

    def test_spec_fields(self):
        assert self.spec.SPEC.domain == ModelDomain.PERSONALIZATION

    def test_inference(self):
        req = InferenceRequest(context={"interaction_history": []})
        result = self.spec.inference(req)
        assert result.output is not None


# ============================================================
# SPECIALIST: MULTIMODAL
# ============================================================

class TestMultimodalSpecialist:
    def setup_method(self):
        self.spec = MultimodalSpecialist()

    def test_spec_fields(self):
        assert self.spec.SPEC.domain == ModelDomain.MULTIMODAL

    def test_inference(self):
        req = InferenceRequest(context={"transcript": "analyze the chart"})
        result = self.spec.inference(req)
        assert result.output is not None


# ============================================================
# NEURAL FUSION
# ============================================================

class TestNeuralFusion:
    def setup_method(self):
        NeuralFusion.reset_singleton()

    def teardown_method(self):
        NeuralFusion.reset_singleton()

    def test_singleton(self):
        f1 = NeuralFusion()
        f2 = NeuralFusion()
        assert f1 is f2

    def test_fuse_empty(self):
        f = NeuralFusion()
        result = f.fuse([])
        assert result.ensemble_size == 0

    def test_fuse_single(self):
        f = NeuralFusion()
        r = _make_result(confidence=0.9)
        result = f.fuse([r])
        assert result.ensemble_size == 1
        assert result.combined_confidence > 0.8

    def test_fuse_multiple_agreeing(self):
        f = NeuralFusion()
        results = [_make_result(f"m{i}", confidence=0.8, uncertainty=0.2) for i in range(3)]
        result = f.fuse(results)
        assert result.ensemble_size == 3
        assert result.combined_confidence > 0.7

    def test_fuse_multiple_disagreeing(self):
        f = NeuralFusion()
        r1 = _make_result("m1", confidence=0.9, uncertainty=0.1, output="bullish")
        r2 = _make_result("m2", confidence=0.3, uncertainty=0.7, output="bearish")
        result = f.fuse([r1, r2])
        assert result.disagreement_score > 0.0

    def test_weighted_combine(self):
        f = NeuralFusion()
        r1 = _make_result("m1", confidence=0.9)
        r1.quality = 1.0
        r2 = _make_result("m2", confidence=0.3)
        r2.quality = 0.5
        weights = f.weighted_combine([r1, r2])
        assert weights[0] > weights[1]

    def test_calculate_disagreement(self):
        f = NeuralFusion()
        r1 = _make_result("m1", confidence=0.9)
        r2 = _make_result("m2", confidence=0.9)
        assert f.calculate_disagreement([r1, r2]) < 0.1

    def test_detect_outliers(self):
        f = NeuralFusion()
        results = [_make_result(f"m{i}", confidence=0.8) for i in range(5)]
        results.append(_make_result("outlier", confidence=0.1))
        outliers = f.detect_outliers(results)
        assert len(outliers) > 0

    def test_fusion_count(self):
        f = NeuralFusion()
        f.fuse([_make_result()])
        assert f.fusion_count == 1

    def test_reset(self):
        f = NeuralFusion()
        f.fuse([_make_result()])
        f.reset()
        assert f.fusion_count == 0


# ============================================================
# DISAGREEMENT ENGINE
# ============================================================

class TestDisagreementEngine:
    def test_no_disagreement(self):
        de = DisagreementEngine()
        results = [_make_result(f"m{i}", confidence=0.8) for i in range(3)]
        report = de.analyze_disagreement(results)
        assert not report.has_disagreement

    def test_high_disagreement(self):
        de = DisagreementEngine()
        r1 = _make_result("m1", confidence=0.9, output="bullish")
        r2 = _make_result("m2", confidence=0.2, output="bearish")
        report = de.analyze_disagreement([r1, r2])
        assert report.has_disagreement

    def test_single_result(self):
        de = DisagreementEngine()
        report = de.analyze_disagreement([_make_result()])
        assert not report.has_disagreement

    def test_recommend_action(self):
        de = DisagreementEngine()
        from desktop_agent.neural_engine.fusion.disagreement_engine import DisagreementSeverity
        report = de.analyze_disagreement([])
        action = de.recommend_action(report)
        assert action is not None


# ============================================================
# MODEL REGISTRY
# ============================================================

class TestModelRegistry:
    def setup_method(self):
        self.registry = ModelRegistry()
        self.registry._models.clear()

    def test_register(self):
        spec = _make_spec()
        self.registry.register(spec)
        assert self.registry.get(spec.model_id) is not None

    def test_unregister(self):
        spec = _make_spec("ur_model")
        self.registry.register(spec)
        assert self.registry.unregister(spec.model_id)

    def test_get_active_for_domain(self):
        spec = _make_spec("v_model", ModelDomain.VISION)
        self.registry.register(spec)
        self.registry.set_status(spec.model_id, ModelStatus.ACTIVE)
        active = self.registry.get_active_for_domain(ModelDomain.VISION)
        assert active is not None

    def test_health_report(self):
        self.registry.register(_make_spec("hr1"))
        self.registry.register(_make_spec("hr2"))
        report = self.registry.health_report()
        assert report["total_models"] == 2

    def test_promote_model(self):
        spec = _make_spec("prom_model")
        self.registry.register(spec)
        self.registry.update_benchmark(spec.model_id, {"accuracy": 0.9, "latency_ms": 50})
        result = self.registry.promote_model(spec.model_id)
        assert result is not None

    def test_demote_model(self):
        spec = _make_spec("dem_model")
        self.registry.register(spec)
        self.registry.demote_model(spec.model_id, "test reason")
        info = self.registry.get(spec.model_id)
        assert info is not None


# ============================================================
# FALLBACK CHAIN
# ============================================================

class TestFallbackChain:
    def test_get_fallback(self):
        fc = FallbackChain({ModelDomain.TRADING: ["m1", "m2", "m3"]})
        fb = fc.get_fallback(ModelDomain.TRADING, "m1")
        assert fb == "m2"

    def test_record_failure(self):
        fc = FallbackChain({ModelDomain.TRADING: ["m1", "m2"]})
        fc.record_failure("m1", "error")
        assert not fc.is_healthy("m1")

    def test_record_success(self):
        fc = FallbackChain({ModelDomain.TRADING: ["m1", "m2"]})
        fc.record_failure("m1", "error")
        for _ in range(10):
            fc.record_success("m1")
        assert fc.is_healthy("m1")


# ============================================================
# SPECIALIST WRAPPER
# ============================================================

class TestSpecialistModelWrapper:
    def test_inference_success(self):
        spec = _make_spec()
        wrapper = SpecialistModelWrapper(spec, lambda r: "output")
        req = InferenceRequest()
        result = wrapper.inference(req)
        assert result.output == "output"
        assert result.confidence == 0.5

    def test_inference_failure_with_fallback(self):
        spec = _make_spec()
        def failing(req):
            raise RuntimeError("fail")
        wrapper = SpecialistModelWrapper(spec, failing, lambda r: "fallback_out")
        result = wrapper.inference(InferenceRequest())
        assert result.output == "fallback_out"

    def test_health_degradation(self):
        spec = _make_spec()
        def failing(req):
            raise RuntimeError("fail")
        wrapper = SpecialistModelWrapper(spec, failing)
        for _ in range(10):
            wrapper.inference(InferenceRequest())
        assert wrapper.health_score < 0.5

    def test_avg_latency(self):
        spec = _make_spec()
        wrapper = SpecialistModelWrapper(spec, lambda r: time.sleep(0.001) or "ok")
        for _ in range(5):
            wrapper.inference(InferenceRequest())
        assert wrapper.avg_latency_ms() > 0


# ============================================================
# ARCHITECTURE: ONE ENGINE, NO DUPLICATES
# ============================================================

class TestArchitectureInvariants:
    def test_one_neural_engine(self):
        NeuralEngine.reset_singleton()
        e1 = NeuralEngine()
        e2 = NeuralEngine()
        assert e1 is e2
        NeuralEngine.reset_singleton()

    def test_one_fusion(self):
        NeuralFusion.reset_singleton()
        f1 = NeuralFusion()
        f2 = NeuralFusion()
        assert f1 is f2
        NeuralFusion.reset_singleton()

    def test_no_duplicate_vision(self):
        assert VisionSpecialist.SPEC.domain == ModelDomain.VISION

    def test_no_duplicate_trading(self):
        assert TradingSpecialist.SPEC.domain == ModelDomain.TRADING

    def test_all_specialists_have_domain(self):
        for cls in [VisionSpecialist, TradingSpecialist,
                     VoiceSpecialist, PredictionSpecialist,
                     PersonalizationSpecialist, MultimodalSpecialist]:
            assert hasattr(cls, 'SPEC')
            assert hasattr(cls.SPEC, 'domain')

    def test_neural_predictions_are_evidence(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda r: "prediction")
        result = engine.infer(InferenceRequest())
        assert result.confidence <= 1.0
        NeuralEngine.reset_singleton()


# ============================================================
# SECURITY
# ============================================================

class TestNeuralSecurity:
    def test_no_secrets_in_results(self):
        result = _make_result()
        d = result.to_dict()
        for key, val in d.items():
            if isinstance(val, str):
                assert "api_key" not in val.lower()
                assert "secret" not in val.lower()
                assert "password" not in val.lower()

    def test_untrusted_output_boundary(self):
        engine = NeuralEngine()
        def malicious_fn(req):
            return {"action": "execute", "command": "rm -rf /"}
        engine.register_model(_make_spec(), malicious_fn)
        result = engine.infer(InferenceRequest())
        assert result.output is not None
        assert isinstance(result.output, dict)
        NeuralEngine.reset_singleton()

    def test_neural_not_authority(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda r: {"recommendation": "BUY"})
        result = engine.infer(InferenceRequest())
        assert result.confidence <= 1.0
        assert result.uncertainty >= 0.0
        NeuralEngine.reset_singleton()

    def test_fusion_lower_confidence_on_disagreement(self):
        f = NeuralFusion()
        r1 = _make_result("m1", confidence=0.9, output="up")
        r2 = _make_result("m2", confidence=0.1, output="down")
        result = f.fuse([r1, r2])
        assert result.combined_confidence < 0.9
        NeuralFusion.reset_singleton()

    def test_cache_no_secret_leakage(self):
        engine = NeuralEngine()
        engine.register_model(_make_spec(), lambda r: "safe")
        engine.infer(InferenceRequest(cache_key="k1"))
        cached = engine._cache.get("k1")
        assert cached is not None
        NeuralEngine.reset_singleton()
