"""Phase 10.10-10.11 — Model contracts + circuit breaker validation.

Tests:
1. OllamaProvider contract: generate() and stream_generate() return correct shapes
2. CircuitBreaker state machine: CLOSED→OPEN→HALF_OPEN→CLOSED transitions
3. CircuitBreaker thread safety
4. CircuitBreaker stats accuracy
"""
import pytest
import sys
import os
import time
import threading

sys.path.insert(0, os.getcwd())

from desktop_agent.brain.ai.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState, CircuitBreakerStats,
)


# ── CircuitBreaker unit tests ────────────────────────────────

class TestCircuitBreakerStateMachine:
    """Validate CLOSED→OPEN→HALF_OPEN→CLOSED transitions."""

    def test_starts_closed(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_open_after_threshold(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_rejects_when_open(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=60))
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_transitions_to_half_open_after_cooldown(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2, cooldown_seconds=0.1,
        ))
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_probe(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2, cooldown_seconds=0.1,
        ))
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_half_open_rejects_after_max_probes(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2, cooldown_seconds=0.1, half_open_max_probes=1,
        ))
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.allow_request() is True   # first probe
        assert cb.allow_request() is False  # probe limit reached

    def test_half_open_success_recovers_to_closed(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2, cooldown_seconds=0.1, success_threshold=2,
        ))
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2, cooldown_seconds=0.1,
        ))
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset_returns_to_closed(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerStats:
    """Validate stats accuracy."""

    def test_stats_initial_state(self):
        cb = CircuitBreaker("test")
        s = cb.stats()
        assert s.state == "closed"
        assert s.consecutive_failures == 0
        assert s.total_successes == 0
        assert s.total_failures == 0
        assert s.total_rejected == 0

    def test_stats_after_failures(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure()
        cb.record_failure()
        s = cb.stats()
        assert s.consecutive_failures == 2
        assert s.total_failures == 2

    def test_stats_after_rejection(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=60))
        cb.record_failure()
        cb.record_failure()
        cb.allow_request()
        s = cb.stats()
        assert s.total_rejected == 1

    def test_stats_success_count(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        cb.record_success()
        s = cb.stats()
        assert s.total_successes == 2


class TestCircuitBreakerThreadSafety:
    """Verify concurrent access doesn't corrupt state."""

    def test_concurrent_failures(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=100))
        errors = []

        def fail_worker():
            try:
                for _ in range(50):
                    cb.record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        s = cb.stats()
        assert s.total_failures == 200

    def test_concurrent_mixed_operations(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=500))
        errors = []

        def mixed_worker():
            try:
                for _ in range(100):
                    cb.record_success()
                    cb.record_failure()
                    cb.allow_request()
                    cb.stats()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mixed_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ── OllamaProvider contract tests ────────────────────────────

class TestOllamaProviderContract:
    """Validate OllamaProvider interface without requiring Ollama server."""

    def test_import_provider(self):
        from desktop_agent.brain.ai.providers.ollama_provider import OllamaProvider
        assert OllamaProvider is not None

    def test_provider_has_required_methods(self):
        from desktop_agent.brain.ai.providers.ollama_provider import OllamaProvider
        assert hasattr(OllamaProvider, "generate")
        assert hasattr(OllamaProvider, "stream_generate")

    def test_provider_config_defaults(self):
        from desktop_agent.brain.ai.providers.ollama_provider import OllamaProvider
        p = OllamaProvider()
        assert "127.0.0.1" in p.host or "localhost" in p.host

    def test_circuit_breaker_wired(self):
        from desktop_agent.brain.ai.providers.ollama_provider import OllamaProvider
        p = OllamaProvider()
        assert hasattr(p, "_circuit")


# ── Model contract tests ─────────────────────────────────────

class TestFastCoreModelContract:
    """Validate FastCoreOutput dataclass contract."""

    def test_output_has_all_required_fields(self):
        from desktop_agent.fastcore.classifier import FastCoreClassifier
        fc = FastCoreClassifier()
        out = fc.classify("hello")
        assert hasattr(out, "task_type")
        assert hasattr(out, "response_mode")
        assert hasattr(out, "complexity")
        assert hasattr(out, "model_route")
        assert hasattr(out, "safety_class")
        assert hasattr(out, "confidence")
        assert hasattr(out, "tools_required")
        assert hasattr(out, "tool_names")
        assert hasattr(out, "freshness_required")
        assert hasattr(out, "escalate")
        assert hasattr(out, "reasoning")

    def test_confidence_is_bounded(self):
        from desktop_agent.fastcore.classifier import FastCoreClassifier
        fc = FastCoreClassifier()
        for text in ["hello", "open notepad", "weather in Delhi", "latest news"]:
            out = fc.classify(text)
            assert 0.0 <= out.confidence <= 1.0, f"confidence={out.confidence} for '{text}'"

    def test_tool_names_is_list(self):
        from desktop_agent.fastcore.classifier import FastCoreClassifier
        fc = FastCoreClassifier()
        out = fc.classify("open notepad")
        assert isinstance(out.tool_names, list)

    def test_response_mode_matches_task_type(self):
        """Weather task should produce weather response mode."""
        from desktop_agent.fastcore.classifier import FastCoreClassifier
        from desktop_agent.fastcore.models import TaskType, ResponseMode
        fc = FastCoreClassifier()
        out = fc.classify("weather in Delhi")
        assert out.task_type == TaskType.WEATHER_TASK
        assert out.response_mode == ResponseMode.WEATHER


class TestTaskRouterContract:
    """Validate TaskRouter RoutingDecision contract."""

    def test_decision_has_all_required_fields(self):
        from desktop_agent.brain.router.task_router import TaskRouter
        tr = TaskRouter()
        d = tr.route("open notepad")
        assert hasattr(d, "task_type")
        assert hasattr(d, "response_mode")
        assert hasattr(d, "tools_required")
        assert hasattr(d, "freshness_required")
        assert hasattr(d, "confidence")
        assert hasattr(d, "reasoning")
        assert hasattr(d, "estimated_latency_ms")
        assert hasattr(d, "tool_names")
        assert hasattr(d, "metadata")

    def test_confidence_is_bounded(self):
        from desktop_agent.brain.router.task_router import TaskRouter
        tr = TaskRouter()
        for text in ["hello", "open notepad", "what is AI"]:
            d = tr.route(text)
            assert 0.0 <= d.confidence <= 1.0
