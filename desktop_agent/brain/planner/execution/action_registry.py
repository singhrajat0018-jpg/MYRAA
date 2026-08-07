"""
MYRAA Cognitive Engine

Action Registry

Dynamic registry for execution actions.
"""

from __future__ import annotations

from typing import Callable, Any

from ..models.action_types import ActionType



class ActionRegistry:
    """
    Stores and resolves executable actions.
    """

    def __init__(self) -> None:

        self._actions: dict[
            ActionType,
            Callable
        ] = {}


    # =====================================================
    # Register Action
    # =====================================================

    def register(
        self,
        action: ActionType,
        handler: Callable,
    ) -> None:
        """
        Register a new executable action.
        """

        if not callable(handler):

            raise TypeError(
                "Action handler must be callable."
            )


        self._actions[action] = handler



    # =====================================================
    # Remove Action
    # =====================================================

    def unregister(
        self,
        action: ActionType,
    ) -> None:
        """
        Remove action from registry.
        """

        self._actions.pop(
            action,
            None,
        )



    # =====================================================
    # Resolve Action
    # =====================================================

    def resolve(
        self,
        action: ActionType,
    ) -> Callable:
        """
        Get executable handler.
        """

        if action not in self._actions:

            raise KeyError(
                f"No handler registered for {action}"
            )


        return self._actions[action]



    # =====================================================
    # Check Exists
    # =====================================================

    def exists(
        self,
        action: ActionType,
    ) -> bool:
        """
        Check if action exists.
        """

        return action in self._actions



    # =====================================================
    # List Actions
    # =====================================================

    def available_actions(
        self,
    ) -> list[ActionType]:
        """
        Return all registered actions.
        """

        return list(
            self._actions.keys()
        )



    # =====================================================
    # Clear Registry
    # =====================================================

    def clear(
        self,
    ) -> None:
        """
        Remove all actions.
        """

        self._actions.clear()



    # =====================================================
    # Count
    # =====================================================

    def count(
        self,
    ) -> int:

        return len(
            self._actions
        )