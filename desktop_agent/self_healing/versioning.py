from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MYRAAVersion:
    version_id: str
    git_commit: Optional[str]
    created_at: float
    description: str
    phase: str
    test_results: Dict
    files_changed: List[str]
    rollback_available: bool


class VersionManager:
    """Tracks MYRAA state snapshots (checkpoints) with git integration."""

    _instance: ClassVar[Optional["VersionManager"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> "VersionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._checkpoints: Dict[str, MYRAAVersion] = {}
                    inst._lock_inst = threading.Lock()
                    inst._repo_root: Optional[str] = None
                    cls._instance = inst
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_checkpoint(self, version_id: str, description: str) -> MYRAAVersion:
        """Snapshot current state as a checkpoint."""
        commit = self._get_current_commit()
        phase = self._detect_phase()
        files = self._get_changed_files()
        mv = MYRAAVersion(
            version_id=version_id,
            git_commit=commit,
            created_at=time.time(),
            description=description,
            phase=phase,
            test_results={},
            files_changed=files,
            rollback_available=False,
        )
        with self._lock_inst:
            self._checkpoints[version_id] = mv
        logger.info("Created checkpoint %s (commit=%s)", version_id, commit or "unknown")
        return mv

    def get_checkpoint(self, version_id: str) -> Optional[MYRAAVersion]:
        with self._lock_inst:
            return self._checkpoints.get(version_id)

    def list_checkpoints(self) -> List[MYRAAVersion]:
        with self._lock_inst:
            return list(self._checkpoints.values())

    def get_latest_checkpoint(self) -> Optional[MYRAAVersion]:
        with self._lock_inst:
            if not self._checkpoints:
                return None
            return max(self._checkpoints.values(), key=lambda v: v.created_at)

    def mark_rollback_available(self, version_id: str) -> None:
        with self._lock_inst:
            cp = self._checkpoints.get(version_id)
            if cp is None:
                logger.warning("Checkpoint %s not found for rollback marking", version_id)
                return
            cp.rollback_available = True
        logger.info("Marked checkpoint %s as rollback available", version_id)

    def can_rollback(self, version_id: str) -> bool:
        with self._lock_inst:
            cp = self._checkpoints.get(version_id)
            if cp is None:
                return False
            return cp.rollback_available

    def record_test_results(self, version_id: str, results: Dict) -> None:
        with self._lock_inst:
            cp = self._checkpoints.get(version_id)
            if cp is None:
                logger.warning("Checkpoint %s not found for test results", version_id)
                return
            cp.test_results.update(results)
        logger.info("Recorded test results for checkpoint %s", version_id)

    def get_change_history(self, limit: int = 20) -> List[Dict]:
        """Retrieve recent git log entries."""
        commits = self._run_git_log(limit)
        return commits

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _get_repo_root(self) -> Optional[str]:
        if self._repo_root is not None:
            return self._repo_root
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.getcwd(),
            )
            if result.returncode == 0:
                self._repo_root = result.stdout.strip()
                return self._repo_root
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.debug("Could not find git repo root: %s", exc)
        return None

    def _get_current_commit(self) -> Optional[str]:
        root = self._get_repo_root()
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=root or os.getcwd(),
            )
            if result.returncode == 0:
                return result.stdout.strip()[:12]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return None

    def _get_changed_files(self) -> List[str]:
        root = self._get_repo_root()
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=root or os.getcwd(),
            )
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return []

    def _detect_phase(self) -> str:
        root = self._get_repo_root()
        if root is None:
            return "unknown"
        phase_files = {
            "brain": "brain_development",
            "vision": "vision_development",
            "finance": "finance_development",
            "research": "research_development",
            "telemetry": "telemetry_development",
            "self_healing": "self_healing_development",
        }
        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=root,
            )
            if result.returncode == 0:
                diff_text = result.stdout.lower()
                for keyword, phase in phase_files.items():
                    if keyword in diff_text:
                        return phase
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return "general"

    def _run_git_log(self, limit: int) -> List[Dict]:
        root = self._get_repo_root()
        if root is None:
            return []
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"--max-count={limit}",
                    "--pretty=format:%H|%h|%s|%ai|%an",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=root,
            )
            if result.returncode != 0:
                return []
            entries: List[Dict] = []
            for line in result.stdout.strip().splitlines():
                parts = line.split("|", 4)
                if len(parts) == 5:
                    entries.append({
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "message": parts[2],
                        "date": parts[3],
                        "author": parts[4],
                    })
            return entries
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("git log failed: %s", exc)
            return []
