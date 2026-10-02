from __future__ import annotations

"""Self-Healing, Self-Engineering, and Patch modules for MYRAA.

This package exposes all public classes from every submodule for
convenient access::

    from desktop_agent.self_healing import SelfHealingManager
    from desktop_agent.self_healing import DiagnosticsEngine, HealingEngine
"""

from .diagnostics import DiagnosticsEngine, DiagnosticResult, HealthStatus, SubsystemHealth
from .root_cause import RootCauseAnalyzer, RootCause, Evidence, EvidenceType
from .healing import HealingEngine, HealingAction, HealingResult, HealingSeverity, RepairProposal
from .engineering import SelfEngineeringEngine, EngineeringRequest, EngineeringResult, EngineeringStatus
from .patch import PatchGenerator, PatchRecord, PatchRisk, ImpactArea
from .regression import RegressionAnalyzer, RegressionStatus, BeforeAfter, BehavioralDiff
from .optimization import PerformanceOptimizer, OptimizationCategory, OptimizationProposal
from .reflection import SelfReflectionEngine, ReflectionRecord, TaskOutcome, OutcomeRecord
from .workflow import WorkflowOptimizer, WorkflowStep, WorkflowRecord, OptimizedWorkflow
from .model_improvement import ModelVersionManager, CapabilityGapDetector, ModelVersion, CapabilityGap
from .deployment import DeploymentManager, DeploymentRecord, DeploymentStage, CanaryMetrics
from .versioning import VersionManager, MYRAAVersion
from .security import SecurityGate, ProtectedArea, SecurityViolation
from .guards import ResourceGuard, LoopProtectionGuard, ResourceLimits, LoopGuardConfig
from .escalation import HumanEscalation, EscalationRequest, EscalationReason
from .telemetry import SelfHealingTelemetry, HealingEvent, SystemHealthSnapshot
from .manager import SelfHealingManager

__all__ = [
    "DiagnosticsEngine", "DiagnosticResult", "HealthStatus", "SubsystemHealth",
    "RootCauseAnalyzer", "RootCause", "Evidence", "EvidenceType",
    "HealingEngine", "HealingAction", "HealingResult", "HealingSeverity", "RepairProposal",
    "SelfEngineeringEngine", "EngineeringRequest", "EngineeringResult", "EngineeringStatus",
    "PatchGenerator", "PatchRecord", "PatchRisk", "ImpactArea",
    "RegressionAnalyzer", "RegressionStatus", "BeforeAfter", "BehavioralDiff",
    "PerformanceOptimizer", "OptimizationCategory", "OptimizationProposal",
    "SelfReflectionEngine", "ReflectionRecord", "TaskOutcome", "OutcomeRecord",
    "WorkflowOptimizer", "WorkflowStep", "WorkflowRecord", "OptimizedWorkflow",
    "ModelVersionManager", "CapabilityGapDetector", "ModelVersion", "CapabilityGap",
    "DeploymentManager", "DeploymentRecord", "DeploymentStage", "CanaryMetrics",
    "VersionManager", "MYRAAVersion",
    "SecurityGate", "ProtectedArea", "SecurityViolation",
    "ResourceGuard", "LoopProtectionGuard", "ResourceLimits", "LoopGuardConfig",
    "HumanEscalation", "EscalationRequest", "EscalationReason",
    "SelfHealingTelemetry", "HealingEvent", "SystemHealthSnapshot",
    "SelfHealingManager",
]
