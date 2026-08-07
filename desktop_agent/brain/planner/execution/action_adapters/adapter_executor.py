"""
MYRAA Cognitive Engine

Adapter Executor

Bridge between ExecutorBridge
and Action Adapter System.
"""

from __future__ import annotations


from typing import Any, Dict


from ..execution_result import ExecutionResult


from ..exceptions import ExecutionError


from .adapter_registry import AdapterRegistry



class AdapterExecutor:
    """
    Executes planner actions using adapters.
    """



    def __init__(
        self,
        registry: AdapterRegistry,
    ) -> None:

        self.registry = registry



    # =====================================================
    # Execute Action
    # =====================================================

    async def execute(
        self,
        action_type,
        parameters: Dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        Execute adapter action
        and normalize result.
        """


        try:

            value = await self.registry.execute(

                action_type,

                parameters or {},

            )



            return ExecutionResult(

                success=True,

                verified=False,

                value=value,

                metadata={

                    "action":
                        str(action_type),

                },

            )



        except Exception as exc:


            return ExecutionResult(

                success=False,

                error_message=str(exc),

                exception=exc,

            )