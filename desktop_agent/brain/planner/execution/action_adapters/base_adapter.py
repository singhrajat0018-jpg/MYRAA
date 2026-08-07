"""
MYRAA Cognitive Engine

Base Action Adapter

All action adapters inherit from this class.

Architecture:

ExecutorBridge
        |
        ↓
AdapterRegistry
        |
        ↓
BaseAdapter
        |
        ↓
Concrete Adapter
"""

from __future__ import annotations


from abc import ABC, abstractmethod

from typing import Any, Dict


from ..exceptions import ExecutionError



class BaseAdapter(ABC):
    """
    Base interface for all MYRAA action adapters.
    """


    def __init__(
        self,
        name: str,
    ) -> None:

        self.name = name



    # =====================================================
    # Adapter Information
    # =====================================================

    def get_name(
        self,
    ) -> str:
        """
        Return adapter name.
        """

        return self.name



    # =====================================================
    # Action Support
    # =====================================================

    @abstractmethod
    def supports(
        self,
        action_type,
    ) -> bool:
        """
        Check whether adapter supports action.
        """

        pass



    # =====================================================
    # Execute
    # =====================================================

    async def execute(
        self,
        action_type,
        parameters: Dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute action safely.
        """


        if parameters is None:

            parameters = {}



        if not self.supports(
            action_type
        ):

            raise ExecutionError(

                f"{self.name} does not support {action_type}"

            )



        try:

            return await self._execute(

                action_type,

                parameters,

            )


        except Exception as exc:


            raise ExecutionError(

                f"{self.name} failed: {exc}"

            ) from exc



    # =====================================================
    # Internal Execute
    # =====================================================

    @abstractmethod
    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:
        """
        Actual adapter implementation.
        """

        pass



    # =====================================================
    # Validation
    # =====================================================

    def validate_parameters(
        self,
        parameters: Dict[str, Any],
        required: list[str],
    ) -> bool:
        """
        Validate required parameters.
        """


        for key in required:

            if key not in parameters:

                return False


        return True