"""
MYRAA Reflection Engine
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Reflection:

    action: str
    success: bool
    message: str
    timestamp: datetime


class ReflectionEngine:

    def __init__(self, working_memory, blackboard=None,):

        self.working_memory = working_memory

        self.blackboard = blackboard

        self._history: list[Reflection] = []

    def record(
        self,
        action: str,
        success: bool,
        message: str,
    ):

        reflection = Reflection(

            action=action,

            success=success,

            message=message,

            timestamp=datetime.now(),

        )

        self._history.append(

            reflection

        )

        if self.blackboard:

            self.blackboard.write(

                "reflection",

                "latest",

                reflection,

            )

    def recent(self, limit: int = 20):

        return self._history[-limit:]

    def clear(self):

        self._history.clear()

    def last(self) -> Reflection | None:

        if not self._history:
            return None

        return self._history[-1]

    def success_rate(self) -> float:

        if not self._history:
            return 1.0

        success = sum(
            1
            for item in self._history
            if item.success
        )

        return success / len(self._history)

    def failed_actions(
        self,
        limit: int = 10,
    ) -> list[Reflection]:

        failures = [
            item
            for item in self._history
            if not item.success
        ]

        return failures[-limit:]

    def reflect(self, observation, events, predictions):
        """
        Adapter method for autonomy loop reflection.

        The autonomy loop calls this to reflect on observations, events, and predictions.
        This method analyzes them and records a reflection.

        Args:
            observation: Current observation from perception
            events: Recent events from the blackboard
            predictions: Model predictions about outcomes
        """
        # Simple reflection: check if predictions matched observations
        try:
            # Extract key info for reflection
            if hasattr(observation, '__dict__'):
                obs_str = str(observation.__dict__)
            else:
                obs_str = str(observation)

            # For now, record a successful reflection
            # More sophisticated analysis can be added later
            self.record(
                action="autonomy_reflection",
                success=True,
                message=f"Reflected on observation with {len(events) if events else 0} events"
            )
        except Exception as e:
            # Record failed reflection
            self.record(
                action="autonomy_reflection",
                success=False,
                message=f"Reflection failed: {e}"
            )

    def learn(
        self,
        plan,
        result,
    ):

        title = result.plan_title or "Unknown"

        message = (
            "Execution completed"
            if result.success
            else result.reason
        )

        # Existing reflection history
        self.record(
            action=title,
            success=result.success,
            message=message,
        )

        # Working Memory update
        self.working_memory.remember_execution(
            title=title,
            success=result.success,
            execution_time=result.execution_time,
        )

    def process_execution_feedback(self):

        report = self.blackboard.read(

            "execution",

            "latest",

        )

        if report is None:

            return

        self.record(

            action=report.task,

            success=report.success,

            message=report.summary,

        )