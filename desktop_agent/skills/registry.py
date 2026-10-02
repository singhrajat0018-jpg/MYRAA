"""SkillRegistry — canonical registry for MYRAA skills.

Supports: register, unregister, discover, enable, disable, health,
version, permissions, dependencies, capability search.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .skill import Skill, SkillState, SkillDomain, SkillHealth, SkillVersion

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Thread-safe registry of all MYRAA skills.

    Singleton pattern for global access.
    """

    _instance: Optional[SkillRegistry] = None
    _class_lock = threading.Lock()

    def __new__(cls) -> SkillRegistry:
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._skills: Dict[str, Skill] = {}
        self._lock = threading.RLock()
        self._listeners: List[Callable[[str, Skill], None]] = []
        logger.info("SkillRegistry initialised")

    @classmethod
    def reset(cls) -> None:
        with cls._class_lock:
            cls._instance = None

    # ── Registration ──────────────────────────────────────────────────

    def register(self, skill: Skill) -> bool:
        with self._lock:
            if skill.id in self._skills:
                logger.warning("Skill %s already registered, updating", skill.id)
            self._skills[skill.id] = skill
            self._notify("registered", skill)
            logger.info("Registered skill: %s (%s)", skill.name, skill.domain.value)
            return True

    def unregister(self, skill_id: str) -> bool:
        with self._lock:
            skill = self._skills.pop(skill_id, None)
            if skill:
                self._notify("unregistered", skill)
                return True
            return False

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def all(self) -> List[Skill]:
        with self._lock:
            return list(self._skills.values())

    # ── Discovery ─────────────────────────────────────────────────────

    def discover(
        self,
        domain: Optional[SkillDomain] = None,
        capability: Optional[str] = None,
        tool: Optional[str] = None,
        state: Optional[SkillState] = None,
        tags: Optional[Set[str]] = None,
        limit: int = 50,
    ) -> List[Skill]:
        """Discover skills matching criteria."""
        results: List[Skill] = []
        with self._lock:
            for skill in self._skills.values():
                if domain and skill.domain != domain:
                    continue
                if capability and capability not in skill.capabilities:
                    continue
                if tool and tool not in skill.required_tools:
                    continue
                if state and skill.state != state:
                    continue
                if tags and not tags.issubset(skill.tags):
                    continue
                results.append(skill)
                if len(results) >= limit:
                    break
        return results

    def find_by_capability(self, capability: str) -> List[Skill]:
        return self.discover(capability=capability)

    def find_by_domain(self, domain: SkillDomain) -> List[Skill]:
        return self.discover(domain=domain)

    def find_by_tool(self, tool: str) -> List[Skill]:
        return self.discover(tool=tool)

    def find_available(self) -> List[Skill]:
        return self.discover(state=SkillState.AVAILABLE)

    def best_for_task(
        self,
        domain: SkillDomain,
        required_tools: Optional[List[str]] = None,
        required_capabilities: Optional[List[str]] = None,
    ) -> Optional[Skill]:
        """Select best skill for a task based on domain, tools, capabilities, and health."""
        candidates = self.discover(domain=domain, state=SkillState.AVAILABLE)
        if not candidates:
            candidates = self.discover(domain=domain, state=SkillState.DEGRADED)

        if not candidates:
            return None

        # Filter by required tools
        if required_tools:
            candidates = [
                s for s in candidates
                if all(t in s.required_tools for t in required_tools)
            ]

        # Filter by required capabilities
        if required_capabilities:
            candidates = [
                s for s in candidates
                if all(c in s.capabilities for c in required_capabilities)
            ]

        if not candidates:
            return None

        # Sort by: success rate desc, avg latency asc
        candidates.sort(
            key=lambda s: (-s.health.success_rate, s.health.avg_latency_ms)
        )
        return candidates[0]

    # ── State Management ──────────────────────────────────────────────

    def enable(self, skill_id: str) -> bool:
        with self._lock:
            skill = self._skills.get(skill_id)
            if skill:
                skill.update_state(SkillState.AVAILABLE)
                self._notify("enabled", skill)
                return True
            return False

    def disable(self, skill_id: str) -> bool:
        with self._lock:
            skill = self._skills.get(skill_id)
            if skill:
                skill.update_state(SkillState.DISABLED)
                self._notify("disabled", skill)
                return True
            return False

    def degrade(self, skill_id: str, reason: str = "") -> bool:
        with self._lock:
            skill = self._skills.get(skill_id)
            if skill:
                skill.update_state(SkillState.DEGRADED)
                if reason:
                    skill.health.last_error = reason
                self._notify("degraded", skill)
                return True
            return False

    # ── Health ────────────────────────────────────────────────────────

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            skills = list(self._skills.values())
        return {
            "total": len(skills),
            "available": sum(1 for s in skills if s.state == SkillState.AVAILABLE),
            "disabled": sum(1 for s in skills if s.state == SkillState.DISABLED),
            "degraded": sum(1 for s in skills if s.state == SkillState.DEGRADED),
            "error": sum(1 for s in skills if s.state == SkillState.ERROR),
            "skills": {s.id: s.health.to_dict() for s in skills},
            "timestamp": time.time(),
        }

    def record_success(self, skill_id: str, latency_ms: float) -> None:
        skill = self._skills.get(skill_id)
        if skill:
            skill.record_success(latency_ms)

    def record_failure(self, skill_id: str, error: str) -> None:
        skill = self._skills.get(skill_id)
        if skill:
            skill.record_failure(error)

    # ── Version ───────────────────────────────────────────────────────

    def set_version(self, skill_id: str, version: str, status: SkillVersion = SkillVersion.STABLE) -> bool:
        skill = self._skills.get(skill_id)
        if skill:
            skill.version = version
            skill.version_status = status
            skill.updated_at = time.time()
            return True
        return False

    def deprecate(self, skill_id: str) -> bool:
        skill = self._skills.get(skill_id)
        if skill:
            skill.version_status = SkillVersion.DEPRECATED
            skill.update_state(SkillState.DEPRECATED)
            return True
        return False

    # ── Dependencies ──────────────────────────────────────────────────

    def check_dependencies(self, skill_id: str) -> Dict[str, Any]:
        skill = self._skills.get(skill_id)
        if skill is None:
            return {"satisfied": False, "missing": [skill_id]}

        missing = []
        for dep_id in skill.dependencies:
            dep = self._skills.get(dep_id)
            if dep is None or dep.state in (SkillState.DISABLED, SkillState.ERROR):
                missing.append(dep_id)

        return {
            "satisfied": len(missing) == 0,
            "missing": missing,
            "total_deps": len(skill.dependencies),
        }

    # ── Permissions ───────────────────────────────────────────────────

    def skills_for_tools(self, tools: List[str]) -> List[Skill]:
        """Find skills that can use the given tools."""
        tool_set = set(tools)
        return [
            s for s in self._skills.values()
            if tool_set.issubset(set(s.required_tools))
        ]

    # ── Listeners ─────────────────────────────────────────────────────

    def on_change(self, callback: Callable[[str, Skill], None]) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str, skill: Skill) -> None:
        for cb in self._listeners:
            try:
                cb(event, skill)
            except Exception:
                pass

    # ── Stats ─────────────────────────────────────────────────────────

    def count(self) -> Dict[str, int]:
        by_domain: Dict[str, int] = {}
        by_state: Dict[str, int] = {}
        with self._lock:
            for skill in self._skills.values():
                by_domain[skill.domain.value] = by_domain.get(skill.domain.value, 0) + 1
                by_state[skill.state.value] = by_state.get(skill.state.value, 0) + 1
        return {"by_domain": by_domain, "by_state": by_state, "total": len(self._skills)}
