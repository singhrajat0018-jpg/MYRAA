"""
MYRAA Cognitive Engine

Progress Tracker

Tracks execution progress,
completion percentage and ETA.
"""

from __future__ import annotations

from dataclasses import dataclass
import time



# ==========================================================
# Progress State
# ==========================================================

@dataclass(slots=True)
class ProgressState:
    """
    Current execution progress.
    """

    current: int = 0

    total: int = 0

    percentage: float = 0.0

    elapsed_time: float = 0.0

    estimated_remaining: float = 0.0



# ==========================================================
# Progress Tracker
# ==========================================================

class ProgressTracker:
    """
    Tracks execution progress.
    """

    def __init__(self) -> None:

        self.state = ProgressState()

        self._start_time: float | None = None


    # =====================================================
    # Reset
    # =====================================================

    def reset(
        self,
        total: int = 0,
    ) -> None:
        """
        Start new progress tracking.
        """

        self.state = ProgressState(

            current=0,

            total=total,

        )

        self._start_time = time.perf_counter()


    # =====================================================
    # Update
    # =====================================================

    def update(
        self,
        current: int,
        total: int | None = None,
    ) -> ProgressState:
        """
        Update execution progress.
        """

        if total is not None:

            self.state.total = total


        self.state.current = current


        if self.state.total > 0:

            self.state.percentage = (

                self.state.current
                /
                self.state.total

            ) * 100


        self._calculate_time()


        return self.state



    # =====================================================
    # Increment
    # =====================================================

    def increment(
        self,
    ) -> ProgressState:
        """
        Increase completed step count.
        """

        return self.update(

            self.state.current + 1

        )



    # =====================================================
    # Time Calculation
    # =====================================================

    def _calculate_time(
        self,
    ) -> None:

        if self._start_time is None:

            return


        elapsed = (

            time.perf_counter()
            -
            self._start_time

        )


        self.state.elapsed_time = elapsed


        if self.state.current > 0:

            average = (

                elapsed
                /
                self.state.current

            )

            remaining = (

                self.state.total
                -
                self.state.current

            )


            self.state.estimated_remaining = (

                average
                *
                remaining

            )



    # =====================================================
    # Properties
    # =====================================================

    @property
    def percentage(
        self,
    ) -> float:

        return self.state.percentage



    @property
    def completed(
        self,
    ) -> int:

        return self.state.current



    @property
    def remaining(
        self,
    ) -> int:

        return max(

            0,

            self.state.total
            -
            self.state.current

        )



    @property
    def eta(
        self,
    ) -> float:

        return self.state.estimated_remaining



    def get_state(
        self,
    ) -> ProgressState:

        return self.state


    