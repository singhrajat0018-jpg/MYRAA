"""
Ollama Provider — Local-First Multi-Model

Provides local LLM inference via Ollama HTTP API.
Supports model selection for Qwen3.5 4B / Gemma3 4B / MiniMax-M3.
Includes health tracking, cooldown, and fallback.
"""

from __future__ import annotations
import os
import time
import logging
import requests
from typing import Any, Dict, List, Optional

from ..provider import AIProvider

log = logging.getLogger(__name__)

# Model roles for FastCore/TaskRouter integration
# Based on RTX 3050 4GB benchmark: llama3.2:3b is fastest (120ms TTFT)
MODEL_ROLES = {
    "llama3.2:3b": ["conversation", "voice_fast", "fallback", "fast"],
    "qwen3:4b": ["reasoning", "coding", "tool_planning", "general"],
    "gemma3:4b": ["vision", "multimodal", "screen_understanding"],
    "minimax-m3:cloud": ["complex_reasoning", "deep_coding", "architecture", "long_context", "design"],  # REQUIRES PAID OLLAMA SUBSCRIPTION — unavailable without upgrade
    "qwen3.5:4b": ["conversation", "reasoning"],  # DISABLED — thinking model, empty on low VRAM
}

DEFAULT_MODEL = "llama3.2:3b"
FALLBACK_MODEL = "qwen3:4b"


import json as _json

# Dynamic response budgets by intent (tokens)
RESPONSE_BUDGETS = {
    "greeting": 60,
    "conversation": 100,
    "casual": 100,
    "simple_question": 120,
    "weather": 80,
    "news": 200,
    "desktop_command": 50,
    "explanation": 200,
    "coding": 400,
    "complex_reasoning": 500,
    "research": 250,
    "vision": 200,
    "default_voice": 120,
    "default_text": 400,
}


class OllamaProvider(AIProvider):
    """Local-first Ollama provider with multi-model support."""

    def __init__(
        self,
        model: str = "",
        host: str = "http://127.0.0.1:11434",
    ):
        # Import centralized config — fallback to env/OLLAMA_MODEL for backward compat
        try:
            from desktop_agent.config.settings import GENERAL_MODEL, FALLBACK_MODEL
            default = GENERAL_MODEL
            self._fallback_model = FALLBACK_MODEL
        except ImportError:
            default = DEFAULT_MODEL
            self._fallback_model = FALLBACK_MODEL

        self.model = model or os.getenv("OLLAMA_MODEL", default)
        self.host = host
        self.session = requests.Session()
        self._last_available_check = 0.0
        self._last_available_result = False
        self._available_models: list[str] = []
        self._cooldown_until: float = 0.0
        self._consecutive_failures: int = 0
        self._last_success: float = 0.0
        self._last_failure: float = 0.0
        self._last_latency: float = 0.0
        self._last_error: Optional[str] = None
        self._total_requests: int = 0
        self._total_failures: int = 0
        # Model health tracking per model
        self._model_health: Dict[str, Dict[str, Any]] = {}
        # Disabled models — known broken
        self._disabled_models: set = set()
        # Circuit breaker for fast-fail on repeated Ollama errors
        from desktop_agent.brain.ai.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        self._circuit = CircuitBreaker("ollama", CircuitBreakerConfig(
            failure_threshold=3,
            cooldown_seconds=30.0,
        ))

    def __del__(self):
        try:
            self.session.close()
        except Exception:
            pass

    @property
    def name(self):
        return "ollama"

    def available(self) -> bool:
        now = time.monotonic()
        if now < self._cooldown_until:
            return False
        if now - self._last_available_check < 10.0:
            return self._last_available_result
        self._last_available_check = now
        try:
            r = self.session.get(f"{self.host}/api/tags", timeout=3)
            self._last_available_result = r.status_code == 200
            if self._last_available_result:
                data = r.json()
                self._available_models = [m["name"] for m in data.get("models", [])]
                if not self.model and self._available_models:
                    self.model = self._available_models[0]
            else:
                self._available_models = []
        except Exception:
            self._last_available_result = False
            self._available_models = []
        return self._last_available_result

    def get_model_for_role(self, role: str) -> Optional[str]:
        """Return the best available model for a given role.

        Skips disabled models. Falls back to default if no role match.
        """
        if not self._available_models:
            self.available()
        for model_name, roles in MODEL_ROLES.items():
            if role in roles:
                if model_name in self._disabled_models:
                    continue
                for avail in self._available_models:
                    if model_name in avail:
                        return avail
        # Fallback: return default if available and not disabled
        if self.model and self.model not in self._disabled_models:
            for avail in self._available_models:
                if self.model in avail:
                    return avail
        return self.model if self.model else None

    def get_model_with_fallback(self, preferred_model: str) -> str:
        """Return preferred model if available and healthy, else fallback chain."""
        if not self._available_models:
            self.available()

        # Try preferred model
        if preferred_model not in self._disabled_models:
            for avail in self._available_models:
                if preferred_model in avail:
                    return avail

        # Try fallback model
        if self._fallback_model not in self._disabled_models:
            for avail in self._available_models:
                if self._fallback_model in avail:
                    log.info("[Ollama] Falling back from %s to %s", preferred_model, self._fallback_model)
                    return avail

        # Last resort: any available model that isn't disabled
        for avail in self._available_models:
            if avail not in self._disabled_models:
                log.warning("[Ollama] Using last-resort model: %s", avail)
                return avail

        return self.model

    def disable_model(self, model: str, reason: str = ""):
        """Mark a model as disabled (known broken)."""
        self._disabled_models.add(model)
        log.warning("[Ollama] Model DISABLED: %s (%s)", model, reason)

    def enable_model(self, model: str):
        """Re-enable a previously disabled model."""
        self._disabled_models.discard(model)
        log.info("[Ollama] Model re-enabled: %s", model)

    def model_status(self) -> Dict[str, Dict[str, Any]]:
        """Return status for all known models."""
        if not self._available_models:
            self.available()
        status = {}
        for model_name in MODEL_ROLES:
            installed = any(model_name in m for m in self._available_models)
            health = self.model_health(model_name)
            disabled = model_name in self._disabled_models
            healthy = health["consecutive_failures"] < 3 and not disabled
            status[model_name] = {
                "installed": installed,
                "healthy": healthy,
                "disabled": disabled,
                "consecutive_failures": health["consecutive_failures"],
                "total_requests": health["total_requests"],
                "avg_latency": round(health["avg_latency"], 2),
                "roles": MODEL_ROLES.get(model_name, []),
            }
        return status

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ):
        # Circuit breaker: fail fast if Ollama is known-down
        if not self._circuit.allow_request():
            log.warning("[Ollama] Circuit OPEN — rejecting request (probe pending)")
            raise ConnectionError(f"Circuit breaker OPEN for {self.name}")

        model = kwargs.pop("model", self.model)
        payload = {
            "model": model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": kwargs.get("stream", False),
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_ctx": kwargs.get("num_ctx", 8192),
            },
        }

        # Qwen3 thinking model: disable thinking for fast responses
        if "qwen3" in model:
            payload["think"] = False

        timeout = kwargs.get("timeout", 120)

        log.debug("[Ollama] Sending request to %s model=%s", self.host, model)
        start = time.perf_counter()

        try:
            response = self.session.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=timeout,
            )
        except requests.Timeout:
            self._on_failure(model, requests.Timeout("timeout"))
            log.warning("[Ollama] Request timed out after %ds", timeout)
            raise
        except requests.ConnectionError:
            self._on_failure(model, requests.ConnectionError("connection refused"))
            log.warning("[Ollama] Connection refused at %s", self.host)
            raise
        except requests.RequestException as e:
            self._on_failure(model, e)
            log.warning("[Ollama] Request failed: %s", e)
            raise

        elapsed = time.perf_counter() - start
        self._last_latency = elapsed
        self._total_requests += 1
        log.debug("[Ollama] HTTP returned in %.2fs", elapsed)

        if response.status_code == 500:
            self._on_failure(model, requests.HTTPError("500"))
            log.warning("[Ollama] Internal server error (model may not be loaded)")
            raise requests.HTTPError(
                f"Ollama internal error — model may not be loaded. Try: ollama pull {model}",
                response=response,
            )

        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            log.warning("[Ollama] Non-JSON response (status %d)", response.status_code)
            raise ValueError(f"Ollama returned non-JSON response (HTTP {response.status_code})")

        # Success — reset failure tracking
        self._consecutive_failures = 0
        self._cooldown_until = 0.0
        self._last_success = time.time()
        self._circuit.record_success()
        self._last_error = None
        self._record_model_success(model, elapsed)
        return data.get("response", "")

    def _on_failure(self, model: str, error: Exception):
        """Track failures and apply cooldown after repeated errors."""
        self._consecutive_failures += 1
        self._total_failures += 1
        self._last_failure = time.time()
        self._last_error = str(error)[:200]
        self._record_model_failure(model, str(error)[:100])
        self._circuit.record_failure()
        if self._consecutive_failures >= 3:
            cooldown = min(60, 5 * self._consecutive_failures)
            self._cooldown_until = time.monotonic() + cooldown
            log.warning(
                "[Ollama] %d consecutive failures, cooldown %ds",
                self._consecutive_failures, cooldown,
            )

    def _record_model_success(self, model: str, latency: float):
        """Track per-model success metrics."""
        if model not in self._model_health:
            self._model_health[model] = {
                "last_success": 0.0, "last_failure": 0.0,
                "consecutive_failures": 0, "total_requests": 0,
                "total_failures": 0, "avg_latency": 0.0,
            }
        h = self._model_health[model]
        h["last_success"] = time.time()
        h["consecutive_failures"] = 0
        h["total_requests"] += 1
        h["avg_latency"] = (h["avg_latency"] * (h["total_requests"] - 1) + latency) / h["total_requests"]

    def _record_model_failure(self, model: str, error: str):
        """Track per-model failure metrics."""
        if model not in self._model_health:
            self._model_health[model] = {
                "last_success": 0.0, "last_failure": 0.0,
                "consecutive_failures": 0, "total_requests": 0,
                "total_failures": 0, "avg_latency": 0.0,
            }
        h = self._model_health[model]
        h["last_failure"] = time.time()
        h["consecutive_failures"] += 1
        h["total_failures"] += 1
        h["last_error"] = error

    def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ):
        """Streaming generation via Ollama /api/generate with stream=True.

        Yields text chunks as they become available from the model.
        Uses fallback chain if preferred model fails or returns empty.
        """
        # Circuit breaker: fail fast if Ollama is known-down
        if not self._circuit.allow_request():
            log.warning("[Ollama] Circuit OPEN — rejecting stream request")
            return

        preferred = kwargs.pop("model", self.model)
        model = self.get_model_with_fallback(preferred)

        # Build prompt
        prompt_text = f"{system_prompt}\n\n{user_prompt}"

        # Voice-optimized defaults: smaller context, shorter output
        is_voice = kwargs.pop("is_voice", False)
        intent = kwargs.pop("intent", None)
        default_num_ctx = 4096 if is_voice else 8192

        # Dynamic response budget based on intent
        if "num_predict" not in kwargs:
            if intent and intent in RESPONSE_BUDGETS:
                default_num_predict = RESPONSE_BUDGETS[intent]
            elif is_voice:
                default_num_predict = RESPONSE_BUDGETS["default_voice"]
            else:
                default_num_predict = RESPONSE_BUDGETS["default_text"]
        else:
            default_num_predict = kwargs.pop("num_predict")

        payload = {
            "model": model,
            "prompt": prompt_text,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_ctx": kwargs.get("num_ctx", default_num_ctx),
                "num_predict": default_num_predict,
            },
        }

        # Qwen3 thinking model: disable thinking for fast voice responses
        if "qwen3" in model:
            payload["think"] = False

        timeout = kwargs.get("timeout", 180)

        log.debug("[Ollama] Streaming request to %s model=%s budget=%d", self.host, model, default_num_predict)
        start = time.perf_counter()

        try:
            response = self.session.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=timeout,
                stream=True,
            )
        except requests.Timeout:
            self._on_failure(model, requests.Timeout("timeout"))
            log.warning("[Ollama] Stream timed out after %ds", timeout)
            return
        except requests.ConnectionError:
            self._on_failure(model, requests.ConnectionError("connection refused"))
            log.warning("[Ollama] Connection refused at %s", self.host)
            return
        except requests.RequestException as e:
            self._on_failure(model, e)
            log.warning("[Ollama] Stream request failed: %s", e)
            return

        self._total_requests += 1
        full_response = ""

        try:
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = line.decode("utf-8") if isinstance(line, bytes) else line
                    data = _json.loads(chunk)
                    token = data.get("response", "")
                    if token:
                        full_response += token
                        yield token
                    if data.get("done", False):
                        break
                except (ValueError, KeyError):
                    continue
        finally:
            elapsed = time.perf_counter() - start
            self._last_latency = elapsed
            if full_response:
                self._consecutive_failures = 0
                self._cooldown_until = 0.0
                self._last_success = time.time()
                self._last_error = None
                self._circuit.record_success()
                self._record_model_success(model, elapsed)
            else:
                # Empty response — mark model unhealthy, try fallback
                self._record_model_failure(model, "empty response")
                log.warning("[Ollama] Empty response from %s after %.1fs", model, elapsed)
                if model != self._fallback_model and self._fallback_model not in self._disabled_models:
                    log.info("[Ollama] Retrying with fallback: %s", self._fallback_model)
                    # Pass is_voice and intent to fallback
                    yield from self._stream_fallback(
                        system_prompt, user_prompt, model,
                        is_voice=is_voice, intent=intent, **kwargs,
                    )
            response.close()

    def _stream_fallback(self, system_prompt: str, user_prompt: str,
                         failed_model: str, is_voice=False, intent=None, **kwargs):
        """Attempt fallback generation with a different model."""
        fallback = self._fallback_model
        if fallback in self._disabled_models or fallback == failed_model:
            return

        prompt_text = f"{system_prompt}\n\n{user_prompt}"

        # Dynamic budget for fallback
        if intent and intent in RESPONSE_BUDGETS:
            num_predict = RESPONSE_BUDGETS[intent]
        elif is_voice:
            num_predict = RESPONSE_BUDGETS["default_voice"]
        else:
            num_predict = RESPONSE_BUDGETS["default_text"]

        payload = {
            "model": fallback,
            "prompt": prompt_text,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_ctx": kwargs.get("num_ctx", 4096 if is_voice else 8192),
                "num_predict": kwargs.get("num_predict", num_predict),
            },
        }

        # Qwen3 fallback: disable thinking
        if "qwen3" in fallback:
            payload["think"] = False

        try:
            response = self.session.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=kwargs.get("timeout", 180),
                stream=True,
            )
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = _json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
                except (ValueError, KeyError):
                    continue
            response.close()
        except Exception as e:
            log.warning("[Ollama] Fallback %s also failed: %s", fallback, e)

    def model_health(self, model: str) -> Dict[str, Any]:
        """Get health metrics for a specific model."""
        return self._model_health.get(model, {
            "last_success": 0.0, "last_failure": 0.0,
            "consecutive_failures": 0, "total_requests": 0,
            "total_failures": 0, "avg_latency": 0.0,
        })

    def is_model_healthy(self, model: str) -> bool:
        """Check if a specific model is healthy (no repeated failures)."""
        h = self.model_health(model)
        return h["consecutive_failures"] < 3

    def health(self) -> Dict[str, Any]:
        """Return provider health status."""
        cb = self._circuit.stats()
        return {
            "provider": "ollama",
            "model": self.model,
            "healthy": self.available(),
            "degraded": self._consecutive_failures > 0,
            "cooldown_until": self._cooldown_until,
            "consecutive_failures": self._consecutive_failures,
            "total_requests": self._total_requests,
            "total_failures": self._total_failures,
            "last_success": self._last_success,
            "last_failure": self._last_failure,
            "last_latency": self._last_latency,
            "last_error": self._last_error,
            "available_models": self._available_models,
            "model_health": self._model_health,
            "model_status": self.model_status(),
            "disabled_models": list(self._disabled_models),
            "circuit_breaker": {
                "state": cb.state,
                "consecutive_failures": cb.consecutive_failures,
                "total_rejected": cb.total_rejected,
                "total_successes": cb.total_successes,
                "total_failures": cb.total_failures,
            },
        }
