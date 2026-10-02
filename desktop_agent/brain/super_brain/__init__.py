"""
MYRAA Super-Brain (EPIC-BRAIN Phase 2).

A coordination layer that UNIFIES the existing MYRAA cognitive components
into one goal-oriented, context-aware, planning-capable, self-correcting,
long-horizon cognitive system.

It REUSES the existing systems and never duplicates them:

  AIManager.route()        -> routing authority (AI Manager 4.1)
  SemanticTask/ResponseRouter -> perception/semantics
  WorldModel/Perception    -> world state
  MemoryManager            -> memory
  Planner/ActionBuilder    -> step building
  ExecutionPlan/PlanStep   -> plan representation
  Orchestrator             -> step execution
  RecoveryEngine           -> retry/recovery
  VerificationManager      -> outcome verification
  CommandDispatcher/PermissionManager/ValidationLayer -> tool + safety
  TelemetryCollector/MetricsCollector -> observability
  FeedbackStore            -> offline experience
"""

from __future__ import annotations

__all__ = ["SuperBrain"]


def __getattr__(name: str):
    # PEP 562 lazy attribute: import the facade only when requested so
    # submodules remain importable without pulling the full SuperBrain graph.
    if name == "SuperBrain":
        from .super_brain import SuperBrain

        return SuperBrain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")