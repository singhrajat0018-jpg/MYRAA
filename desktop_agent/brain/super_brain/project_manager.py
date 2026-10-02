"""
MYRAA Super-Brain -- Project Manager (Phase A).

Manages project state, checkpoint/resume, progress tracking, and project memory.
Single authority for project lifecycle -- does NOT duplicate Planner/Memory/Tools.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProjectTask:
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    depends_on: List[str] = field(default_factory=list)
    milestone: str = ""
    tool_used: str = ""
    result_summary: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    files_changed: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "status": self.status.value, "depends_on": list(self.depends_on),
            "milestone": self.milestone, "tool_used": self.tool_used,
            "result_summary": self.result_summary, "error": self.error,
            "created_at": self.created_at, "started_at": self.started_at,
            "completed_at": self.completed_at, "files_changed": list(self.files_changed),
        }


@dataclass
class ProjectMilestone:
    id: str
    title: str
    description: str = ""
    status: MilestoneStatus = MilestoneStatus.PENDING
    task_ids: List[str] = field(default_factory=list)
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "status": self.status.value, "task_ids": list(self.task_ids), "order": self.order,
        }


class ProjectTaskGraph:
    def __init__(self) -> None:
        self.tasks: Dict[str, ProjectTask] = {}
        self.milestones: Dict[str, ProjectMilestone] = {}

    def add_task(self, task: ProjectTask) -> None:
        self.tasks[task.id] = task

    def add_milestone(self, milestone: ProjectMilestone) -> None:
        self.milestones[milestone.id] = milestone

    def get_task(self, task_id: str) -> Optional[ProjectTask]:
        return self.tasks.get(task_id)

    def pending_tasks(self) -> List[ProjectTask]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]

    def active_tasks(self) -> List[ProjectTask]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.ACTIVE]

    def completed_tasks(self) -> List[ProjectTask]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]

    def failed_tasks(self) -> List[ProjectTask]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]

    def blocked_tasks(self) -> List[ProjectTask]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.BLOCKED]

    def next_ready_tasks(self) -> List[ProjectTask]:
        ready = []
        for task in self.pending_tasks():
            deps_met = all(
                self.tasks.get(dep_id) is not None
                and self.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.depends_on
            )
            if deps_met:
                ready.append(task)
        return ready

    def all_finished(self) -> bool:
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
            for t in self.tasks.values()
        )

    def has_failures(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks.values())

    def progress_pct(self) -> float:
        total = len(self.tasks)
        if total == 0:
            return 0.0
        done = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        return round(done / total * 100, 1)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_tasks": len(self.tasks),
            "completed": len(self.completed_tasks()),
            "active": len(self.active_tasks()),
            "pending": len(self.pending_tasks()),
            "failed": len(self.failed_tasks()),
            "blocked": len(self.blocked_tasks()),
            "progress_pct": self.progress_pct(),
            "all_finished": self.all_finished(),
            "has_failures": self.has_failures(),
            "milestones": {mid: m.to_dict() for mid, m in self.milestones.items()},
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "milestones": {mid: m.to_dict() for mid, m in self.milestones.items()},
            "summary": self.summary(),
        }


@dataclass
class ProjectCheckpoint:
    checkpoint_id: str
    project_id: str
    timestamp: float
    task_graph_state: Dict[str, Any]
    current_milestone: str
    completed_milestones: List[str]
    active_task_id: Optional[str]
    files_changed: List[str]
    git_state: Dict[str, Any]
    test_results: Dict[str, Any]
    blocker: str = ""
    next_action: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id, "project_id": self.project_id,
            "timestamp": self.timestamp, "task_graph_state": self.task_graph_state,
            "current_milestone": self.current_milestone,
            "completed_milestones": list(self.completed_milestones),
            "active_task_id": self.active_task_id,
            "files_changed": list(self.files_changed),
            "git_state": self.git_state, "test_results": self.test_results,
            "blocker": self.blocker, "next_action": self.next_action,
        }


@dataclass
class ProjectState:
    project_id: str
    name: str
    description: str = ""
    project_type: str = "python"
    root_path: str = ""
    tech_stack: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    task_graph: ProjectTaskGraph = field(default_factory=ProjectTaskGraph)
    checkpoints: List[ProjectCheckpoint] = field(default_factory=list)
    current_milestone: str = ""
    completed_milestones: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    git_initialized: bool = False
    last_test_results: Dict[str, Any] = field(default_factory=dict)
    architecture_decisions: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id, "name": self.name,
            "description": self.description, "project_type": self.project_type,
            "root_path": self.root_path, "tech_stack": list(self.tech_stack),
            "requirements": list(self.requirements),
            "constraints": list(self.constraints),
            "created_at": self.created_at, "updated_at": self.updated_at,
            "task_graph": self.task_graph.to_dict(),
            "checkpoints": [c.to_dict() for c in self.checkpoints[-5:]],
            "current_milestone": self.current_milestone,
            "completed_milestones": list(self.completed_milestones),
            "files_created": list(self.files_created),
            "files_modified": list(self.files_modified),
            "git_initialized": self.git_initialized,
            "last_test_results": self.last_test_results,
            "progress_pct": self.task_graph.progress_pct(),
        }


class ProjectManager:
    """Single authority for project lifecycle management (Phase A)."""

    def __init__(self, memory_2_0: Optional[Any] = None) -> None:
        self.memory_2_0 = memory_2_0
        self._active_projects: Dict[str, ProjectState] = {}
        self._project_index: Dict[str, str] = {}

    def create_project(
        self,
        name: str,
        description: str = "",
        project_type: str = "python",
        root_path: str = "",
        tech_stack: Optional[List[str]] = None,
        requirements: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
    ) -> ProjectState:
        project_id = f"proj-{uuid.uuid4().hex[:8]}"
        state = ProjectState(
            project_id=project_id, name=name, description=description,
            project_type=project_type, root_path=root_path,
            tech_stack=tech_stack or [], requirements=requirements or [],
            constraints=constraints or [],
        )
        self._active_projects[project_id] = state
        self._project_index[name.lower()] = project_id
        log.info("Created project '%s' (id=%s)", name, project_id)
        return state

    def get_project(self, project_id: str) -> Optional[ProjectState]:
        return self._active_projects.get(project_id)

    def get_project_by_name(self, name: str) -> Optional[ProjectState]:
        pid = self._project_index.get(name.lower())
        if pid:
            return self._active_projects.get(pid)
        return None

    def list_projects(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._active_projects.values()]

    def find_project_by_path(self, root_path: str) -> Optional[ProjectState]:
        resolved = str(Path(root_path).resolve())
        for state in self._active_projects.values():
            if state.root_path and str(Path(state.root_path).resolve()) == resolved:
                return state
        return None

    def remove_project(self, project_id: str) -> bool:
        state = self._active_projects.pop(project_id, None)
        if state:
            self._project_index.pop(state.name.lower(), None)
            return True
        return False

    def update_task(
        self, project_id: str, task_id: str, status: Optional[TaskStatus] = None,
        result_summary: str = "", error: str = "", tool_used: str = "",
        files_changed: Optional[List[str]] = None,
    ) -> Optional[ProjectTask]:
        state = self._active_projects.get(project_id)
        if not state:
            return None
        task = state.task_graph.get_task(task_id)
        if not task:
            return None
        if status:
            task.status = status
            if status == TaskStatus.ACTIVE:
                task.started_at = time.time()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = time.time()
        if result_summary:
            task.result_summary = result_summary
        if error:
            task.error = error
        if tool_used:
            task.tool_used = tool_used
        if files_changed:
            task.files_changed = files_changed
            for fc in files_changed:
                if fc not in state.files_created and fc not in state.files_modified:
                    state.files_modified.append(fc)
        state.updated_at = time.time()
        self._update_milestone_status(state)
        return task

    def add_task_to_project(
        self, project_id: str, task: ProjectTask,
    ) -> bool:
        state = self._active_projects.get(project_id)
        if not state:
            return False
        state.task_graph.add_task(task)
        if task.milestone and task.milestone in state.task_graph.milestones:
            ms = state.task_graph.milestones[task.milestone]
            if task.id not in ms.task_ids:
                ms.task_ids.append(task.id)
        state.updated_at = time.time()
        return True

    def add_milestone_to_project(
        self, project_id: str, milestone: ProjectMilestone,
    ) -> bool:
        state = self._active_projects.get(project_id)
        if not state:
            return False
        state.task_graph.add_milestone(milestone)
        state.updated_at = time.time()
        return True

    def create_checkpoint(
        self, project_id: str, blocker: str = "", next_action: str = "",
    ) -> Optional[ProjectCheckpoint]:
        state = self._active_projects.get(project_id)
        if not state:
            return None
        active = state.task_graph.active_tasks()
        cp = ProjectCheckpoint(
            checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
            project_id=project_id, timestamp=time.time(),
            task_graph_state=state.task_graph.to_dict(),
            current_milestone=state.current_milestone,
            completed_milestones=list(state.completed_milestones),
            active_task_id=active[0].id if active else None,
            files_changed=list(state.files_modified),
            git_state={}, test_results=dict(state.last_test_results),
            blocker=blocker, next_action=next_action,
        )
        state.checkpoints.append(cp)
        log.info("Checkpoint created for project %s: %s", project_id, cp.checkpoint_id)
        return cp

    def get_latest_checkpoint(self, project_id: str) -> Optional[ProjectCheckpoint]:
        state = self._active_projects.get(project_id)
        if not state or not state.checkpoints:
            return None
        return state.checkpoints[-1]

    def progress_report(self, project_id: str) -> Dict[str, Any]:
        state = self._active_projects.get(project_id)
        if not state:
            return {"error": "project not found"}
        tg = state.task_graph
        failed = tg.failed_tasks()
        next_tasks = tg.next_ready_tasks()
        return {
            "project": state.name,
            "progress_pct": tg.progress_pct(),
            "completed": len(tg.completed_tasks()),
            "total": len(tg.tasks),
            "active": [t.title for t in tg.active_tasks()],
            "next": [t.title for t in next_tasks],
            "failed": [{"title": t.title, "error": t.error} for t in failed],
            "current_milestone": state.current_milestone,
            "completed_milestones": list(state.completed_milestones),
            "files_created": len(state.files_created),
            "files_modified": len(state.files_modified),
        }

    def write_project_memory(self, project_id: str) -> bool:
        if not self.memory_2_0:
            return False
        state = self._active_projects.get(project_id)
        if not state:
            return False
        try:
            from desktop_agent.brain.memory.unified_model import (
                MemoryRecord, MemoryType, MemoryScope, MemoryStatus,
                RetentionPolicy, Provenance,
            )
            record = MemoryRecord(
                type=MemoryType.EPISODIC,
                content=json.dumps(state.to_dict(), default=str),
                summary=f"Project state: {state.name} ({state.task_graph.progress_pct()}% complete)",
                source="project_manager",
                importance=0.9,
                confidence=1.0,
                retention_policy=RetentionPolicy.LONG_TERM,
                scope=MemoryScope.USER,
                status=MemoryStatus.ACTIVE,
                provenance=Provenance.SYSTEM_OBSERVED,
                tags={"project", state.project_type, state.name.lower()},
                relations={"project_id": [state.project_id]},
                metadata={"progress_pct": state.task_graph.progress_pct()},
            )
            self.memory_2_0.remember(record)
            return True
        except Exception as exc:
            log.warning("Failed to write project memory: %s", exc)
            return False

    def load_project_memory(self, project_name: str) -> Optional[Dict[str, Any]]:
        if not self.memory_2_0:
            return None
        try:
            results = self.memory_2_0.get_relevant_memories(
                query=f"project {project_name}", limit=5,
            )
            for rec in results:
                if project_name.lower() in (rec.summary or "").lower():
                    return json.loads(rec.content)
            return None
        except Exception:
            return None

    def _update_milestone_status(self, state: ProjectState) -> None:
        for ms in state.task_graph.milestones.values():
            if ms.status == MilestoneStatus.COMPLETED:
                continue
            tasks_in_ms = [
                state.task_graph.get_task(tid) for tid in ms.task_ids
                if state.task_graph.get_task(tid) is not None
            ]
            if not tasks_in_ms:
                continue
            all_done = all(t.status == TaskStatus.COMPLETED for t in tasks_in_ms)
            any_active = any(t.status == TaskStatus.ACTIVE for t in tasks_in_ms)
            any_failed = any(t.status == TaskStatus.FAILED for t in tasks_in_ms)
            if all_done:
                ms.status = MilestoneStatus.COMPLETED
                if ms.id not in state.completed_milestones:
                    state.completed_milestones.append(ms.id)
            elif any_failed:
                ms.status = MilestoneStatus.FAILED
            elif any_active:
                ms.status = MilestoneStatus.IN_PROGRESS

    def cleanup_temp_projects(self, max_age_hours: float = 24.0) -> int:
        cutoff = time.time() - max_age_hours * 3600
        to_remove = []
        for pid, state in self._active_projects.items():
            if state.updated_at < cutoff and state.task_graph.all_finished():
                to_remove.append(pid)
        for pid in to_remove:
            self.remove_project(pid)
        return len(to_remove)
