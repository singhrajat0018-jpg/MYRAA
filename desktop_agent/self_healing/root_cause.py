from __future__ import annotations

"""Root-Cause Analyzer for MYRAA subsystem failures.

Gathers evidence from diagnostic results and recent events, applies
heuristic pattern matching to identify the most likely root cause, and
recommends a fix.  This is NOT ML-based -- it uses rule signatures,
weight-averaged confidence, and configurable impact classification.
"""

import logging
import math
import re
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from desktop_agent.self_healing.diagnostics import (
    DiagnosticResult,
    HealthStatus,
)

logger = logging.getLogger(__name__)


class EvidenceType(Enum):
    ERROR_LOG = "error_log"
    TELEMETRY = "telemetry"
    RECENT_CHANGE = "recent_change"
    DEPENDENCY_STATE = "dependency_state"
    RUNTIME_STATE = "runtime_state"
    CONFIG_STATE = "config_state"
    RESOURCE_STATE = "resource_state"
    PATTERN = "pattern"


class Evidence:
    """A single piece of evidence supporting a root-cause hypothesis."""

    __slots__ = ("type", "source", "content", "timestamp", "weight")

    def __init__(
        self,
        type: EvidenceType,
        source: str,
        content: str,
        timestamp: float,
        weight: float = 0.5,
    ) -> None:
        self.type = type
        self.source = source
        self.content = content
        self.timestamp = timestamp
        self.weight = max(0.0, min(1.0, weight))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "weight": self.weight,
        }

    def __repr__(self) -> str:
        return (
            f"Evidence(type={self.type.value}, source={self.source!r}, "
            f"weight={self.weight:.2f})"
        )


class RootCause:
    """A hypothesised root cause with evidence and recommended fix."""

    __slots__ = (
        "cause", "description", "evidence", "confidence",
        "impact", "recommended_fix", "category",
    )

    def __init__(
        self,
        cause: str,
        description: str,
        evidence: List[Evidence],
        confidence: float,
        impact: str,
        recommended_fix: str,
        category: str,
    ) -> None:
        self.cause = cause
        self.description = description
        self.evidence = evidence
        self.confidence = max(0.0, min(1.0, confidence))
        self.impact = impact
        self.recommended_fix = recommended_fix
        self.category = category

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "description": self.description,
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence,
            "impact": self.impact,
            "recommended_fix": self.recommended_fix,
            "category": self.category,
        }

    def __repr__(self) -> str:
        return (
            f"RootCause(cause={self.cause!r}, confidence={self.confidence:.2f}, "
            f"impact={self.impact!r})"
        )


# ---------------------------------------------------------------------------
# Known failure signatures (heuristic pattern library)
# ---------------------------------------------------------------------------

_ERROR_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "connection_refused": {
        "pattern": re.compile(r"connection\s+refused|errno\s+111|econnrefused", re.I),
        "cause": "Dependency service unreachable",
        "description": "A downstream service is not listening on the expected port.",
        "category": "dependency",
        "impact": "high",
        "fix": "Verify the dependency is running and listening on the correct port.",
    },
    "timeout": {
        "pattern": re.compile(r"timed?\s*out|deadline\s+exceeded|etimedout", re.I),
        "cause": "Request timeout",
        "description": "A request exceeded the allowed time limit.",
        "category": "network",
        "impact": "medium",
        "fix": "Check network latency or increase timeout thresholds.",
    },
    "permission_denied": {
        "pattern": re.compile(r"permission\s+denied|eacces|access\s+denied", re.I),
        "cause": "Insufficient permissions",
        "description": "The process lacks OS-level permissions for a required resource.",
        "category": "security",
        "impact": "high",
        "fix": "Adjust file/resource permissions or run with appropriate privileges.",
    },
    "out_of_memory": {
        "pattern": re.compile(r"out\s+of\s+memory|oom|memoryerror|malloc\s+fail", re.I),
        "cause": "Memory exhaustion",
        "description": "The process has exhausted available memory.",
        "category": "resource",
        "impact": "critical",
        "fix": "Increase available memory or reduce memory footprint.",
    },
    "disk_full": {
        "pattern": re.compile(r"no\s+space\s+left|disk\s+full|enospc", re.I),
        "cause": "Disk space exhaustion",
        "description": "The disk has no remaining free space.",
        "category": "resource",
        "impact": "critical",
        "fix": "Free disk space or expand storage.",
    },
    "config_corrupt": {
        "pattern": re.compile(r"json\.decode|yaml\.parse|config.*corrupt|parse.*error", re.I),
        "cause": "Configuration file corruption",
        "description": "A configuration file is malformed or unreadable.",
        "category": "config",
        "impact": "high",
        "fix": "Restore configuration from backup or regenerate defaults.",
    },
    "import_error": {
        "pattern": re.compile(r"importerror|modulenotfound|no\s+module\s+named", re.I),
        "cause": "Missing Python dependency",
        "description": "A required Python package is not installed.",
        "category": "dependency",
        "impact": "high",
        "fix": "Install the missing package (pip install <package>).",
    },
    "key_error": {
        "pattern": re.compile(r"keyerror|key\s+.*not\s+found", re.I),
        "cause": "Missing expected data key",
        "description": "A dictionary lookup failed -- expected key is absent.",
        "category": "runtime",
        "impact": "medium",
        "fix": "Verify data schema or add defensive key access.",
    },
    "connection_reset": {
        "pattern": re.compile(r"connection\s+reset|econnreset", re.I),
        "cause": "Connection reset by peer",
        "description": "The remote end forcibly closed the connection.",
        "category": "network",
        "impact": "medium",
        "fix": "Check remote service health and network stability.",
    },
    "rate_limited": {
        "pattern": re.compile(r"rate.?limit|429|too\s+many\s+requests", re.I),
        "cause": "API rate limit exceeded",
        "description": "The client has exceeded the provider's rate limit.",
        "category": "dependency",
        "impact": "medium",
        "fix": "Implement backoff/retry or request a higher quota.",
    },
}

_RESOURCE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "high_cpu": {
        "pattern": re.compile(r"cpu\s+(usage|utiliz).*\d{2,3}\s*%", re.I),
        "cause": "High CPU usage",
        "description": "CPU utilisation is abnormally high.",
        "category": "resource",
        "impact": "medium",
        "fix": "Identify the CPU-heavy process and optimise or throttle it.",
    },
    "high_memory": {
        "pattern": re.compile(r"memory\s+(usage|utiliz|percent).*\d{2,3}\s*%", re.I),
        "cause": "High memory usage",
        "description": "Memory utilisation is abnormally high.",
        "category": "resource",
        "impact": "medium",
        "fix": "Identify memory-heavy processes and reduce consumption.",
    },
    "low_disk": {
        "pattern": re.compile(r"disk\s+(space|free).*\d+\s*(mb|gb)", re.I),
        "cause": "Low disk space",
        "description": "Available disk space is below a safe threshold.",
        "category": "resource",
        "impact": "high",
        "fix": "Clean up temp files or expand storage.",
    },
}

_CATEGORIES = {
    EvidenceType.ERROR_LOG: "error",
    EvidenceType.DEPENDENCY_STATE: "dependency",
    EvidenceType.RESOURCE_STATE: "resource",
    EvidenceType.CONFIG_STATE: "config",
    EvidenceType.RECENT_CHANGE: "change",
    EvidenceType.RUNTIME_STATE: "runtime",
    EvidenceType.TELEMETRY: "telemetry",
    EvidenceType.PATTERN: "pattern",
}

_CAUSE_MAP = {
    "error": ("Runtime error", "high"),
    "dependency": ("Dependency failure", "high"),
    "resource": ("Resource exhaustion", "high"),
    "config": ("Configuration issue", "medium"),
    "network": ("Network connectivity issue", "medium"),
    "security": ("Permission / security issue", "high"),
    "runtime": ("Runtime state anomaly", "medium"),
    "change": ("Recent change regression", "medium"),
    "telemetry": ("Telemetry anomaly", "low"),
    "unknown": ("Undetermined cause", "low"),
}


class RootCauseAnalyzer:
    """Heuristic root-cause analyzer for subsystem failures.

    Example::

        analyzer = RootCauseAnalyzer()
        root_cause = analyzer.analyze(
            component="server",
            status=HealthStatus.FAILING,
            diagnostic_results=results,
            recent_events=events,
        )
    """

    _instance: Optional[RootCauseAnalyzer] = None
    _lock_class: Any = None

    def __new__(cls) -> RootCauseAnalyzer:
        import threading as _threading

        if not isinstance(cls._lock_class, _threading.Lock.__class__):
            cls._lock_class = _threading.Lock()

        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        import threading

        self._lock = threading.Lock()
        logger.info("RootCauseAnalyzer initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        component: str,
        status: HealthStatus,
        diagnostic_results: List[DiagnosticResult],
        recent_events: List[Dict[str, Any]],
    ) -> RootCause:
        """Perform full root-cause analysis for *component*."""
        with self._lock:
            logger.info(
                "Analyzing root cause for %s (status=%s)", component, status.value
            )

            evidence = self.gather_evidence(component, diagnostic_results, recent_events)

            sig_rc = self._match_signature(evidence)
            if sig_rc is not None:
                return sig_rc

            comp_results = [r for r in diagnostic_results if r.component == component]
            pattern_rc = self.analyze_pattern(component, comp_results)
            if pattern_rc is not None:
                return pattern_rc

            return self.classify_cause(evidence)

    def gather_evidence(
        self,
        component: str,
        diagnostic_results: List[DiagnosticResult],
        recent_events: List[Dict[str, Any]],
    ) -> List[Evidence]:
        """Collect all relevant evidence from diagnostics and recent events."""
        evidence: List[Evidence] = []
        now = time.time()

        _STATUS_WEIGHTS = {
            HealthStatus.HEALTHY: 0.1,
            HealthStatus.DEGRADED: 0.4,
            HealthStatus.FAILING: 0.7,
            HealthStatus.UNAVAILABLE: 0.6,
            HealthStatus.CORRUPTED: 0.9,
            HealthStatus.UNKNOWN: 0.2,
        }

        for dr in diagnostic_results:
            if dr.component != component:
                continue

            weight = _STATUS_WEIGHTS.get(dr.status, 0.3)
            ev_type = (
                EvidenceType.ERROR_LOG
                if dr.status in (HealthStatus.FAILING, HealthStatus.CORRUPTED)
                else EvidenceType.RUNTIME_STATE
            )

            evidence.append(Evidence(
                type=ev_type,
                source=f"diagnostic:{dr.component}",
                content=f"[{dr.status.value}] {dr.reason}",
                timestamp=dr.timestamp,
                weight=weight,
            ))

        for event in recent_events:
            ev_text = str(event.get("message", event.get("error", "")))
            ev_type_str = event.get("type", "")

            if ev_type_str == "error":
                ev_type = EvidenceType.ERROR_LOG
                ev_weight = 0.7
            elif ev_type_str == "config_change":
                ev_type = EvidenceType.RECENT_CHANGE
                ev_weight = 0.6
            elif ev_type_str == "dependency":
                ev_type = EvidenceType.DEPENDENCY_STATE
                ev_weight = 0.6
            elif ev_type_str == "resource":
                ev_type = EvidenceType.RESOURCE_STATE
                ev_weight = 0.65
            elif ev_type_str == "telemetry":
                ev_type = EvidenceType.TELEMETRY
                ev_weight = 0.5
            else:
                ev_type = EvidenceType.RUNTIME_STATE
                ev_weight = 0.5

            evidence.append(Evidence(
                type=ev_type,
                source=event.get("source", "event"),
                content=ev_text,
                timestamp=event.get("timestamp", now),
                weight=ev_weight,
            ))

        return evidence

    def classify_cause(self, evidence: List[Evidence]) -> RootCause:
        """Classify the most likely cause from evidence using heuristics."""
        if not evidence:
            return RootCause(
                cause="Unknown",
                description="Insufficient evidence to determine root cause.",
                evidence=[],
                confidence=0.1,
                impact="low",
                recommended_fix="Gather more diagnostic data.",
                category="unknown",
            )

        pattern_match = self._scan_evidence_content(evidence)
        if pattern_match is not None:
            conf = self._calculate_confidence(evidence)
            pattern_match["confidence"] = min(conf, pattern_match.get("confidence", 0.5))
            return RootCause(
                cause=pattern_match["cause"],
                description=pattern_match["description"],
                evidence=evidence,
                confidence=pattern_match["confidence"],
                impact=pattern_match["impact"],
                recommended_fix=pattern_match["fix"],
                category=pattern_match["category"],
            )

        category_scores: Dict[str, float] = {}
        for ev in evidence:
            cat = _CATEGORIES.get(ev.type, "unknown")
            category_scores[cat] = category_scores.get(cat, 0.0) + ev.weight

        best_cat = max(category_scores, key=category_scores.get)  # type: ignore[arg-type]
        conf = self._calculate_confidence(evidence)
        cause, default_impact = _CAUSE_MAP.get(best_cat, ("Undetermined cause", "low"))

        return RootCause(
            cause=cause,
            description=f"Evidence predominantly indicates a {best_cat}-related issue.",
            evidence=evidence,
            confidence=conf,
            impact=default_impact,
            recommended_fix=f"Investigate {best_cat} subsystem.",
            category=best_cat,
        )

    def analyze_pattern(
        self, component: str, history: List[DiagnosticResult]
    ) -> Optional[RootCause]:
        """Detect repeated failure patterns in a component's diagnostic history."""
        if len(history) < 3:
            return None

        recent = history[-20:] if len(history) > 20 else history

        consecutive_fail = 0
        for dr in reversed(recent):
            if dr.status in (HealthStatus.HEALTHY, HealthStatus.UNKNOWN):
                break
            consecutive_fail += 1

        if consecutive_fail >= 5:
            return RootCause(
                cause=f"Chronic failure in {component}",
                description=(
                    f"{consecutive_fail} consecutive non-healthy checks for "
                    f"{component}. Persistent, unrecovered failure."
                ),
                evidence=[
                    Evidence(
                        type=EvidenceType.PATTERN,
                        source=f"history:{component}",
                        content=f"{consecutive_fail} consecutive failures",
                        timestamp=recent[-1].timestamp,
                        weight=0.9,
                    )
                ],
                confidence=min(0.95, 0.5 + consecutive_fail * 0.05),
                impact="critical",
                recommended_fix=f"Restart or redeploy {component}.",
                category="persistent_failure",
            )

        transitions = 0
        for i in range(1, len(recent)):
            if recent[i].status != recent[i - 1].status:
                transitions += 1

        if transitions >= 6 and len(recent) >= 6:
            return RootCause(
                cause=f"Oscillating health in {component}",
                description=(
                    f"{transitions} status transitions in recent history, "
                    "indicating instability."
                ),
                evidence=[
                    Evidence(
                        type=EvidenceType.PATTERN,
                        source=f"history:{component}",
                        content=f"{transitions} transitions in {len(recent)} checks",
                        timestamp=recent[-1].timestamp,
                        weight=0.7,
                    )
                ],
                confidence=0.65,
                impact="high",
                recommended_fix=f"Check for intermittent failures in {component}.",
                category="instability",
            )

        if (
            recent[0].status in (HealthStatus.HEALTHY, HealthStatus.UNKNOWN)
            and recent[-1].status in (
                HealthStatus.FAILING, HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE
            )
        ):
            return RootCause(
                cause=f"Recent degradation of {component}",
                description=(
                    f"Status changed from {recent[0].status.value} to "
                    f"{recent[-1].status.value}, suggesting a regression."
                ),
                evidence=[
                    Evidence(
                        type=EvidenceType.PATTERN,
                        source=f"history:{component}",
                        content=(
                            f"Status changed {recent[0].status.value} -> "
                            f"{recent[-1].status.value}"
                        ),
                        timestamp=recent[-1].timestamp,
                        weight=0.75,
                    )
                ],
                confidence=0.7,
                impact="high",
                recommended_fix="Check recent deployments or configuration changes.",
                category="regression",
            )

        return None

    # ------------------------------------------------------------------
    # Confidence calculation
    # ------------------------------------------------------------------

    def _calculate_confidence(self, evidence: List[Evidence]) -> float:
        """Weighted average of evidence weights. More evidence = higher confidence."""
        if not evidence:
            return 0.0

        total_weight = sum(e.weight for e in evidence)
        count = len(evidence)

        avg_weight = total_weight / count
        count_factor = min(1.0, 0.3 + 0.7 * (math.log1p(count) / math.log1p(20)))

        confidence = avg_weight * count_factor
        return max(0.0, min(1.0, confidence))

    # ------------------------------------------------------------------
    # Singleton reset
    # ------------------------------------------------------------------

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        import threading as _threading

        if not isinstance(cls._lock_class, _threading.Lock.__class__):
            cls._lock_class = _threading.Lock()

        with cls._lock_class:
            cls._instance = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_evidence_content(
        self, evidence: List[Evidence]
    ) -> Optional[Dict[str, Any]]:
        """Scan evidence content against all known failure signatures."""
        for ev in evidence:
            text = ev.content

            for sig_name, sig in _ERROR_SIGNATURES.items():
                if sig["pattern"].search(text):
                    logger.debug("Signature match '%s' in evidence", sig_name)
                    return {
                        "cause": sig["cause"],
                        "description": sig["description"],
                        "category": sig["category"],
                        "impact": sig["impact"],
                        "fix": sig["fix"],
                        "confidence": 0.8,
                    }

            for res_name, res in _RESOURCE_PATTERNS.items():
                if res["pattern"].search(text):
                    logger.debug("Resource pattern match '%s'", res_name)
                    return {
                        "cause": res["cause"],
                        "description": res["description"],
                        "category": res["category"],
                        "impact": res["impact"],
                        "fix": res["fix"],
                        "confidence": 0.7,
                    }

        return None

    def _match_signature(
        self, evidence: List[Evidence]
    ) -> Optional[RootCause]:
        """Try to match gathered evidence against known failure signatures."""
        result = self._scan_evidence_content(evidence)
        if result is None:
            return None

        return RootCause(
            cause=result["cause"],
            description=result["description"],
            evidence=evidence,
            confidence=result["confidence"],
            impact=result["impact"],
            recommended_fix=result["fix"],
            category=result["category"],
        )