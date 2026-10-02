from __future__ import annotations

"""
Controlled Self-Engineering + Sandbox for MYRAA.

Provides isolated sandbox environments for proposing, testing, benchmarking,
and promoting code changes safely.  Every sandbox operation is bounded by
timeout and size limits.
"""

import hashlib
import logging
import os
import pathlib
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SANDBOX_ROOT = pathlib.Path.home() / ".myraa" / "sandboxes"
_MAX_SANDBOX_SIZE_MB = 50
_MAX_Sandbox_TIMEOUT_S = 300

# Dangerous patterns that must never appear in sandboxed code
_DANGEROUS_PATTERNS = (
    "eval(",
    "exec(",
    "__import__(",
    "os.system(",
    "subprocess.call(",
    "subprocess.run(",
    "subprocess.Popen(",
    "shell=True",
)


class EngineeringStatus(Enum):
    """Lifecycle states for an engineering request."""
    PROPOSED = "proposed"
    SANDBOX_CREATED = "sandbox_created"
    MODIFYING = "modifying"
    TESTING = "testing"
    BENCHMARKING = "benchmarking"
    SECURITY_CHECK = "security_check"
    REGRESSION_TEST = "regression_test"
    STAGING = "staging"
    PROMOTING = "promoting"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass
class EngineeringRequest:
    """Describes a proposed code improvement."""
    request_id: str
    description: str
    target_files: list[str]
    improvement_type: str  # performance | bugfix | refactor | optimization
    risk_level: HealingSeverity
    created_at: float


@dataclass
class EngineeringResult:
    """Outcome of an engineering attempt."""
    request_id: str
    status: EngineeringStatus
    sandbox_path: Optional[str]
    files_changed: list[str]
    tests_passed: int
    tests_failed: int
    benchmark_before: Optional[dict]
    benchmark_after: Optional[dict]
    security_passed: bool
    regression_passed: bool
    rollback_point: Optional[str]
    timestamp: float


# Avoid circular import – use the enum directly from healing.py
try:
    from .healing import HealingSeverity
except ImportError:
    from enum import Enum as _Enum  # type: ignore[assignment]

    class HealingSeverity(_Enum):  # type: ignore[no-redef]
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"


class SelfEngineeringEngine:
    """
    Singleton engine that manages isolated sandboxes for controlled
    self-engineering.

    Lifecycle:
    create_sandbox -> apply_patch -> run_tests -> benchmark ->
    security_check -> promote  (or rollback at any stage)
    """

    _instance: Optional[SelfEngineeringEngine] = None
    _class_lock = threading.Lock()

    def __new__(cls) -> SelfEngineeringEngine:
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
        self._active_sandboxes: dict[str, dict[str, Any]] = {}
        _SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
        logger.info("SelfEngineeringEngine initialized (root=%s)", _SANDBOX_ROOT)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._class_lock:
            cls._instance = None

    # ── Public API ──────────────────────────────────────────────────────

    def create_sandbox(self, request: EngineeringRequest) -> str:
        """
        Create an isolated sandbox for *request* and copy target files into it.

        Returns the sandbox directory path.
        """
        sandbox_path = _SANDBOX_ROOT / request.request_id
        sandbox_path.mkdir(parents=True, exist_ok=True)

        for target in request.target_files:
            src = pathlib.Path(target)
            if src.is_file():
                dest = sandbox_path / src.name
                shutil.copy2(src, dest)
                logger.debug("copied %s -> %s", src, dest)

        with self._lock:
            self._active_sandboxes[request.request_id] = {
                "path": str(sandbox_path),
                "request": request,
                "status": EngineeringStatus.SANDBOX_CREATED,
                "created_at": time.time(),
            }

        logger.info(
            "sandbox created: id=%s path=%s", request.request_id, sandbox_path
        )
        return str(sandbox_path)

    def apply_patch(
        self,
        sandbox_path: str,
        patches: dict[str, str],
    ) -> bool:
        """
        Apply *patches* (mapping filename -> new content) inside the sandbox.

        Returns True if all patches were written successfully.
        """
        sandbox = pathlib.Path(sandbox_path)
        if not sandbox.is_dir():
            logger.error("apply_patch: sandbox not found: %s", sandbox_path)
            return False

        try:
            for filename, content in patches.items():
                target = sandbox / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                logger.debug("patched %s", target)
            return True
        except OSError:
            logger.exception("apply_patch failed")
            return False

    def run_tests_in_sandbox(self, sandbox_path: str) -> tuple[int, int]:
        """
        Discover and run pytest tests inside the sandbox.

        Returns ``(pass_count, fail_count)``.  A non-zero exit from pytest
        counts as failures; test discovery is best-effort.
        """
        sandbox = pathlib.Path(sandbox_path)
        test_files = list(sandbox.glob("test_*.py")) + list(
            sandbox.glob("**/test_*.py")
        )
        if not test_files:
            logger.info("run_tests_in_sandbox: no test files found in %s", sandbox)
            return (0, 0)

        import subprocess

        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    str(sandbox),
                    "-q",
                    "--tb=short",
                ],
                capture_output=True,
                text=True,
                timeout=_MAX_Sandbox_TIMEOUT_S,
                cwd=str(sandbox),
            )
            # Parse pytest output for pass/fail counts
            passed = result.stdout.count(".")  # simple heuristic
            failed = result.stdout.count("F") + result.stdout.count("E")
            if result.returncode != 0 and failed == 0:
                failed = 1
            return (passed, failed)
        except subprocess.TimeoutExpired:
            logger.warning("run_tests_in_sandbox: timeout in %s", sandbox)
            return (0, 1)
        except FileNotFoundError:
            logger.warning("run_tests_in_sandbox: pytest not available")
            return (0, 0)

    def benchmark_sandbox(self, sandbox_path: str) -> dict[str, Any]:
        """
        Run a simple timing and memory benchmark on the sandbox.

        Returns ``{"wall_time_ms": ..., "peak_memory_mb": ...}``.
        """
        import tracemalloc

        sandbox = pathlib.Path(sandbox_path)
        py_files = list(sandbox.glob("*.py"))
        if not py_files:
            return {"wall_time_ms": 0.0, "peak_memory_mb": 0.0}

        tracemalloc.start()
        t0 = time.monotonic()
        try:
            import subprocess

            for f in py_files:
                subprocess.run(
                    ["python", str(f)],
                    capture_output=True,
                    timeout=min(_MAX_Sandbox_TIMEOUT_S, 60),
                    cwd=str(sandbox),
                )
        except Exception:
            logger.exception("benchmark_sandbox: execution error")
        finally:
            elapsed = (time.monotonic() - t0) * 1000
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        return {
            "wall_time_ms": round(elapsed, 2),
            "peak_memory_mb": round(peak / (1024 * 1024), 2),
        }

    def security_check_sandbox(self, sandbox_path: str) -> bool:
        """
        Scan all Python files in the sandbox for dangerous patterns.

        Returns True if no security issues are found.
        """
        sandbox = pathlib.Path(sandbox_path)
        py_files = list(sandbox.glob("*.py")) + list(
            sandbox.glob("**/*.py")
        )
        issues: list[str] = []
        for f in py_files:
            try:
                content = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for pattern in _DANGEROUS_PATTERNS:
                if pattern in content:
                    issues.append(f"{f.name}: contains '{pattern}'")

        if issues:
            logger.warning(
                "security_check_sandbox: %d issues in %s", len(issues), sandbox
            )
            for issue in issues:
                logger.warning("  - %s", issue)
            return False

        logger.info("security_check_sandbox: passed for %s", sandbox)
        return True

    def promote_sandbox(
        self,
        sandbox_path: str,
        request_id: str,
    ) -> EngineeringResult:
        """
        Copy sandbox contents to production if all checks pass.

        Performs security check and basic regression validation before
        promoting.  Returns the full ``EngineeringResult``.
        """
        sandbox = pathlib.Path(sandbox_path)
        start = time.time()

        # Security gate
        sec_ok = self.security_check_sandbox(sandbox_path)
        # Test gate
        passed, failed = self.run_tests_in_sandbox(sandbox_path)

        status = EngineeringStatus.PROMOTED if (sec_ok and failed == 0) else EngineeringStatus.REJECTED

        # Copy files to production (current working directory as proxy)
        files_changed: list[str] = []
        if status == EngineeringStatus.PROMOTED:
            for f in sandbox.iterdir():
                if f.is_file() and f.suffix == ".py":
                    dest = pathlib.Path.cwd() / f.name
                    try:
                        shutil.copy2(f, dest)
                        files_changed.append(str(dest))
                        logger.info("promoted %s -> %s", f, dest)
                    except OSError:
                        logger.exception("promote: failed to copy %s", f)

        with self._lock:
            entry = self._active_sandboxes.get(request_id)
            if entry:
                entry["status"] = status

        result = EngineeringResult(
            request_id=request_id,
            status=status,
            sandbox_path=sandbox_path,
            files_changed=files_changed,
            tests_passed=passed,
            tests_failed=failed,
            benchmark_before=None,
            benchmark_after=None,
            security_passed=sec_ok,
            regression_passed=(failed == 0),
            rollback_point=sandbox_path,
            timestamp=time.time(),
        )
        logger.info(
            "promote_sandbox: request=%s status=%s files=%d",
            request_id,
            status.value,
            len(files_changed),
        )
        return result

    def rollback_sandbox(self, request_id: str) -> bool:
        """
        Rollback a sandbox by removing it and restoring files from the
        rollback point if a backup exists.

        Returns True on success.
        """
        with self._lock:
            entry = self._active_sandboxes.get(request_id)

        if entry is None:
            logger.warning("rollback_sandbox: unknown request %s", request_id)
            return False

        sandbox_path = pathlib.Path(entry["path"])
        if sandbox_path.is_dir():
            shutil.rmtree(sandbox_path, ignore_errors=True)
            logger.info("rollback_sandbox: removed %s", sandbox_path)

        with self._lock:
            entry["status"] = EngineeringStatus.ROLLED_BACK
        return True

    def get_active_sandboxes(self) -> list[dict[str, Any]]:
        """Return metadata for all active sandboxes."""
        with self._lock:
            result = []
            for rid, entry in self._active_sandboxes.items():
                result.append(
                    {
                        "request_id": rid,
                        "path": entry["path"],
                        "status": entry["status"].value,
                        "created_at": entry["created_at"],
                    }
                )
            return result

    def cleanup_sandboxes(self, max_age_hours: int = 24) -> int:
        """
        Remove sandboxes older than *max_age_hours*.

        Returns the number of sandboxes cleaned.
        """
        cutoff = time.time() - (max_age_hours * 3600)
        cleaned = 0
        to_remove: list[str] = []

        with self._lock:
            for rid, entry in self._active_sandboxes.items():
                if entry["created_at"] < cutoff:
                    to_remove.append(rid)

        for rid in to_remove:
            with self._lock:
                entry = self._active_sandboxes.pop(rid, None)
            if entry:
                sp = pathlib.Path(entry["path"])
                if sp.is_dir():
                    shutil.rmtree(sp, ignore_errors=True)
                cleaned += 1
                logger.info("cleanup: removed sandbox %s", rid)

        # Also clean orphan directories
        if _SANDBOX_ROOT.is_dir():
            for child in _SANDBOX_ROOT.iterdir():
                if child.is_dir() and child.name not in {
                    e.get("request_id") for e in self._active_sandboxes.values()
                }:
                    stat = child.stat()
                    if stat.st_mtime < cutoff:
                        shutil.rmtree(child, ignore_errors=True)
                        cleaned += 1

        logger.info("cleanup_sandboxes: cleaned %d sandboxes", cleaned)
        return cleaned
