"""Workflow memory: learn and replay multi-step actions across any app."""

from __future__ import annotations

import time
import json
import threading
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class WorkflowStep:
    action: str
    target: str
    args: dict = field(default_factory=dict)
    expected_outcome: str = ""
    timestamp: float = 0.0
    success: bool = True
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class Workflow:
    workflow_id: str
    name: str
    app: str
    steps: list[WorkflowStep] = field(default_factory=list)
    created_at: float = 0.0
    last_run: float = 0.0
    run_count: int = 0
    success_count: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.run_count if self.run_count > 0 else 0.0

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict:
        return {
            "id": self.workflow_id, "name": self.name, "app": self.app,
            "steps": len(self.steps), "runs": self.run_count,
            "success_rate": f"{self.success_rate:.0%}",
        }


class WorkflowMemory:
    """Learn, store, and replay multi-step workflows."""

    def __init__(self, storage_path: Optional[Path] = None, max_workflows: int = 200):
        self._storage_path = storage_path
        self._max_workflows = max_workflows
        self._workflows: dict[str, Workflow] = {}
        self._lock = threading.Lock()
        self._current: Optional[Workflow] = None
        self._current_steps: list[WorkflowStep] = []
        self._id_counter = 0

    def start_recording(self, name: str, app: str, tags: Optional[list[str]] = None) -> str:
        with self._lock:
            self._id_counter += 1
            wf_id = f"wf_{self._id_counter}_{int(time.time() * 1000)}"
            self._current = Workflow(
                workflow_id=wf_id, name=name, app=app,
                created_at=time.time(), tags=tags or [],
            )
            self._current_steps = []
            return wf_id

    def record_step(self, action: str, target: str, args: Optional[dict] = None,
                    expected_outcome: str = "", success: bool = True,
                    error: str = "", duration_ms: float = 0.0):
        with self._lock:
            self._current_steps.append(WorkflowStep(
                action=action, target=target, args=args or {},
                expected_outcome=expected_outcome,
                timestamp=time.time(), success=success,
                error=error, duration_ms=duration_ms,
            ))

    def stop_recording(self) -> Optional[Workflow]:
        with self._lock:
            if not self._current:
                return None
            self._current.steps = list(self._current_steps)
            self._workflows[self._current.workflow_id] = self._current
            wf = self._current
            self._current = None
            self._current_steps = []
            self._enforce_limit()
            return wf

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self._workflows.get(workflow_id)

    def find_by_name(self, name: str) -> list[Workflow]:
        return [wf for wf in self._workflows.values()
                if name.lower() in wf.name.lower()]

    def find_by_app(self, app: str) -> list[Workflow]:
        return [wf for wf in self._workflows.values()
                if app.lower() in wf.app.lower()]

    def record_run(self, workflow_id: str, success: bool):
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf:
                wf.run_count += 1
                if success:
                    wf.success_count += 1
                wf.last_run = time.time()

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._lock:
            return self._workflows.pop(workflow_id, None) is not None

    def list_all(self) -> list[Workflow]:
        with self._lock:
            return list(self._workflows.values())

    def popular_workflows(self, n: int = 10) -> list[Workflow]:
        with self._lock:
            return sorted(self._workflows.values(),
                          key=lambda w: w.run_count, reverse=True)[:n]

    def _enforce_limit(self):
        if len(self._workflows) > self._max_workflows:
            sorted_wfs = sorted(self._workflows.values(),
                                key=lambda w: w.last_run or w.created_at)
            for wf in sorted_wfs[:len(self._workflows) - self._max_workflows]:
                self._workflows.pop(wf.workflow_id, None)

    def save(self):
        if not self._storage_path:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for wf in self._workflows.values():
            data.append({
                "id": wf.workflow_id, "name": wf.name, "app": wf.app,
                "tags": wf.tags, "run_count": wf.run_count,
                "success_count": wf.success_count,
                "steps": [{"action": s.action, "target": s.target, "args": s.args,
                           "success": s.success} for s in wf.steps],
            })
        self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self):
        if not self._storage_path or not self._storage_path.exists():
            return
        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            for item in data:
                steps = [WorkflowStep(**s) for s in item.get("steps", [])]
                wf = Workflow(
                    workflow_id=item["id"], name=item["name"], app=item["app"],
                    steps=steps, tags=item.get("tags", []),
                    run_count=item.get("run_count", 0),
                    success_count=item.get("success_count", 0),
                )
                self._workflows[wf.workflow_id] = wf
        except Exception:
            pass

    def clear(self):
        with self._lock:
            self._workflows.clear()
            self._current = None
            self._current_steps.clear()
