"""Self-Reflection + Outcome Intelligence for MYRAA self-healing."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

MAX_OUTCOMES = 500
MAX_REFLECTIONS = 200


class TaskOutcome(Enum):
    """Possible result categories for a completed task."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ROLLED_BACK = "rolled_back"
    UNKNOWN = "unknown"


@dataclass
class ReflectionRecord:
    """A single reflection entry produced after task execution."""

    task_id: str
    goal: str
    outcome: TaskOutcome
    efficiency_score: float  # 0.0 – 1.0
    verification_confirmed: bool
    unnecessary_steps: list[str]
    reasoning_quality: str  # correct / acceptable / incorrect
    lessons: list[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class OutcomeRecord:
    """A recorded goal-action-outcome triple with an optional lesson."""

    goal: str
    action: str
    outcome: str
    quality: float  # 0.0 – 1.0
    lesson: str | None = None
    timestamp: float = field(default_factory=time.time)


class SelfReflectionEngine:
    """Thread-safe singleton that reflects on task results and tracks lessons."""

    _instance: SelfReflectionEngine | None = None
    _lock_cls = threading.Lock()

    def __new__(cls) -> SelfReflectionEngine:
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._init_lock = threading.Lock()
                    inst._reflections: list[ReflectionRecord] = []
                    inst._outcomes: list[OutcomeRecord] = []
                    cls._instance = inst
        return cls._instance

    def reflect(
        self,
        task_id: str,
        goal: str,
        steps_taken: list[str],
        result: dict,
        verified: bool,
    ) -> ReflectionRecord:
        """Produce a reflection record for a completed task."""
        outcome = self._determine_outcome(result)
        efficiency = self._evaluate_efficiency(steps_taken, result)
        reasoning = self._evaluate_reasoning(goal, steps_taken, result)
        unnecessary = self._find_unnecessary_steps(steps_taken, result)

        record = ReflectionRecord(
            task_id=task_id,
            goal=goal,
            outcome=outcome,
            efficiency_score=efficiency,
            verification_confirmed=verified,
            unnecessary_steps=unnecessary,
            reasoning_quality=reasoning,
            lessons=[],
            timestamp=time.time(),
        )
        record.lessons = self._extract_lessons(record)

        with self._init_lock:
            self._reflections.append(record)
            if len(self._reflections) > MAX_REFLECTIONS:
                self._reflections = self._reflections[-MAX_REFLECTIONS:]
        logger.info(
            "Reflection produced for task %s — outcome=%s efficiency=%.2f",
            task_id,
            outcome.value,
            efficiency,
        )
        return record

    def record_outcome(
        self,
        goal: str,
        action: str,
        outcome: str,
        quality: float,
        lesson: str | None = None,
    ) -> OutcomeRecord:
        """Store a single outcome record."""
        rec = OutcomeRecord(
            goal=goal,
            action=action,
            outcome=outcome,
            quality=max(0.0, min(1.0, quality)),
            lesson=lesson,
            timestamp=time.time(),
        )
        with self._init_lock:
            self._outcomes.append(rec)
            if len(self._outcomes) > MAX_OUTCOMES:
                self._outcomes = self._outcomes[-MAX_OUTCOMES:]
        return rec

    def get_outcomes(self, limit: int = 50) -> list[OutcomeRecord]:
        """Return the most recent *limit* outcome records."""
        with self._init_lock:
            return list(self._outcomes[-limit:])

    def get_lessons_for_domain(self, domain: str) -> list[str]:
        """Return lessons whose goal or lesson text contains *domain* (case-insensitive)."""
        keyword = domain.lower()
        lessons: list[str] = []
        with self._init_lock:
            for rec in self._outcomes:
                if rec.lesson and keyword in rec.lesson.lower():
                    lessons.append(rec.lesson)
                elif keyword in rec.goal.lower():
                    if rec.lesson:
                        lessons.append(rec.lesson)
            for ref in self._reflections:
                for lesson in ref.lessons:
                    if keyword in lesson.lower():
                        lessons.append(lesson)
        return lessons

    def get_reflection_history(self) -> list[ReflectionRecord]:
        """Return a copy of all stored reflection records."""
        with self._init_lock:
            return list(self._reflections)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        with cls._lock_cls:
            cls._instance = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_outcome(result: dict) -> TaskOutcome:
        """Derive a TaskOutcome enum from a raw result dictionary."""
        status = str(result.get("status", "")).lower()
        if status in ("success", "ok", "done", "completed"):
            return TaskOutcome.SUCCESS
        if status in ("partial", "partial_success"):
            return TaskOutcome.PARTIAL_SUCCESS
        if status in ("timeout", "timed_out"):
            return TaskOutcome.TIMEOUT
        if status in ("rolled_back", "rollback"):
            return TaskOutcome.ROLLED_BACK
        if status in ("failure", "error", "failed"):
            return TaskOutcome.FAILURE
        return TaskOutcome.UNKNOWN

    @staticmethod
    def _evaluate_efficiency(steps: list[str], result: dict) -> float:
        """Return an efficiency score between 0 and 1."""
        if not steps:
            return 1.0
        expected = result.get("expected_steps", len(steps))
        if expected <= 0:
            expected = len(steps)
        ratio = min(len(steps) / expected, 2.0)
        if ratio <= 1.0:
            return 1.0
        return max(0.0, 1.0 - (ratio - 1.0))

    @staticmethod
    def _evaluate_reasoning(
        goal: str, steps: list[str], result: dict
    ) -> str:
        """Classify reasoning quality as correct / acceptable / incorrect."""
        success = str(result.get("status", "")).lower() in (
            "success",
            "ok",
            "done",
            "completed",
        )
        if success and len(steps) <= result.get("expected_steps", len(steps)) + 2:
            return "correct"
        if success:
            return "acceptable"
        return "incorrect"

    @staticmethod
    def _find_unnecessary_steps(
        steps: list[str], result: dict
    ) -> list[str]:
        """Identify steps that did not contribute to the outcome."""
        required = set(result.get("required_steps", []))
        if not required:
            return []
        return [s for s in steps if s not in required]

    @staticmethod
    def _extract_lessons(reflection: ReflectionRecord) -> list[str]:
        """Derive short lesson strings from a reflection."""
        lessons: list[str] = []
        if reflection.efficiency_score < 0.5:
            lessons.append(
                f"Task '{reflection.goal}' was inefficient "
                f"(score={reflection.efficiency_score:.2f}); reduce steps."
            )
        if reflection.unnecessary_steps:
            lessons.append(
                f"Unnecessary steps detected: {', '.join(reflection.unnecessary_steps)}."
            )
        if reflection.outcome in (TaskOutcome.FAILURE, TaskOutcome.TIMEOUT):
            lessons.append(
                f"Task '{reflection.goal}' ended with {reflection.outcome.value}; "
                "add fallback or increase timeout."
            )
        if reflection.verification_confirmed and reflection.efficiency_score >= 0.8:
            lessons.append(
                f"Task '{reflection.goal}' was verified and efficient; "
                "consider caching or reusing this pattern."
            )
        return lessons
