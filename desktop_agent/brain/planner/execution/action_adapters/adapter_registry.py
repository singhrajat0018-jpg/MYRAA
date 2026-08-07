"""
MYRAA Cognitive Engine

Adapter Registry

Routes planner actions to the correct
execution adapter.

Flow:

ExecutorBridge
        |
        ↓
AdapterRegistry
        |
        ↓
Specific Adapter
        |
        ↓
Desktop Tool
"""

from __future__ import annotations


from typing import Dict, List


from ..exceptions import ExecutionError


from .base_adapter import BaseAdapter



class AdapterRegistry:
    """
    Central registry for all MYRAA action adapters.
    """



    def __init__(self) -> None:

        self._adapters: List[BaseAdapter] = []



    # =====================================================
    # Register Adapter
    # =====================================================

    def register(
        self,
        adapter: BaseAdapter,
    ) -> None:
        """
        Add adapter to registry.
        """


        if adapter not in self._adapters:

            self._adapters.append(
                adapter
            )



    # =====================================================
    # Remove Adapter
    # =====================================================

    def unregister(
        self,
        adapter: BaseAdapter,
    ) -> None:
        """
        Remove adapter.
        """

        if adapter in self._adapters:

            self._adapters.remove(
                adapter
            )



    # =====================================================
    # Resolve Adapter
    # =====================================================

    def resolve(
        self,
        action_type,
    ) -> BaseAdapter:
        """
        Find adapter responsible
        for action.
        """


        for adapter in self._adapters:


            if adapter.supports(
                action_type
            ):

                return adapter



        raise ExecutionError(

            f"No adapter found for action: {action_type}"

        )



    # =====================================================
    # Execute Action
    # =====================================================

    async def execute(
        self,
        action_type,
        parameters: Dict | None = None,
    ):

        adapter = self.resolve(
            action_type
        )


        return await adapter.execute(

            action_type,

            parameters,

        )



    # =====================================================
    # Information
    # =====================================================

    def get_adapters(
        self,
    ) -> list[BaseAdapter]:
        """
        Return registered adapters.
        """

        return self._adapters.copy()



    def has_adapter(
        self,
        action_type,
    ) -> bool:
        """
        Check action support.
        """

        for adapter in self._adapters:

            if adapter.supports(
                action_type
            ):

                return True


        return False