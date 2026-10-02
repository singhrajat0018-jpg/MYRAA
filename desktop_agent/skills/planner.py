"""AgentPlanner — task decomposition and execution graph for MYRAA.

Decomposes goals into subgoals, creates dependency graphs, maps skills,
and generates execution plans for single-agent or multi-agent modes.
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .skill import Skill, SkillDomain, SkillState
from .registry import SkillRegistry
from .worker import WorkerContract

logger = logging.getLogger(__name__)


class PlanMode(str, Enum):
    SINGLE = "single"          # One worker, no overhead
    SEQUENTIAL = "sequential"  # Workers in order
    PARALLEL = "parallel"      # Independent workers run concurrently
    HIERARCHICAL = "hierarchical"  # Supervisor → sub-workers
    DELEGATED = "delegated"    # One worker delegates to another


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """Single step in an execution plan."""
    step_id: str
    task_id: str
    description: str
    skill_id: str
    worker_class: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    timeout_seconds: float = 60.0
    priority: int = 5
    retry_budget: int = 2
    retries_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "task_id": self.task_id,
            "description": self.description,
            "skill_id": self.skill_id,
            "worker_class": self.worker_class,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "priority": self.priority,
            "retry_budget": self.retry_budget,
            "retries_used": self.retries_used,
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan for a goal."""
    plan_id: str
    goal: str
    mode: PlanMode
    steps: List[PlanStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def ready_steps(self) -> List[PlanStep]:
        """Get steps whose dependencies are all completed."""
        completed = {s.step_id for s in self.steps if s.status == PlanStepStatus.COMPLETED}
        ready = []
        for step in self.steps:
            if step.status != PlanStepStatus.PENDING:
                continue
            if all(dep in completed for dep in step.depends_on):
                ready.append(step)
        return ready

    def is_complete(self) -> bool:
        return all(
            s.status in (PlanStepStatus.COMPLETED, PlanStepStatus.SKIPPED)
            for s in self.steps
        )

    def has_failures(self) -> bool:
        return any(s.status == PlanStepStatus.FAILED for s in self.steps)

    def next_step(self) -> Optional[PlanStep]:
        ready = self.ready_steps()
        if not ready:
            return None
        ready.sort(key=lambda s: s.priority)
        return ready[0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "mode": self.mode.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
        }


class AgentPlanner:
    """Decomposes goals into execution plans.

    Uses TaskRouter output + SkillRegistry + WorldModel context.
    """

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
    ) -> None:
        self._registry = registry or SkillRegistry()
        self._lock = threading.Lock()
        self._plan_counter = 0

    def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """Create an execution plan for a goal.

        Determines: mode, skills needed, dependency graph, execution order.
        """
        ctx = context or {}
        task_type = ctx.get("task_type", "general")

        # Determine plan mode
        mode = self._determine_mode(goal, task_type, ctx)

        # Decompose into steps
        steps = self._decompose(goal, task_type, mode, ctx)

        with self._lock:
            self._plan_counter += 1
            plan_id = f"plan-{self._plan_counter:04d}"

        plan = ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            mode=mode,
            steps=steps,
            metadata={"task_type": task_type, "context_keys": list(ctx.keys())},
        )

        logger.info(
            "Created plan %s: %s mode, %d steps",
            plan_id, mode.value, len(steps),
        )
        return plan

    def _determine_mode(
        self,
        goal: str,
        task_type: str,
        context: Dict[str, Any],
    ) -> PlanMode:
        """Determine execution mode based on goal complexity."""
        # Simple tasks → single agent
        simple_types = {"conversation", "direct_knowledge", "fast_answer"}
        if task_type.lower() in simple_types:
            return PlanMode.SINGLE

        # Complex tasks → multi-agent
        complex_keywords = [
            "build", "create project", "analyze", "research",
            "portfolio", "report", "fix bug", "run tests", "deploy",
        ]
        if any(kw in goal.lower() for kw in complex_keywords):
            # Default to sequential for dependent workflows
            # Only parallelize if explicitly independent tasks are mentioned
            independent_keywords = ["meanwhile", "in parallel", "at the same time", "simultaneously"]
            if any(kw in goal.lower() for kw in independent_keywords):
                return PlanMode.PARALLEL
            return PlanMode.SEQUENTIAL

        # Default
        return PlanMode.SINGLE

    def _decompose(
        self,
        goal: str,
        task_type: str,
        mode: PlanMode,
        context: Dict[str, Any],
    ) -> List[PlanStep]:
        """Decompose goal into plan steps."""
        steps: List[PlanStep] = []
        goal_lower = goal.lower()

        # Route to appropriate decomposition
        if any(kw in goal_lower for kw in ["build", "create project", "scaffold"]):
            steps = self._plan_project(goal, context)
        elif any(kw in goal_lower for kw in ["research", "find", "search", "look up"]):
            steps = self._plan_research(goal, context)
        elif any(kw in goal_lower for kw in ["fix", "bug", "debug", "error"]):
            steps = self._plan_debug(goal, context)
        elif any(kw in goal_lower for kw in ["test", "run tests", "verify"]):
            steps = self._plan_test(goal, context)
        elif any(kw in goal_lower for kw in ["analyze", "portfolio", "stock", "trading"]):
            steps = self._plan_analysis(goal, context)
        elif any(kw in goal_lower for kw in ["screenshot", "ocr", "screen", "what's on"]):
            steps = self._plan_vision(goal, context)
        elif any(kw in goal_lower for kw in ["open", "close", "volume", "brightness", "type", "click"]):
            steps = self._plan_desktop(goal, context)
        else:
            steps = self._plan_generic(goal, context)

        return steps

    def _plan_project(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="scaffold",
                task_id="t1",
                description=f"Scaffold project: {goal}",
                skill_id="projects",
                worker_class="ProjectWorker",
                input_data={"action": "create", "description": goal},
            ),
            PlanStep(
                step_id="implement",
                task_id="t2",
                description="Implement core files",
                skill_id="coding",
                worker_class="CodingWorker",
                input_data={"action": "implement", "description": goal},
                depends_on=["scaffold"],
            ),
            PlanStep(
                step_id="test",
                task_id="t3",
                description="Run tests",
                skill_id="coding",
                worker_class="CodingWorker",
                input_data={"action": "run tests"},
                depends_on=["implement"],
            ),
            PlanStep(
                step_id="verify",
                task_id="t4",
                description="Verify project",
                skill_id="verification",
                worker_class="VerificationWorker",
                input_data={"action": "verify"},
                depends_on=["test"],
            ),
        ]

    def _plan_research(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="research",
                task_id="t1",
                description=f"Research: {goal}",
                skill_id="research",
                worker_class="ResearchWorker",
                input_data={"query": goal},
            ),
            PlanStep(
                step_id="verify",
                task_id="t2",
                description="Verify research findings",
                skill_id="verification",
                worker_class="VerificationWorker",
                input_data={"action": "verify research"},
                depends_on=["research"],
            ),
        ]

    def _plan_debug(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="diagnose",
                task_id="t1",
                description=f"Diagnose: {goal}",
                skill_id="diagnostics",
                worker_class="DiagnosticsWorker",
                input_data={"action": "diagnose", "description": goal},
            ),
            PlanStep(
                step_id="fix",
                task_id="t2",
                description="Apply fix",
                skill_id="coding",
                worker_class="CodingWorker",
                input_data={"action": "fix", "description": goal},
                depends_on=["diagnose"],
            ),
            PlanStep(
                step_id="test",
                task_id="t3",
                description="Run tests after fix",
                skill_id="coding",
                worker_class="CodingWorker",
                input_data={"action": "run tests"},
                depends_on=["fix"],
            ),
            PlanStep(
                step_id="verify",
                task_id="t4",
                description="Verify fix",
                skill_id="verification",
                worker_class="VerificationWorker",
                input_data={"action": "verify"},
                depends_on=["test"],
            ),
        ]

    def _plan_test(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="test",
                task_id="t1",
                description=f"Run tests: {goal}",
                skill_id="coding",
                worker_class="CodingWorker",
                input_data={"action": "run tests", "description": goal},
            ),
            PlanStep(
                step_id="verify",
                task_id="t2",
                description="Verify test results",
                skill_id="verification",
                worker_class="VerificationWorker",
                input_data={"action": "verify tests"},
                depends_on=["test"],
            ),
        ]

    def _plan_analysis(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="analyze",
                task_id="t1",
                description=f"Analyze: {goal}",
                skill_id="trading",
                worker_class="TradingWorker",
                input_data={"action": "analyze", "description": goal},
            ),
            PlanStep(
                step_id="verify",
                task_id="t2",
                description="Verify analysis",
                skill_id="verification",
                worker_class="VerificationWorker",
                input_data={"action": "verify analysis"},
                depends_on=["analyze"],
            ),
        ]

    def _plan_vision(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="vision",
                task_id="t1",
                description=f"Vision: {goal}",
                skill_id="vision",
                worker_class="VisionWorker",
                input_data={"action": "analyze", "description": goal},
            ),
            PlanStep(
                step_id="verify",
                task_id="t2",
                description="Verify vision result",
                skill_id="verification",
                worker_class="VerificationWorker",
                input_data={"action": "verify vision"},
                depends_on=["vision"],
            ),
        ]

    def _plan_desktop(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="desktop",
                task_id="t1",
                description=f"Desktop action: {goal}",
                skill_id="desktop",
                worker_class="DesktopWorker",
                input_data={"action": "execute", "description": goal},
            ),
        ]

    def _plan_generic(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        return [
            PlanStep(
                step_id="execute",
                task_id="t1",
                description=f"Execute: {goal}",
                skill_id="desktop",
                worker_class="DesktopWorker",
                input_data={"action": "execute", "description": goal},
            ),
            PlanStep(
                step_id="verify",
                task_id="t2",
                description="Verify result",
                skill_id="verification",
                worker_class="VerificationWorker",
                input_data={"action": "verify"},
                depends_on=["execute"],
            ),
        ]

    def to_contracts(self, plan: ExecutionPlan) -> List[WorkerContract]:
        """Convert plan steps to WorkerContracts."""
        contracts = []
        for step in plan.steps:
            contracts.append(WorkerContract(
                task_id=step.task_id,
                task_description=step.description,
                skill_id=step.skill_id,
                input_data=step.input_data,
                timeout_seconds=step.timeout_seconds,
                retry_budget=step.retry_budget,
                priority=step.priority,
                depends_on=step.depends_on,
            ))
        return contracts
