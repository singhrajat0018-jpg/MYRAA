"""
Execution Coordinator

Coordinates the complete execution intelligence pipeline.

Responsibilities
----------------
• Execution report lifecycle
• Live monitoring
• Verification
• Retry analytics
• Recovery
• Reflection hook
• Working memory hook

NOTE:
This class DOES NOT execute tools.
Execution is still handled by Orchestrator/ExecutionWorker.
"""

from __future__ import annotations

import logging
from typing import Any

from .execution_monitor import ExecutionMonitor
from .execution_report import ExecutionReport
from .execution_verifier import ExecutionVerifier
from .retry_manager import RetryManager
from .recovery_manager import RecoveryManager

logger = logging.getLogger(__name__)


class ExecutionCoordinator:
    """
    High-level execution intelligence coordinator.

    The coordinator owns all execution-intelligence modules
    while keeping the orchestrator lightweight.
    """

    def __init__(
        self,
        execution_monitor: ExecutionMonitor,
        execution_verifier: ExecutionVerifier,
        retry_manager: RetryManager,
        recovery_manager: RecoveryManager,
        reflection_engine: Any = None,
        working_memory: Any = None,
        blackboard=None,
    ):

        self.monitor = execution_monitor
        self.verifier = execution_verifier
        self.retry_manager = retry_manager
        self.recovery_manager = recovery_manager
        self.blackboard = blackboard
        self.reflection = reflection_engine
        self.working_memory = working_memory

    # ==========================================================
    # Report Lifecycle
    # ==========================================================

    def create_report(
        self,
        task_id: str,
        task_name: str,
    ) -> ExecutionReport:

        report = ExecutionReport(
            task_id=task_id,
            task=task_name,
        )

        report.mark_started()

        self.monitor.register(report)
        self.monitor.start(task_id)

        logger.debug(
            "Execution started: %s",
            task_name,
        )

        return report

    # ==========================================================
    # Verification
    # ==========================================================

    def verify(
        self,
        tool: str,
        parameters: dict,
        result: Any,
        report: ExecutionReport,
    ):

        verification = self.verifier.verify(
            tool=tool,
            parameters=parameters,
            result=result,
        )

        report.verified = verification.success

        return verification

    # ==========================================================
    # Success
    # ==========================================================

    def complete(
        self,
        report: ExecutionReport,
        summary: str = "",
    ):
        print("\n========== EXECUTION COORDINATOR ==========")
        print("complete() called")
        print("Metadata:", report.metadata)
        print("==========================================\n")
        report.summary = (
            summary
            if summary
            else "Execution completed successfully."
        )

        report.mark_completed()

        self.monitor.complete(
            report.task_id,
        )

        self._remember(report)

        if self.blackboard:

            self.blackboard.write(

                "execution",

                "latest",

                report,

            )

    # ==========================================================
    # Failure
    # ==========================================================

    def fail(
        self,
        report: ExecutionReport,
        error: str,
    ):

        report.mark_failed(error)

        self.monitor.fail(
            report.task_id,
            error,
        )

        self._remember(report)

        if self.blackboard:

            self.blackboard.write(

                "execution",

                "latest",

                report,

            )
    # ==========================================================
    # Recovery
    # ==========================================================

    def recover(
        self,
        tool_name: str,
        parameters: dict,
        report: ExecutionReport,
    ) -> bool:

        recovered = self.recovery_manager.recover(
            tool_name=tool_name,
            parameters=parameters,
        )

        if recovered:

            report.recovery_used = True
            report.recovery_strategy = "default"

        return recovered

    # ==========================================================
    # Retry Analytics
    # ==========================================================

    def record_retry(
        self,
        tool_name: str,
        attempt: int,
        reason: str,
    ):

        try:

            self.retry_manager.record_retry(
                tool_name=tool_name,
                attempt=attempt,
                reason=reason,
            )

        except Exception:

            logger.exception(
                "Retry analytics failed."
            )

    # ==========================================================
    # Cleanup
    # ==========================================================

    def finish(
        self,
        report: ExecutionReport,
    ):

        self.monitor.remove(
            report.task_id,
        )

    # ==========================================================
    # Memory + Reflection
    # ==========================================================

    def _remember(
        self,
        report: ExecutionReport,
    ):
        print("Coordinator WM:", id(self.working_memory))
        print("\n===== EXECUTION WORKING MEMORY =====")
        print("WorkingMemory id:", id(self.working_memory))
        print("Snapshot id:", id(self.working_memory.snapshot))
        print("====================================")
        print("\n========== WORKING MEMORY ==========")
        print("_remember() called")
        print(report.metadata)
        print("===================================\n")
        try:

            if self.working_memory:

                self.working_memory.remember_execution(
                    title=report.task,
                    success=report.success,
                    execution_time=report.total_duration,
                )
            # ---------------------------------------------------------
            # Update Working Memory entities
            # ---------------------------------------------------------

            metadata = report.metadata or {}

            self.working_memory.update_entity(

                application=metadata.get("application"),

                file=metadata.get("file"),

                folder=metadata.get("folder"),

                website=metadata.get("website"),

                person=metadata.get("person"),

            )

            # ---------------------------------------------------------
            # Remember entities produced by execution
            # ---------------------------------------------------------

            try:

                metadata = report.metadata or {}

                entity_fields = (
                    "application",
                    "website",
                    "file",
                    "folder",
                    "person",
                )

                for field in entity_fields:

                    value = metadata.get(field)

                    if value:

                        self.working_memory.remember_entity(
                            field,
                            value,
                        )

            except Exception:

                logger.exception(
                    "WorkingMemory entity update failed."
                )

        except Exception:

            logger.exception(
                "WorkingMemory update failed."
            )

        try:

            if self.reflection:

                self.reflection.record(
                    action=report.task,
                    success=report.success,
                    message=report.summary,
                )

        except Exception:

            logger.exception(
                
            )

        meta = report.metadata

        try:
            if self.working_memory:

                self.working_memory.update_action(
                    action=report.task,
                    tool=meta.get("application", ""),
                    result=meta.get("result", "")
                )

        except Exception:
            logger.exception("WorkingMemory entity update failed.")