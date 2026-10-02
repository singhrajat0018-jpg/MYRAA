from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DeploymentStage(Enum):
    STABLE = "stable"
    CANDIDATE = "candidate"
    CANARY = "canary"
    RETIRED = "retired"


@dataclass
class CanaryMetrics:
    error_rate: float
    latency_p50: float
    latency_p99: float
    success_rate: float
    memory_mb: float
    sample_count: int


@dataclass
class DeploymentRecord:
    deployment_id: str
    version: str
    stage: DeploymentStage
    started_at: float
    metrics: Dict[str, float] = field(default_factory=dict)
    health_status: str = "unknown"
    rollback_count: int = 0
    max_rollbacks: int = 3
    code_path: str = ""
    canary_metrics: List[CanaryMetrics] = field(default_factory=list)

    def summary(self) -> Dict:
        return {
            "deployment_id": self.deployment_id,
            "version": self.version,
            "stage": self.stage.value,
            "started_at": self.started_at,
            "health_status": self.health_status,
            "rollback_count": self.rollback_count,
            "code_path": self.code_path,
            "canary_samples": sum(m.sample_count for m in self.canary_metrics),
        }


class DeploymentManager:
    """Manages canary deployments with automated rollback on metric degradation."""

    _instance: ClassVar[Optional["DeploymentManager"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    # Thresholds for rollback decisions
    MAX_ERROR_RATE = 0.05
    LATENCY_SPIKE_MULTIPLIER = 2.0
    MIN_SUCCESS_RATE = 0.95

    def __new__(cls) -> "DeploymentManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._deployments: Dict[str, DeploymentRecord] = {}
                    inst._history: List[DeploymentRecord] = []
                    inst._active_id: Optional[str] = None
                    inst._stable_version: Optional[str] = None
                    inst._baseline_latency: float = 100.0
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

    def create_candidate(self, version: str, code_path: str = "") -> DeploymentRecord:
        """Register a new deployment as a candidate."""
        dep_id = f"deploy-{version}-{uuid.uuid4().hex[:8]}"
        record = DeploymentRecord(
            deployment_id=dep_id,
            version=version,
            stage=DeploymentStage.CANDIDATE,
            started_at=time.time(),
            code_path=code_path,
            health_status="pending",
        )
        with self._lock_inst:
            self._deployments[dep_id] = record
            self._history.append(record)
            if len(self._history) > 20:
                self._history = self._history[-20:]
        logger.info("Created candidate deployment %s for version %s", dep_id, version)
        return record

    def promote_to_canary(self, deployment_id: str) -> bool:
        """Promote a candidate deployment to canary stage."""
        with self._lock_inst:
            record = self._deployments.get(deployment_id)
            if record is None:
                logger.warning("Deployment %s not found", deployment_id)
                return False
            if record.stage != DeploymentStage.CANDIDATE:
                logger.warning(
                    "Deployment %s is %s, expected CANDIDATE", deployment_id, record.stage.value
                )
                return False
            record.stage = DeploymentStage.CANARY
            record.health_status = "canary_active"
            logger.info("Promoted %s to CANARY", deployment_id)
            return True

    def promote_to_stable(self, deployment_id: str) -> bool:
        """Promote a canary deployment to stable, retiring any previous stable."""
        with self._lock_inst:
            record = self._deployments.get(deployment_id)
            if record is None:
                logger.warning("Deployment %s not found", deployment_id)
                return False
            if record.stage != DeploymentStage.CANARY:
                logger.warning(
                    "Deployment %s is %s, expected CANARY", deployment_id, record.stage.value
                )
                return False
            # Retire previous stable
            for dep in self._deployments.values():
                if dep.stage == DeploymentStage.STABLE:
                    dep.stage = DeploymentStage.RETIRED
                    dep.health_status = "retired"
                    logger.info("Retired previous stable deployment %s", dep.deployment_id)
            record.stage = DeploymentStage.STABLE
            record.health_status = "healthy"
            self._active_id = deployment_id
            self._stable_version = record.version
            logger.info("Promoted %s to STABLE (version %s)", deployment_id, record.version)
            return True

    def rollback(self, deployment_id: str, reason: str) -> bool:
        """Roll back a deployment, reverting to the previous stable version."""
        with self._lock_inst:
            record = self._deployments.get(deployment_id)
            if record is None:
                logger.warning("Deployment %s not found for rollback", deployment_id)
                return False
            if record.rollback_count >= record.max_rollbacks:
                logger.error(
                    "Deployment %s exceeded max rollbacks (%d)",
                    deployment_id, record.max_rollbacks,
                )
                record.health_status = "max_rollbacks_exceeded"
                return False
            record.rollback_count += 1
            record.stage = DeploymentStage.RETIRED
            record.health_status = f"rolled_back: {reason}"
            if self._active_id == deployment_id:
                self._active_id = None
            logger.info(
                "Rolled back deployment %s (reason: %s, rollback #%d)",
                deployment_id, reason, record.rollback_count,
            )
            return True

    def record_canary_metrics(self, deployment_id: str, metrics: CanaryMetrics) -> None:
        """Record canary metrics for a deployment and check for rollback."""
        with self._lock_inst:
            record = self._deployments.get(deployment_id)
            if record is None:
                logger.warning("Deployment %s not found for metrics", deployment_id)
                return
            record.canary_metrics.append(metrics)
            # Update baseline from first sample if available
            if len(record.canary_metrics) == 1:
                self._baseline_latency = metrics.latency_p50

        should_rb, rb_reason = self.should_rollback(deployment_id)
        if should_rb:
            logger.warning("Auto-rollback triggered for %s: %s", deployment_id, rb_reason)
            self.rollback(deployment_id, rb_reason)

    def should_rollback(self, deployment_id: str) -> Tuple[bool, str]:
        """Evaluate canary metrics to decide if rollback is needed."""
        with self._lock_inst:
            record = self._deployments.get(deployment_id)
            if record is None:
                return False, ""
            if not record.canary_metrics:
                return False, ""
            latest = record.canary_metrics[-1]

        # Check error rate
        if latest.error_rate > self.MAX_ERROR_RATE:
            return True, f"error_rate {latest.error_rate:.2%} > {self.MAX_ERROR_RATE:.0%}"

        # Check latency spike
        if self._baseline_latency > 0 and latest.latency_p99 > self._baseline_latency * self.LATENCY_SPIKE_MULTIPLIER:
            return True, (
                f"latency_p99 {latest.latency_p99:.1f}ms > "
                f"{self.LATENCY_SPIKE_MULTIPLIER}x baseline {self._baseline_latency:.1f}ms"
            )

        # Check success rate
        if latest.success_rate < self.MIN_SUCCESS_RATE:
            return True, f"success_rate {latest.success_rate:.2%} < {self.MIN_SUCCESS_RATE:.0%}"

        return False, ""

    def get_active_deployment(self) -> Optional[DeploymentRecord]:
        with self._lock_inst:
            if self._active_id and self._active_id in self._deployments:
                return self._deployments[self._active_id]
        return None

    def get_deployment_history(self) -> List[DeploymentRecord]:
        with self._lock_inst:
            return list(self._history)

    def get_stable_version(self) -> Optional[str]:
        with self._lock_inst:
            return self._stable_version
