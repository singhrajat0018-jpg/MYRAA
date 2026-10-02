"""
MYRAA Brain
Tool Outcome Verification (P0-F5)

Replaces the always-true VerificationManager stub. MYRAA must verify real
outcomes - a tool reporting "success" is a claim, not proof. After a tool
executes, the result is checked against the real world (filesystem state,
etc.) using the existing per-tool ExecutionVerifier checks, and an outcome
is reported:

    VERIFIED            deterministic check passed
    PARTIALLY_VERIFIED  independent evidence exists, but not a full proof
    UNVERIFIED          no deterministic check is available for this tool
    FAILED              tool claimed success but reality disagrees (or no result)

Verification is advisory for UNVERIFIED tools and authoritative for tools
with a deterministic check. It never executes tools itself.
"""

from __future__ import annotations

import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationOutcome(str, Enum):
    """Outcome classes for tool-outcome verification (P0-F5)."""

    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


@dataclass
class VerificationEvidence:
    """One piece of evidence gathered during verification."""

    check: str
    passed: Optional[bool]
    detail: str = ""


@dataclass
class ToolVerificationResult:
    """Result of verifying a single tool execution."""

    tool: str
    outcome: VerificationOutcome
    message: str
    evidence: List[VerificationEvidence] = field(default_factory=list)
    verification_time: float = 0.0

    @property
    def is_verified(self) -> bool:
        return self.outcome in (
            VerificationOutcome.VERIFIED,
            VerificationOutcome.PARTIALLY_VERIFIED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "outcome": self.outcome.value,
            "message": self.message,
            "verified": self.is_verified,
            "evidence": [
                {"check": e.check, "passed": e.passed, "detail": e.detail}
                for e in self.evidence
            ],
            "verification_time_ms": round(self.verification_time * 1000, 3),
        }


# Shared worker pool for timeout-guarded verification. Small (2 workers): the
# checks are quick filesystem/app-state probes, never heavy compute.
_verification_lock = None
_VERIFICATION_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _executor() -> ThreadPoolExecutor:
    global _VERIFICATION_EXECUTOR, _verification_lock
    if _verification_lock is None:
        _verification_lock = threading.Lock()
    if _VERIFICATION_EXECUTOR is None:
        with _verification_lock:
            if _VERIFICATION_EXECUTOR is None:
                _VERIFICATION_EXECUTOR = ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix="myraa_verify"
                )
                # Mark workers as daemon so they don't block process exit
                for t in list(_VERIFICATION_EXECUTOR._threads):
                    t.daemon = True
    return _VERIFICATION_EXECUTOR


def shutdown_verification_executor(wait: bool = False):
    """Shut down the verification executor. Called during application shutdown."""
    global _VERIFICATION_EXECUTOR
    if _VERIFICATION_EXECUTOR is not None:
        try:
            _VERIFICATION_EXECUTOR.shutdown(wait=wait, cancel_futures=True)
        except TypeError:
            _VERIFICATION_EXECUTOR.shutdown(wait=wait)
        _VERIFICATION_EXECUTOR = None


class VerificationManager:
    """
    Verifies real tool outcomes. Never treats "tool returned success" as proof.

    REUSE: per-tool deterministic checks are delegated to the existing
    ExecutionVerifier (desktop_agent/brain/executive/execution_verifier.py).
    No second verifier registry is introduced.
    """

    def __init__(
        self,
        verifier: Any = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        from .executive.execution_verifier import ExecutionVerifier

        self._verifier = verifier if verifier is not None else ExecutionVerifier()
        self.timeout_seconds = timeout_seconds

    # =======================================================
    # Public API
    # =======================================================

    def verify(
        self,
        result: Any,
        tool: str = "",
        args: Optional[Dict[str, Any]] = None,
    ) -> ToolVerificationResult:
        """
        Verify a tool execution outcome against the real world.

        Args:
            result: the value returned by the tool handler (not the wrapper).
            tool: the registered tool name (e.g. "createFile").
            args: the validated arguments passed to the tool.

        Returns:
            ToolVerificationResult with an outcome class and evidence.
        """
        started = time.perf_counter()
        args = args or {}

        if result is None:
            return self._build(
                tool,
                VerificationOutcome.FAILED,
                "Execution returned no result.",
                [
                    VerificationEvidence(
                        "result_present",
                        False,
                        "Tool handler returned None.",
                    )
                ],
                started,
            )

        method = getattr(self._verifier, f"_verify_{tool}", None)

        if method is None:
            # No deterministic check exists. Look for independent evidence in
            # the tool's own output (e.g. a path that really exists on disk).
            evidence = self._partial_evidence(result)
            if evidence and all(e.passed for e in evidence):
                return self._build(
                    tool,
                    VerificationOutcome.PARTIALLY_VERIFIED,
                    "Independent evidence of success found; no deterministic check exists.",
                    evidence,
                    started,
                )
            return self._build(
                tool,
                VerificationOutcome.UNVERIFIED,
                "No deterministic check exists for this tool; success is a claim, not proof.",
                [
                    VerificationEvidence(
                        "deterministic_check",
                        False,
                        f"No _verify_{tool} handler in ExecutionVerifier.",
                    )
                ],
                started,
            )

        try:
            check = _executor().submit(
                lambda: method(args, result)
            ).result(timeout=self.timeout_seconds)
        except FutureTimeout:
            return self._build(
                tool,
                VerificationOutcome.UNVERIFIED,
                f"Verification timed out after {self.timeout_seconds}s.",
                [
                    VerificationEvidence(
                        "deterministic_check",
                        False,
                        "Timed out; outcome could not be confirmed.",
                    )
                ],
                started,
            )
        except Exception as exc:  # noqa: BLE001 - a broken verifier must not crash execution
            return self._build(
                tool,
                VerificationOutcome.UNVERIFIED,
                f"Verification raised an error: {exc}",
                [
                    VerificationEvidence(
                        "deterministic_check",
                        False,
                        f"Exception: {exc}",
                    )
                ],
                started,
            )

        outcome = (
            VerificationOutcome.VERIFIED
            if check.success
            else VerificationOutcome.FAILED
        )
        message = check.message or ("Verified." if check.success else "Verification failed.")

        return self._build(
            tool,
            outcome,
            message,
            [
                VerificationEvidence(
                    "deterministic_check",
                    check.success,
                    message,
                )
            ],
            started,
        )

    # =======================================================
    # Helpers
    # =======================================================

    @staticmethod
    def _partial_evidence(result: Any) -> List[VerificationEvidence]:
        """Independent evidence from the tool's own output, when trustworthy.

        A tool may report a "path" it claims to have created/modified. If that
        path actually exists on disk we treat it as partial (not full) proof.
        """
        if not isinstance(result, dict):
            return []
        path = result.get("path")
        if not path or not isinstance(path, str):
            return []
        import os

        p = os.path.expanduser(os.path.expandvars(path))
        return [
            VerificationEvidence(
                "reported_path_exists",
                os.path.exists(p),
                f"path={p}",
            )
        ]

    def _build(
        self,
        tool: str,
        outcome: VerificationOutcome,
        message: str,
        evidence: List[VerificationEvidence],
        started: float,
    ) -> ToolVerificationResult:
        return ToolVerificationResult(
            tool=tool,
            outcome=outcome,
            message=message,
            evidence=evidence,
            verification_time=time.perf_counter() - started,
        )
