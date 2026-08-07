"""
MYRAA Cognitive Engine

Execution Exceptions

Centralized exception definitions
for the execution engine.
"""

from __future__ import annotations


# ==========================================================
# Base Execution Exception
# ==========================================================

class ExecutionError(Exception):
    """
    Base exception for all execution failures.
    """

    pass



# ==========================================================
# Plan Errors
# ==========================================================

class InvalidPlanError(ExecutionError):
    """
    Raised when ExecutionPlan is invalid.
    """

    pass



class EmptyPlanError(ExecutionError):
    """
    Raised when plan contains no executable steps.
    """

    pass



# ==========================================================
# Step Errors
# ==========================================================

class StepExecutionError(ExecutionError):
    """
    Raised when a PlanStep fails execution.
    """

    def __init__(
        self,
        step_id: int,
        message: str,
    ):

        self.step_id = step_id

        super().__init__(
            f"Step {step_id} failed: {message}"
        )



class DependencyError(ExecutionError):
    """
    Raised when step dependencies are not satisfied.
    """

    pass



# ==========================================================
# Retry Errors
# ==========================================================

class RetryExceededError(ExecutionError):
    """
    Raised when retry attempts are exhausted.
    """

    def __init__(
        self,
        attempts: int,
        message: str = "",
    ):

        self.attempts = attempts

        super().__init__(
            message
            or
            f"Retry limit exceeded after {attempts} attempts"
        )



# ==========================================================
# Verification Errors
# ==========================================================

class VerificationError(ExecutionError):
    """
    Raised when execution verification fails.
    """

    pass



# ==========================================================
# Timeout Errors
# ==========================================================

class ExecutionTimeoutError(ExecutionError):
    """
    Raised when execution exceeds timeout.
    """

    def __init__(
        self,
        timeout: float,
    ):

        self.timeout = timeout

        super().__init__(
            f"Execution timeout after {timeout} seconds"
        )



# ==========================================================
# Rollback Errors
# ==========================================================

class RollbackError(ExecutionError):
    """
    Raised when rollback fails.
    """

    pass



# ==========================================================
# Cancellation
# ==========================================================

class ExecutionCancelledError(ExecutionError):
    """
    Raised when execution is cancelled.
    """

    pass



# ==========================================================
# Shutdown
# ==========================================================

class ExecutionShutdownError(ExecutionError):
    """
    Raised when engine shutdown is requested.
    """

    pass