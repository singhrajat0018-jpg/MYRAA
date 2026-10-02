"""Performance Self-Optimization for MYRAA self-healing."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

MAX_HISTORY = 50


class OptimizationCategory(Enum):
    """Categories of performance issues the optimizer can detect."""

    SLOW_MODEL = "slow_model"
    SLOW_TOOL = "slow_tool"
    EXCESSIVE_CONTEXT = "excessive_context"
    REPEATED_WORK = "repeated_work"
    CACHE_MISS = "cache_miss"
    SERIALIZATION = "serialization"
    BLOCKING_IO = "blocking_io"
    UNNECESSARY_LLM = "unnecessary_llm"
    BAD_CONCURRENCY = "bad_concurrency"
    MEMORY_PRESSURE = "memory_pressure"


@dataclass
class OptimizationProposal:
    """A concrete optimization suggestion with evidence and risk assessment."""

    proposal_id: str
    category: OptimizationCategory
    component: str
    description: str
    estimated_impact: str  # low / medium / high
    estimated_risk: str  # low / medium / high
    evidence: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class PerformanceOptimizer:
    """Thread-safe singleton that analyses bottlenecks and proposes fixes."""

    _instance: PerformanceOptimizer | None = None
    _lock_cls = threading.Lock()

    def __new__(cls) -> PerformanceOptimizer:
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._init_lock = threading.Lock()
                    inst._proposals: list[OptimizationProposal] = []
                    inst._history: list[dict] = []
                    cls._instance = inst
        return cls._instance

    def analyze_bottlenecks(
        self, telemetry_data: dict
    ) -> list[OptimizationProposal]:
        """Inspect telemetry data and return proposals for detected bottlenecks."""
        proposals: list[OptimizationProposal] = []

        slow_models = telemetry_data.get("slow_models", [])
        for entry in slow_models:
            proposals.append(
                self.propose_optimization(
                    component=entry.get("model", "unknown"),
                    category=OptimizationCategory.SLOW_MODEL,
                    evidence=[entry],
                )
            )

        slow_tools = telemetry_data.get("slow_tools", [])
        for entry in slow_tools:
            proposals.append(
                self.propose_optimization(
                    component=entry.get("tool", "unknown"),
                    category=OptimizationCategory.SLOW_TOOL,
                    evidence=[entry],
                )
            )

        ctx_tokens = telemetry_data.get("context_tokens", 0)
        if ctx_tokens > 8000:
            proposals.append(
                self.propose_optimization(
                    component="context",
                    category=OptimizationCategory.EXCESSIVE_CONTEXT,
                    evidence=[{"context_tokens": ctx_tokens}],
                )
            )

        cache_misses = telemetry_data.get("cache_misses", 0)
        if cache_misses > 10:
            proposals.append(
                self.propose_optimization(
                    component="cache",
                    category=OptimizationCategory.CACHE_MISS,
                    evidence=[{"cache_misses": cache_misses}],
                )
            )

        blocking_io = telemetry_data.get("blocking_io_count", 0)
        if blocking_io > 5:
            proposals.append(
                self.propose_optimization(
                    component="io",
                    category=OptimizationCategory.BLOCKING_IO,
                    evidence=[{"blocking_io_count": blocking_io}],
                )
            )

        unnecessary_llm = telemetry_data.get("unnecessary_llm_calls", 0)
        if unnecessary_llm > 3:
            proposals.append(
                self.propose_optimization(
                    component="llm",
                    category=OptimizationCategory.UNNECESSARY_LLM,
                    evidence=[{"unnecessary_llm_calls": unnecessary_llm}],
                )
            )

        memory_mb = telemetry_data.get("memory_mb", 0)
        if memory_mb > 512:
            proposals.append(
                self.propose_optimization(
                    component="runtime",
                    category=OptimizationCategory.MEMORY_PRESSURE,
                    evidence=[{"memory_mb": memory_mb}],
                )
            )

        threading_issues = telemetry_data.get("concurrency_issues", 0)
        if threading_issues > 2:
            proposals.append(
                self.propose_optimization(
                    component="concurrency",
                    category=OptimizationCategory.BAD_CONCURRENCY,
                    evidence=[{"concurrency_issues": threading_issues}],
                )
            )

        serialization_ms = telemetry_data.get("serialization_ms", 0)
        if serialization_ms > 100:
            proposals.append(
                self.propose_optimization(
                    component="serialization",
                    category=OptimizationCategory.SERIALIZATION,
                    evidence=[{"serialization_ms": serialization_ms}],
                )
            )

        logger.info("Detected %d bottleneck proposal(s)", len(proposals))
        return proposals

    def propose_optimization(
        self,
        component: str,
        category: OptimizationCategory,
        evidence: list[dict],
    ) -> OptimizationProposal:
        """Create and register an optimization proposal."""
        proposal = OptimizationProposal(
            proposal_id=uuid.uuid4().hex[:12],
            category=category,
            component=component,
            description=self._build_description(category, component),
            estimated_impact=self.estimate_impact(
                OptimizationProposal(
                    proposal_id="",
                    category=category,
                    component=component,
                    description="",
                    estimated_impact="",
                    estimated_risk="",
                    evidence=evidence,
                )
            ),
            estimated_risk=self.estimate_risk(
                OptimizationProposal(
                    proposal_id="",
                    category=category,
                    component=component,
                    description="",
                    estimated_impact="",
                    estimated_risk="",
                    evidence=evidence,
                )
            ),
            evidence=evidence,
        )
        with self._init_lock:
            self._proposals.append(proposal)
            if len(self._proposals) > MAX_HISTORY:
                self._proposals = self._proposals[-MAX_HISTORY:]
        return proposal

    def estimate_impact(self, proposal: OptimizationProposal) -> str:
        """Return an impact estimate based on the proposal's category."""
        high_impact = {
            OptimizationCategory.SLOW_MODEL,
            OptimizationCategory.EXCESSIVE_CONTEXT,
            OptimizationCategory.MEMORY_PRESSURE,
            OptimizationCategory.UNNECESSARY_LLM,
        }
        medium_impact = {
            OptimizationCategory.SLOW_TOOL,
            OptimizationCategory.CACHE_MISS,
            OptimizationCategory.BLOCKING_IO,
        }
        if proposal.category in high_impact:
            return "high"
        if proposal.category in medium_impact:
            return "medium"
        return "low"

    def estimate_risk(self, proposal: OptimizationProposal) -> str:
        """Return a risk estimate based on the component's sensitivity."""
        high_risk_components = {"brain", "orchestrator", "dispatcher", "runtime"}
        medium_risk_components = {"llm", "cache", "concurrency"}
        comp = proposal.component.lower()
        if comp in high_risk_components:
            return "high"
        if comp in medium_risk_components:
            return "medium"
        return "low"

    def prioritize(
        self, proposals: list[OptimizationProposal]
    ) -> list[OptimizationProposal]:
        """Sort proposals by impact DESC then risk ASC."""
        impact_order = {"high": 3, "medium": 2, "low": 1}
        risk_order = {"high": 3, "medium": 2, "low": 1}
        return sorted(
            proposals,
            key=lambda p: (
                -impact_order.get(p.estimated_impact, 0),
                risk_order.get(p.estimated_risk, 0),
            ),
        )

    def record_optimization(
        self, proposal: OptimizationProposal, result: str
    ) -> None:
        """Record the outcome of applying a proposal."""
        record = {
            "proposal_id": proposal.proposal_id,
            "category": proposal.category.value,
            "component": proposal.component,
            "result": result,
            "timestamp": time.time(),
        }
        with self._init_lock:
            self._history.append(record)
            if len(self._history) > MAX_HISTORY:
                self._history = self._history[-MAX_HISTORY:]
        logger.info("Recorded optimization %s: %s", proposal.proposal_id, result)

    def get_optimization_history(self) -> list[dict]:
        """Return a copy of the recorded optimization history."""
        with self._init_lock:
            return list(self._history)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        with cls._lock_cls:
            cls._instance = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_description(
        category: OptimizationCategory, component: str
    ) -> str:
        templates = {
            OptimizationCategory.SLOW_MODEL: f"Model '{component}' is slow — consider switching or caching.",
            OptimizationCategory.SLOW_TOOL: f"Tool '{component}' has high latency — profile and optimise.",
            OptimizationCategory.EXCESSIVE_CONTEXT: "Context size exceeds threshold — summarise or trim.",
            OptimizationCategory.REPEATED_WORK: f"Component '{component}' is repeating work — add memoisation.",
            OptimizationCategory.CACHE_MISS: f"Cache misses detected in '{component}' — review eviction policy.",
            OptimizationCategory.SERIALIZATION: f"Serialisation in '{component}' is expensive — use a faster format.",
            OptimizationCategory.BLOCKING_IO: f"Blocking I/O detected in '{component}' — make async.",
            OptimizationCategory.UNNECESSARY_LLM: f"Unnecessary LLM calls in '{component}' — use deterministic fallback.",
            OptimizationCategory.BAD_CONCURRENCY: f"Concurrency issue in '{component}' — review locks / thread pool.",
            OptimizationCategory.MEMORY_PRESSURE: f"Memory pressure from '{component}' — profile and reduce allocations.",
        }
        return templates.get(category, f"Optimisation needed for '{component}'.")
