from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    model_id: str
    version: str
    benchmark_scores: Dict[str, float]
    accuracy: float
    latency_ms: float
    resource_usage: Dict[str, float]
    failure_rate: float
    domains: List[str]
    validated_at: float
    status: str  # candidate / staging / active / retired

    def summary(self) -> Dict:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "accuracy": self.accuracy,
            "latency_ms": self.latency_ms,
            "failure_rate": self.failure_rate,
            "status": self.status,
            "domains": list(self.domains),
            "benchmark_scores": dict(self.benchmark_scores),
            "resource_usage": dict(self.resource_usage),
            "validated_at": self.validated_at,
        }


@dataclass
class CapabilityGap:
    capability: str
    description: str
    evidence: List[Dict]
    severity: str  # low / medium / high
    suggested_fix: str
    timestamp: float

    def summary(self) -> Dict:
        return {
            "capability": self.capability,
            "description": self.description,
            "severity": self.severity,
            "suggested_fix": self.suggested_fix,
            "evidence_count": len(self.evidence),
            "timestamp": self.timestamp,
        }


class ModelVersionManager:
    """Thread-safe singleton that tracks model versions, benchmarks, and promotion lifecycle."""

    _instance: ClassVar[Optional["ModelVersionManager"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> "ModelVersionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._versions: Dict[str, List[ModelVersion]] = {}
                    inst._lock_inst = threading.Lock()
                    cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_version(
        self, model_id: str, version: str, benchmark: Dict
    ) -> ModelVersion:
        """Register a new model version with benchmark results."""
        mv = ModelVersion(
            model_id=model_id,
            version=version,
            benchmark_scores=dict(benchmark.get("scores", {})),
            accuracy=benchmark.get("accuracy", 0.0),
            latency_ms=benchmark.get("latency_ms", 0.0),
            resource_usage=benchmark.get("resource_usage", {}),
            failure_rate=benchmark.get("failure_rate", 0.0),
            domains=list(benchmark.get("domains", [])),
            validated_at=time.time(),
            status="candidate",
        )
        with self._lock_inst:
            self._versions.setdefault(model_id, []).append(mv)
        logger.info("Registered model version %s/%s (candidate)", model_id, version)
        return mv

    def get_version(self, model_id: str, version: str) -> Optional[ModelVersion]:
        with self._lock_inst:
            for mv in self._versions.get(model_id, []):
                if mv.version == version:
                    return mv
        return None

    def get_active_version(self, model_id: str) -> Optional[ModelVersion]:
        with self._lock_inst:
            for mv in self._versions.get(model_id, []):
                if mv.status == "active":
                    return mv
        return None

    def list_versions(self, model_id: str) -> List[ModelVersion]:
        with self._lock_inst:
            return list(self._versions.get(model_id, []))

    def promote_version(self, model_id: str, version: str) -> bool:
        """Promote a version to active, retiring any previously active version."""
        with self._lock_inst:
            versions = self._versions.get(model_id, [])
            target = None
            for mv in versions:
                if mv.version == version:
                    target = mv
                    break
            if target is None:
                logger.warning("Version %s/%s not found for promotion", model_id, version)
                return False
            if target.status == "active":
                logger.info("Version %s/%s is already active", model_id, version)
                return True
            # Retire previous active
            for mv in versions:
                if mv.status == "active":
                    mv.status = "retired"
                    logger.info("Retired previous active %s/%s", model_id, mv.version)
            target.status = "active"
            logger.info("Promoted %s/%s to active", model_id, version)
            return True

    def demote_version(self, model_id: str, version: str, reason: str) -> bool:
        """Demote a version to retired status."""
        with self._lock_inst:
            for mv in self._versions.get(model_id, []):
                if mv.version == version:
                    if mv.status == "active":
                        mv.status = "retired"
                        logger.info(
                            "Demoted active %s/%s to retired (reason: %s)",
                            model_id, version, reason,
                        )
                        return True
                    mv.status = "retired"
                    logger.info(
                        "Demoted %s/%s to retired (reason: %s)",
                        model_id, version, reason,
                    )
                    return True
        logger.warning("Version %s/%s not found for demotion", model_id, version)
        return False

    def compare_versions(self, model_id: str, v1: str, v2: str) -> Dict:
        """Side-by-side comparison of two model versions."""
        a = self.get_version(model_id, v1)
        b = self.get_version(model_id, v2)
        if a is None or b is None:
            return {"error": "one or both versions not found", "v1": v1, "v2": v2}
        return {
            "v1": a.summary(),
            "v2": b.summary(),
            "accuracy_delta": round(b.accuracy - a.accuracy, 4),
            "latency_delta_ms": round(b.latency_ms - a.latency_ms, 2),
            "failure_rate_delta": round(b.failure_rate - a.failure_rate, 4),
            "benchmark_diff": {
                k: round(b.benchmark_scores.get(k, 0) - a.benchmark_scores.get(k, 0), 4)
                for k in set(list(a.benchmark_scores) + list(b.benchmark_scores))
            },
        }

    def record_benchmark(self, model_id: str, version: str, scores: Dict) -> None:
        """Update benchmark scores for an existing version."""
        mv = self.get_version(model_id, version)
        if mv is None:
            logger.warning("Version %s/%s not found for benchmark recording", model_id, version)
            return
        with self._lock_inst:
            mv.benchmark_scores.update(scores.get("scores", {}))
            if "accuracy" in scores:
                mv.accuracy = scores["accuracy"]
            if "latency_ms" in scores:
                mv.latency_ms = scores["latency_ms"]
            if "failure_rate" in scores:
                mv.failure_rate = scores["failure_rate"]
        logger.info("Recorded benchmark for %s/%s", model_id, version)


# ------------------------------------------------------------------
# CapabilityGapDetector
# ------------------------------------------------------------------

_CAPABILITY_MAP = {
    "timeout": "timeout_handling",
    "rate_limit": "rate_limit_recovery",
    "auth": "authentication_retry",
    "permission": "permission_escalation",
    "memory": "memory_management",
    "network": "network_resilience",
    "disk": "disk_space_management",
    "cpu": "cpu_throttling",
    "ocr": "ocr_accuracy",
    "voice": "speech_recognition",
    "vision": "vision_processing",
    "browser": "browser_automation",
    "clipboard": "clipboard_handling",
    "mouse": "input_control",
    "keyboard": "input_control",
    "file": "file_operations",
    "api": "api_error_handling",
}


class CapabilityGapDetector:
    """Detects capability gaps from task results and failure patterns."""

    _instance: ClassVar[Optional["CapabilityGapDetector"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> "CapabilityGapDetector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._gaps: List[CapabilityGap] = []
                    inst._lock_inst = threading.Lock()
                    cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_gaps(self, task_results: List[Dict]) -> List[CapabilityGap]:
        """Analyze task results for patterns indicating capability gaps."""
        failures = [r for r in task_results if not r.get("success", True)]
        if not failures:
            return []

        # Group by capability
        cap_failures: Dict[str, List[Dict]] = {}
        for f in failures:
            cap = self._match_capability(f)
            cap_failures.setdefault(cap, []).append(f)

        new_gaps: List[CapabilityGap] = []
        for cap, items in cap_failures.items():
            if len(items) < 2:
                continue
            severity = self._calculate_severity([], items[0])
            desc = f"Repeated failure ({len(items)} times) on capability: {cap}"
            gap = CapabilityGap(
                capability=cap,
                description=desc,
                evidence=[{"task": i.get("task", "unknown"), "error": i.get("error", "")} for i in items],
                severity=severity,
                suggested_fix=f"Investigate and improve {cap} handling",
                timestamp=time.time(),
            )
            new_gaps.append(gap)

        # Detect timeout patterns
        timeout_tasks = [r for r in task_results if "timeout" in str(r.get("error", "")).lower()]
        if len(timeout_tasks) >= 3:
            gap = CapabilityGap(
                capability="timeout_handling",
                description=f"Timeout pattern detected ({len(timeout_tasks)} occurrences)",
                evidence=[{"task": t.get("task", "unknown")} for t in timeout_tasks],
                severity="high",
                suggested_fix="Increase timeouts or optimize slow operations",
                timestamp=time.time(),
            )
            new_gaps.append(gap)

        # Detect low confidence patterns
        low_conf = [r for r in task_results if r.get("confidence", 1.0) < 0.5]
        if len(low_conf) >= 3:
            gap = CapabilityGap(
                capability="confidence_calibration",
                description=f"Low confidence pattern ({len(low_conf)} results below 0.5)",
                evidence=[{"task": c.get("task", "unknown"), "confidence": c.get("confidence")} for c in low_conf],
                severity="medium",
                suggested_fix="Retrain or add domain-specific knowledge for low-confidence areas",
                timestamp=time.time(),
            )
            new_gaps.append(gap)

        with self._lock_inst:
            for g in new_gaps:
                if len(self._gaps) >= 50:
                    self._gaps.pop(0)
                self._gaps.append(g)

        if new_gaps:
            logger.info("Detected %d new capability gaps", len(new_gaps))
        return list(new_gaps)

    def analyze_failure_patterns(self, failures: List[Dict]) -> List[CapabilityGap]:
        """Deep analysis of failure patterns to extract capability gaps."""
        if not failures:
            return []

        cap_failures: Dict[str, List[Dict]] = {}
        for f in failures:
            cap = self._match_capability(f)
            cap_failures.setdefault(cap, []).append(f)

        gaps: List[CapabilityGap] = []
        for cap, items in cap_failures.items():
            severity = self._calculate_severity([], items[0])
            evidence = []
            for item in items:
                evidence.append({
                    "task": item.get("task", "unknown"),
                    "error": item.get("error", ""),
                    "timestamp": item.get("timestamp", 0.0),
                })
            gap = CapabilityGap(
                capability=cap,
                description=f"Failure pattern analysis: {len(items)} failures in {cap}",
                evidence=evidence,
                severity=severity,
                suggested_fix=self._suggest_fix(cap, items),
                timestamp=time.time(),
            )
            gaps.append(gap)

        with self._lock_inst:
            for g in gaps:
                if len(self._gaps) >= 50:
                    self._gaps.pop(0)
                self._gaps.append(g)

        return gaps

    def get_known_gaps(self) -> List[CapabilityGap]:
        with self._lock_inst:
            return list(self._gaps)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _match_capability(self, failure: Dict) -> str:
        error_msg = str(failure.get("error", "")).lower()
        task_type = str(failure.get("task", "")).lower()
        combined = f"{error_msg} {task_type}"

        for keyword, capability in _CAPABILITY_MAP.items():
            if keyword in combined:
                return capability

        return "unknown_capability"

    def _calculate_severity(self, gaps: List[CapabilityGap], failure: Dict) -> str:
        error_msg = str(failure.get("error", "")).lower()
        if any(k in error_msg for k in ("critical", "fatal", "data loss", "security")):
            return "high"
        if any(k in error_msg for k in ("timeout", "oom", "crash", "permission")):
            return "high"
        if any(k in error_msg for k in ("slow", "retry", "degraded")):
            return "medium"
        return "low"

    def _suggest_fix(self, capability: str, failures: List[Dict]) -> str:
        suggestions = {
            "timeout_handling": "Increase timeout thresholds or implement circuit breakers",
            "rate_limit_recovery": "Add exponential backoff and retry logic",
            "authentication_retry": "Implement token refresh and re-authentication flow",
            "permission_escalation": "Check and request required permissions before execution",
            "memory_management": "Profile memory usage and implement garbage collection hints",
            "network_resilience": "Add connection pooling and automatic reconnection",
            "ocr_accuracy": "Improve image preprocessing or switch OCR backend",
            "speech_recognition": "Adjust audio thresholds or use alternative STT provider",
            "vision_processing": "Reduce frame resolution or optimize processing pipeline",
            "browser_automation": "Handle dynamic content waits and element readiness",
        }
        return suggestions.get(capability, f"Investigate and resolve {capability} failures")
