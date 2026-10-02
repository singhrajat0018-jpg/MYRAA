"""Workflow Self-Optimization for MYRAA self-healing."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_RECORDS = 200
MIN_IMPROVEMENT_PCT = 15.0


@dataclass
class WorkflowStep:
    """A single step inside a workflow execution."""

    name: str
    duration_ms: float
    success: bool
    tool_used: str | None = None


@dataclass
class WorkflowRecord:
    """Complete record of one workflow execution."""

    workflow_id: str
    name: str
    steps: list[WorkflowStep]
    total_duration_ms: float
    success: bool
    llm_calls: int
    search_calls: int
    repeated_steps: list[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class OptimizedWorkflow:
    """A proposed optimised variant of a workflow."""

    original_id: str
    optimized_steps: list[str]
    estimated_duration_ms: float
    estimated_llm_calls: int
    improvement_pct: float


class WorkflowOptimizer:
    """Thread-safe singleton that records, analyses and optimises workflows."""

    _instance: WorkflowOptimizer | None = None
    _lock_cls = threading.Lock()

    def __new__(cls) -> WorkflowOptimizer:
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._init_lock = threading.Lock()
                    inst._records: list[WorkflowRecord] = []
                    cls._instance = inst
        return cls._instance

    def record_workflow(
        self,
        name: str,
        steps: list[WorkflowStep],
        llm_calls: int,
        search_calls: int,
    ) -> WorkflowRecord:
        """Persist a workflow execution record and return it."""
        total = sum(s.duration_ms for s in steps)
        success = all(s.success for s in steps)
        repeated = self._find_repeated_steps(steps)

        rec = WorkflowRecord(
            workflow_id=uuid.uuid4().hex[:12],
            name=name,
            steps=list(steps),
            total_duration_ms=total,
            success=success,
            llm_calls=llm_calls,
            search_calls=search_calls,
            repeated_steps=repeated,
            timestamp=time.time(),
        )
        with self._init_lock:
            self._records.append(rec)
            if len(self._records) > MAX_RECORDS:
                self._records = self._records[-MAX_RECORDS:]
        logger.info(
            "Recorded workflow '%s' (id=%s, duration=%.1fms, success=%s)",
            name,
            rec.workflow_id,
            total,
            success,
        )
        return rec

    def analyze_patterns(self, workflow_name: str) -> dict:
        """Analyse historical records for *workflow_name* and return patterns."""
        records = [
            r for r in self._records if r.name == workflow_name
        ]
        if not records:
            return {"error": f"No records found for workflow '{workflow_name}'"}

        durations = [r.total_duration_ms for r in records]
        success_count = sum(1 for r in records if r.success)
        all_repeated: list[str] = []
        for r in records:
            all_repeated.extend(r.repeated_steps)

        repeated_freq = Counter(all_repeated).most_common()
        latencies = sorted(durations)
        p95_idx = max(0, int(len(latencies) * 0.95) - 1)

        failure_steps: list[str] = []
        for r in records:
            if not r.success:
                for s in r.steps:
                    if not s.success:
                        failure_steps.append(s.name)

        return {
            "workflow_name": workflow_name,
            "total_runs": len(records),
            "success_rate": success_count / len(records) if records else 0.0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0,
            "p95_duration_ms": latencies[p95_idx] if latencies else 0.0,
            "repeated_steps": repeated_freq,
            "failure_steps": Counter(failure_steps).most_common(),
        }

    def propose_optimization(
        self, workflow_name: str
    ) -> OptimizedWorkflow | None:
        """Return an optimised workflow proposal only when evidence is clear."""
        records = [
            r for r in self._records if r.name == workflow_name
        ]
        if len(records) < 2:
            return None

        latest = records[-1]
        patterns = self.analyze_patterns(workflow_name)
        if "error" in patterns:
            return None

        optimised_steps: list[str] = []
        removed_repeated = set()
        for step_name, count in patterns.get("repeated_steps", []):
            if count >= 3:
                optimised_steps.append(f"deduplicate:{step_name}")
                removed_repeated.add(step_name)

        failure_steps = {name for name, _ in patterns.get("failure_steps", [])}
        for fs in failure_steps:
            if fs not in removed_repeated:
                optimised_steps.append(f"add_fallback:{fs}")

        avg_duration = patterns.get("avg_duration_ms", latest.total_duration_ms)
        estimated_duration = avg_duration * 0.80
        estimated_llm = max(0, latest.llm_calls - 1) if latest.llm_calls > 0 else 0

        improvement = self._calculate_improvement(
            latest,
            OptimizedWorkflow(
                original_id=latest.workflow_id,
                optimized_steps=optimised_steps,
                estimated_duration_ms=estimated_duration,
                estimated_llm_calls=estimated_llm,
                improvement_pct=0.0,
            ),
        )

        if improvement < MIN_IMPROVEMENT_PCT:
            return None

        proposal = OptimizedWorkflow(
            original_id=latest.workflow_id,
            optimized_steps=optimised_steps,
            estimated_duration_ms=estimated_duration,
            estimated_llm_calls=estimated_llm,
            improvement_pct=improvement,
        )
        logger.info(
            "Optimisation proposed for '%s': %.1f%% improvement",
            workflow_name,
            improvement,
        )
        return proposal

    def get_workflow_stats(self) -> dict:
        """Return per-workflow statistics (success rates, average durations)."""
        by_name: dict[str, list[WorkflowRecord]] = {}
        with self._init_lock:
            for rec in self._records:
                by_name.setdefault(rec.name, []).append(rec)

        stats: dict[str, dict] = {}
        for name, recs in by_name.items():
            durations = [r.total_duration_ms for r in recs]
            success = sum(1 for r in recs if r.success)
            stats[name] = {
                "total_runs": len(recs),
                "success_rate": success / len(recs) if recs else 0.0,
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0,
                "avg_llm_calls": sum(r.llm_calls for r in recs) / len(recs) if recs else 0.0,
                "avg_search_calls": sum(r.search_calls for r in recs) / len(recs) if recs else 0.0,
            }
        return stats

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        with cls._lock_cls:
            cls._instance = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_repeated_steps(steps: list[WorkflowStep]) -> list[str]:
        """Return names of steps that appear more than once in *steps*."""
        counts = Counter(s.name for s in steps)
        return [name for name, cnt in counts.items() if cnt > 1]

    @staticmethod
    def _calculate_improvement(
        original: WorkflowRecord, optimized: OptimizedWorkflow
    ) -> float:
        """Return the estimated percentage improvement in duration."""
        if original.total_duration_ms <= 0:
            return 0.0
        saving = original.total_duration_ms - optimized.estimated_duration_ms
        return max(0.0, (saving / original.total_duration_ms) * 100.0)
