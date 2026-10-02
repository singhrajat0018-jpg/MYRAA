"""Skill — canonical capability descriptor for MYRAA workers.

Every skill declares: id, name, domain, version, capabilities, required_tools,
required_context, permissions, risk_level, input_schema, output_schema,
dependencies, health, status, cost, latency, owner.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class SkillState(str, Enum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    ERROR = "error"
    UPGRADING = "upgrading"
    DEPRECATED = "deprecated"


class SkillDomain(str, Enum):
    CODING = "coding"
    RESEARCH = "research"
    BROWSER = "browser"
    DESKTOP = "desktop"
    VISION = "vision"
    VOICE = "voice"
    TRADING = "trading"
    DOCUMENTS = "documents"
    FILES = "files"
    PROJECTS = "projects"
    MEMORY = "memory"
    WORLD_MODEL = "world_model"
    DATA_ANALYSIS = "data_analysis"
    AUTOMATION = "automation"
    VERIFICATION = "verification"
    DIAGNOSTICS = "diagnostics"
    SELF_HEALING = "self_healing"


class SkillVersion(str, Enum):
    STABLE = "stable"
    CANDIDATE = "candidate"
    CANARY = "canary"
    DEPRECATED = "deprecated"


@dataclass
class SkillHealth:
    """Skill health metrics."""
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    last_error: str = ""
    last_used: float = 0.0
    avg_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.success_count / self.total_calls

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failure_count / self.total_calls

    def record_success(self, latency_ms: float) -> None:
        self.total_calls += 1
        self.success_count += 1
        self.total_latency_ms += latency_ms
        self.avg_latency_ms = self.total_latency_ms / self.total_calls
        self.last_used = time.time()

    def record_failure(self, error: str) -> None:
        self.total_calls += 1
        self.failure_count += 1
        self.last_error = error
        self.last_used = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "last_error": self.last_error,
            "last_used": self.last_used,
        }


@dataclass
class Skill:
    """Canonical skill descriptor.

    Thread-safe: mutations go through update_state / record_success / record_failure.
    """
    id: str
    name: str
    description: str
    domain: SkillDomain
    version: str = "1.0.0"
    version_status: SkillVersion = SkillVersion.STABLE
    capabilities: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    required_context: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    state: SkillState = SkillState.AVAILABLE
    health: SkillHealth = field(default_factory=SkillHealth)
    cost_per_call: float = 0.0
    max_latency_ms: float = 10000.0
    owner: str = "system"
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update_state(self, new_state: SkillState) -> None:
        with self._lock:
            self.state = new_state
            self.updated_at = time.time()

    def record_success(self, latency_ms: float) -> None:
        with self._lock:
            self.health.record_success(latency_ms)
            if self.state == SkillState.ERROR:
                self.state = SkillState.AVAILABLE

    def record_failure(self, error: str) -> None:
        with self._lock:
            self.health.record_failure(error)
            if self.health.failure_rate > 0.5 and self.health.total_calls >= 5:
                self.state = SkillState.DEGRADED

    def can_execute(self) -> bool:
        return self.state in (SkillState.AVAILABLE, SkillState.DEGRADED)

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def has_tool(self, tool: str) -> bool:
        return tool in self.required_tools

    def matches_domain(self, domain: SkillDomain) -> bool:
        return self.domain == domain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain.value,
            "version": self.version,
            "version_status": self.version_status.value,
            "capabilities": self.capabilities,
            "required_tools": self.required_tools,
            "required_context": self.required_context,
            "permissions": self.permissions,
            "risk_level": self.risk_level,
            "dependencies": self.dependencies,
            "state": self.state.value,
            "health": self.health.to_dict(),
            "cost_per_call": self.cost_per_call,
            "max_latency_ms": self.max_latency_ms,
            "owner": self.owner,
            "tags": list(self.tags),
        }

    @classmethod
    def create(
        cls,
        skill_id: str,
        name: str,
        domain: SkillDomain,
        description: str = "",
        capabilities: Optional[List[str]] = None,
        required_tools: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        risk_level: str = "low",
        dependencies: Optional[List[str]] = None,
    ) -> Skill:
        return cls(
            id=skill_id,
            name=name,
            description=description,
            domain=domain,
            capabilities=capabilities or [],
            required_tools=required_tools or [],
            permissions=permissions or [],
            risk_level=risk_level,
            dependencies=dependencies or [],
        )
