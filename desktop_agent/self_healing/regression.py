"""Regression Intelligence + Behavioral Diff for MYRAA self-healing."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RegressionStatus(Enum):
    """Classification of regression severity."""

    NO_REGRESSION = "no_regression"
    MINOR_REGRESSION = "minor_regression"
    MAJOR_REGRESSION = "major_regression"
    BEHAVIOR_CHANGE = "behavior_change"
    UNKNOWN = "unknown"


@dataclass
class BeforeAfter:
    """Comparison of a single metric before and after a change."""

    metric_name: str
    before_value: float
    after_value: float
    unit: str
    change_pct: float
    status: RegressionStatus


@dataclass
class BehavioralDiff:
    """Comparison of behavioral output before and after a change."""

    goal: str
    old_behavior: str
    new_behavior: str
    identical: bool
    latency_change_ms: float
    regression_status: RegressionStatus


class RegressionAnalyzer:
    """Thread-safe singleton that analyses metric and behavioral regressions."""

    _instance: RegressionAnalyzer | None = None
    _lock_cls = threading.Lock()

    def __new__(cls) -> RegressionAnalyzer:
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._init_lock = threading.Lock()
                    inst._history: list[BeforeAfter] = []
                    inst._behavioral_history: list[BehavioralDiff] = []
                    cls._instance = inst
        return cls._instance

    def compare_results(
        self, before: dict[str, float], after: dict[str, float], unit: str = ""
    ) -> list[BeforeAfter]:
        """Compare metric dictionaries side-by-side and return a diff list."""
        results: list[BeforeAfter] = []
        with self._init_lock:
            for key in set(before) | set(after):
                bv = before.get(key)
                av = after.get(key)
                if bv is None or av is None:
                    logger.debug("Skipping metric %s — missing from one side", key)
                    continue
                change_pct = ((av - bv) / abs(bv) * 100) if bv != 0 else 0.0
                status = self._classify_change(bv, av)
                ba = BeforeAfter(
                    metric_name=key,
                    before_value=bv,
                    after_value=av,
                    unit=unit,
                    change_pct=change_pct,
                    status=status,
                )
                results.append(ba)
                self._history.append(ba)
        return results

    def detect_regression(self, before_after: list[BeforeAfter]) -> RegressionStatus:
        """Return the worst regression status found across all compared metrics."""
        if not before_after:
            return RegressionStatus.UNKNOWN
        worst = RegressionStatus.NO_REGRESSION
        order = {
            RegressionStatus.NO_REGRESSION: 0,
            RegressionStatus.MINOR_REGRESSION: 1,
            RegressionStatus.MAJOR_REGRESSION: 2,
            RegressionStatus.BEHAVIOR_CHANGE: 3,
            RegressionStatus.UNKNOWN: -1,
        }
        for ba in before_after:
            if order.get(ba.status, 0) > order.get(worst, 0):
                worst = ba.status
        return worst

    def behavioral_diff(
        self,
        goal: str,
        old_response: str,
        new_response: str,
        latency_before_ms: float = 0.0,
        latency_after_ms: float = 0.0,
    ) -> BehavioralDiff:
        """Produce a behavioral diff record for two responses to the same goal."""
        identical = old_response.strip() == new_response.strip()
        latency_delta = latency_after_ms - latency_before_ms

        if identical:
            status = RegressionStatus.NO_REGRESSION
        elif self._classify_change_text(old_response, new_response):
            status = RegressionStatus.BEHAVIOR_CHANGE
        else:
            status = RegressionStatus.MINOR_REGRESSION

        diff = BehavioralDiff(
            goal=goal,
            old_behavior=old_response,
            new_behavior=new_response,
            identical=identical,
            latency_change_ms=latency_delta,
            regression_status=status,
        )
        with self._init_lock:
            self._behavioral_history.append(diff)
        return diff

    def check_test_results(
        self,
        before_pass: int,
        before_fail: int,
        after_pass: int,
        after_fail: int,
    ) -> tuple[bool, str]:
        """Check whether test results indicate a regression.

        Returns ``(ok, reason)`` where *ok* is ``True`` when no regression is
        detected.
        """
        if after_fail < before_fail:
            return True, "Failures decreased — improvement"
        if after_fail == before_fail and after_pass >= before_pass:
            return True, "Stable — no regression detected"
        if after_fail > before_fail and after_pass < before_pass:
            return False, (
                f"MAJOR: failures {before_fail} -> {after_fail}, "
                f"passes {before_pass} -> {after_pass}"
            )
        if after_fail > before_fail:
            return False, (
                f"MINOR: failures increased {before_fail} -> {after_fail}"
            )
        return True, "No significant change"

    def check_latency(
        self,
        before_ms: float,
        after_ms: float,
        threshold_pct: float = 20.0,
    ) -> BeforeAfter:
        """Compare two latency values and flag regressions above *threshold_pct*."""
        change_pct = (
            ((after_ms - before_ms) / before_ms * 100) if before_ms != 0 else 0.0
        )
        if change_pct > 50:
            status = RegressionStatus.MAJOR_REGRESSION
        elif change_pct > threshold_pct:
            status = RegressionStatus.MINOR_REGRESSION
        else:
            status = RegressionStatus.NO_REGRESSION

        ba = BeforeAfter(
            metric_name="latency",
            before_value=before_ms,
            after_value=after_ms,
            unit="ms",
            change_pct=change_pct,
            status=status,
        )
        with self._init_lock:
            self._history.append(ba)
        return ba

    def check_resource_usage(
        self,
        before: dict[str, float],
        after: dict[str, float],
    ) -> list[BeforeAfter]:
        """Compare resource-usage snapshots (memory_mb, cpu_pct, threads, etc.)."""
        return self.compare_results(before, after, unit="resource")

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        with cls._lock_cls:
            cls._instance = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_change(before: float, after: float) -> RegressionStatus:
        """Return a regression status based on the ratio after/before."""
        if before == 0:
            return (
                RegressionStatus.NO_REGRESSION
                if after == 0
                else RegressionStatus.MAJOR_REGRESSION
            )
        ratio = after / before
        if ratio <= 1.0:
            return RegressionStatus.NO_REGRESSION
        if ratio >= 1.5:
            return RegressionStatus.MAJOR_REGRESSION
        if ratio >= 1.2:
            return RegressionStatus.MINOR_REGRESSION
        return RegressionStatus.NO_REGRESSION

    @staticmethod
    def _classify_change_text(old: str, new: str) -> bool:
        """Return ``True`` if the textual responses differ in a meaningful way."""
        return old.strip() != new.strip()
