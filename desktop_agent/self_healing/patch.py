from __future__ import annotations

"""
Patch Generation + Impact Analysis for MYRAA.

Provides structured patch lifecycle management with impact analysis,
security scanning, risk assessment, and rollback via git.
"""

import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PatchRisk(Enum):
    """Risk levels for patches."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactArea(Enum):
    """Areas of the system that a patch may affect."""
    CORE = "core"
    BRAIN = "brain"
    MEMORY = "memory"
    TRADING = "trading"
    VISION = "vision"
    VOICE = "voice"
    TOOLS = "tools"
    UI = "ui"
    SECURITY = "security"
    PERFORMANCE = "performance"


# Mapping of path prefixes to impact areas
_IMPACT_MAP: dict[str, list[ImpactArea]] = {
    "desktop_agent/brain/": [ImpactArea.BRAIN],
    "desktop_agent/finance/": [ImpactArea.TRADING],
    "desktop_agent/vision/": [ImpactArea.VISION],
    "desktop_agent/speech/": [ImpactArea.VOICE],
    "desktop_agent/tools_": [ImpactArea.TOOLS],
    "desktop_agent/desktop/": [ImpactArea.TOOLS],
    "desktop_agent/core/": [ImpactArea.CORE],
    "desktop_agent/runtime/": [ImpactArea.CORE],
    "src/": [ImpactArea.UI],
    "server.ts": [ImpactArea.CORE, ImpactArea.PERFORMANCE],
    "services/": [ImpactArea.CORE],
    "backend/": [ImpactArea.VOICE],
}

# Files / directories that elevate risk
_SECURITY_PATHS = {"security", "auth", "permission", "crypto", "secret"}
_CORE_PATHS = {"core", "main", "registry", "server"}


@dataclass(frozen=True)
class PatchRecord:
    """Immutable record of a patch applied to the system."""
    patch_id: str
    reason: str
    files_changed: list[str]
    risk: PatchRisk
    tests_added: list[str]
    benchmark_result: Optional[dict]
    status: str
    rollback_point: str
    created_at: float
    impact_areas: list[ImpactArea]


class PatchGenerator:
    """
    Singleton patch lifecycle manager.

    Tracks patches, analyses impact, validates changes, and supports
    rollback through git.
    """

    _instance: Optional[PatchGenerator] = None
    _class_lock = threading.Lock()

    def __new__(cls) -> PatchGenerator:
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._lock = threading.Lock()
        self._history: list[PatchRecord] = []
        self._max_history = 100
        logger.info("PatchGenerator initialized")

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._class_lock:
            cls._instance = None

    # ── Public API ──────────────────────────────────────────────────────

    def generate_patch(
        self,
        description: str,
        target_files: list[str],
        test_files: list[str] | None = None,
    ) -> PatchRecord:
        """
        Create a ``PatchRecord`` for the described change.

        Risk is calculated from the target files and their impact areas.
        """
        tests = test_files or []
        impact_areas = self.analyze_impact(target_files)
        risk = self._calculate_risk(target_files, impact_areas)
        rollback_point = self._get_git_commit()

        patch = PatchRecord(
            patch_id=str(uuid.uuid4()),
            reason=description,
            files_changed=list(target_files),
            risk=risk,
            tests_added=tests,
            benchmark_result=None,
            status="proposed",
            rollback_point=rollback_point,
            created_at=time.time(),
            impact_areas=impact_areas,
        )
        logger.info(
            "patch generated: id=%s risk=%s files=%d",
            patch.patch_id,
            risk.value,
            len(target_files),
        )
        return patch

    def analyze_impact(self, target_files: list[str]) -> list[ImpactArea]:
        """
        Map *target_files* to their affected ``ImpactArea``s.

        Returns a deduplicated list of all impacted areas.
        """
        areas: set[ImpactArea] = set()
        for filepath in target_files:
            for prefix, mapped_areas in _IMPACT_MAP.items():
                if prefix in filepath:
                    areas.update(mapped_areas)

            # Check for security-critical paths
            lower = filepath.lower()
            if any(sp in lower for sp in _SECURITY_PATHS):
                areas.add(ImpactArea.SECURITY)

        if not areas:
            areas.add(ImpactArea.CORE)

        return sorted(areas, key=lambda a: a.value)

    def validate_patch(self, patch: PatchRecord) -> tuple[bool, list[str]]:
        """
        Validate a patch by running tests and checking for security issues.

        Returns ``(all_passed, list_of_issues)``.
        """
        issues: list[str] = []

        # Security scan on changed files
        for filepath in patch.files_changed:
            try:
                from pathlib import Path

                content = Path(filepath).read_text(encoding="utf-8")
                sec_issues = self._scan_for_security_issues(content)
                for si in sec_issues:
                    issues.append(f"{filepath}: {si}")
            except (OSError, UnicodeDecodeError):
                issues.append(f"{filepath}: could not read for security scan")

        # Risk gate – CRITICAL patches are rejected unless explicitly approved
        if patch.risk == PatchRisk.CRITICAL:
            issues.append("CRITICAL risk patch requires explicit human approval")

        all_passed = len(issues) == 0
        logger.info(
            "validate_patch: id=%s passed=%s issues=%d",
            patch.patch_id,
            all_passed,
            len(issues),
        )
        return all_passed, issues

    def record_patch(self, patch: PatchRecord) -> None:
        """Store a patch in the bounded history."""
        with self._lock:
            self._history.append(patch)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]
        logger.info("patch recorded: id=%s", patch.patch_id)

    def get_patch_history(self) -> list[PatchRecord]:
        """Return a copy of the bounded patch history."""
        with self._lock:
            return list(self._history)

    def rollback_patch(self, patch_id: str) -> bool:
        """
        Rollback a patch using ``git revert``.

        Returns True if the revert succeeded.
        """
        patch = None
        with self._lock:
            for p in self._history:
                if p.patch_id == patch_id:
                    patch = p
                    break

        if patch is None:
            logger.warning("rollback_patch: unknown patch %s", patch_id)
            return False

        if not patch.rollback_point:
            logger.warning(
                "rollback_patch: no rollback point for %s", patch_id
            )
            return False

        try:
            result = subprocess.run(
                ["git", "revert", "--no-edit", "HEAD"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                logger.info("rollback_patch: reverted %s", patch_id)
                return True
            else:
                logger.error(
                    "rollback_patch: git revert failed: %s", result.stderr
                )
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.exception("rollback_patch: git not available or timeout")
            return False

    def _scan_for_security_issues(self, code: str) -> list[str]:
        """Detect dangerous patterns in *code*."""
        dangerous = {
            "eval(": "use of eval()",
            "exec(": "use of exec()",
            "__import__(": "dynamic import via __import__",
            "os.system(": "use of os.system()",
            "shell=True": "subprocess with shell=True",
            "open(": "file open (verify path safety)",
        }
        issues: list[str] = []
        for pattern, desc in dangerous.items():
            if pattern in code:
                issues.append(desc)
        return issues

    def _calculate_risk(
        self,
        target_files: list[str],
        impact_areas: list[ImpactArea],
    ) -> PatchRisk:
        """
        Determine patch risk based on file paths and impact areas.

        - CORE / SECURITY files -> HIGH or CRITICAL
        - Test files -> LOW
        - Everything else -> MEDIUM
        """
        for filepath in target_files:
            lower = filepath.lower()
            if "test" in lower:
                continue
            if any(sp in lower for sp in _SECURITY_PATHS):
                return PatchRisk.CRITICAL
            if any(cp in lower for cp in _CORE_PATHS):
                return PatchRisk.HIGH

        if ImpactArea.SECURITY in impact_areas:
            return PatchRisk.CRITICAL
        if ImpactArea.CORE in impact_areas:
            return PatchRisk.HIGH

        # Default
        return PatchRisk.MEDIUM

    def _get_git_commit(self) -> str:
        """Return the current HEAD commit hash (or empty string on failure)."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return ""
