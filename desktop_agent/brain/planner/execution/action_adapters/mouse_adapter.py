"""
MYRAA Cognitive Engine

Mouse Action Adapter

Handles mouse operations.

Supported:

- CLICK
- DOUBLE_CLICK
- RIGHT_CLICK
- MIDDLE_CLICK
- MOVE_MOUSE
- DRAG
- DROP
- SCROLL_UP
- SCROLL_DOWN
- HOVER
"""

from __future__ import annotations


from typing import Any, Dict


from .base_adapter import BaseAdapter


from ...models.action_types import ActionType


from ..exceptions import ExecutionError



class MouseAdapter(BaseAdapter):
    """
    Adapter for mouse control.
    """



    def __init__(
        self,
        mouse_tools=None,
    ) -> None:


        super().__init__(
            name="mouse_adapter"
        )


        self.mouse_tools = (
            mouse_tools
        )



    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {


            ActionType.CLICK,

            ActionType.DOUBLE_CLICK,

            ActionType.RIGHT_CLICK,

            ActionType.MIDDLE_CLICK,

            ActionType.MOVE_MOUSE,

            ActionType.DRAG,

            ActionType.DROP,

            ActionType.SCROLL_UP,

            ActionType.SCROLL_DOWN,

            ActionType.HOVER,

        }



    # =====================================================
    # Execute
    # =====================================================

    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:



        if action_type == ActionType.CLICK:

            return await self._click(
                parameters
            )



        if action_type == ActionType.DOUBLE_CLICK:

            return await self._double_click(
                parameters
            )



        if action_type == ActionType.RIGHT_CLICK:

            return await self._right_click(
                parameters
            )



        if action_type == ActionType.MIDDLE_CLICK:

            return await self._middle_click(
                parameters
            )



        if action_type == ActionType.MOVE_MOUSE:

            return await self._move_mouse(
                parameters
            )



        if action_type == ActionType.DRAG:

            return await self._drag(
                parameters
            )



        if action_type == ActionType.DROP:

            return await self._drop(
                parameters
            )



        if action_type == ActionType.SCROLL_UP:

            return await self._scroll(
                parameters,
                "up"
            )



        if action_type == ActionType.SCROLL_DOWN:

            return await self._scroll(
                parameters,
                "down"
            )



        if action_type == ActionType.HOVER:

            return await self._hover(
                parameters
            )



        raise ExecutionError(
            f"Unsupported mouse action: {action_type}"
        )



    # =====================================================
    # Mouse Operations
    # =====================================================


    async def _click(
        self,
        parameters,
    ):


        x = parameters.get("x")

        y = parameters.get("y")



        if self.mouse_tools:

            return await self.mouse_tools.click(
                x,
                y
            )


        return {

            "x": x,

            "y": y,

            "status": "clicked"

        }



    async def _double_click(
        self,
        parameters,
    ):


        x = parameters.get("x")

        y = parameters.get("y")



        if self.mouse_tools:

            return await self.mouse_tools.double_click(
                x,
                y
            )



        return {

            "x": x,

            "y": y,

            "status": "double_clicked"

        }



    async def _right_click(
        self,
        parameters,
    ):


        x = parameters.get("x")

        y = parameters.get("y")



        if self.mouse_tools:

            return await self.mouse_tools.right_click(
                x,
                y
            )



        return {

            "x": x,

            "y": y,

            "status": "right_clicked"

        }



    async def _middle_click(
        self,
        parameters,
    ):


        x = parameters.get("x")

        y = parameters.get("y")



        if self.mouse_tools:

            return await self.mouse_tools.middle_click(
                x,
                y
            )



        return {

            "x": x,

            "y": y,

            "status": "middle_clicked"

        }



    async def _move_mouse(
        self,
        parameters,
    ):


        x = parameters.get("x")

        y = parameters.get("y")



        if self.mouse_tools:

            return await self.mouse_tools.move_mouse(
                x,
                y
            )



        return {

            "x": x,

            "y": y,

            "status": "moved"

        }



    async def _drag(
        self,
        parameters,
    ):


        start = parameters.get(
            "start"
        )

        end = parameters.get(
            "end"
        )



        if self.mouse_tools:

            return await self.mouse_tools.drag(
                start,
                end
            )



        return {

            "start": start,

            "end": end,

            "status": "dragged"

        }



    async def _drop(
        self,
        parameters,
    ):


        if self.mouse_tools:

            return await self.mouse_tools.drop()



        return {

            "status": "dropped"

        }



    async def _scroll(
        self,
        parameters,
        direction,
    ):


        amount = parameters.get(
            "amount",
            1
        )


        if self.mouse_tools:

            return await self.mouse_tools.scroll(
                direction,
                amount
            )



        return {

            "direction": direction,

            "amount": amount,

            "status": "scrolled"

        }



    async def _hover(
        self,
        parameters,
    ):


        x = parameters.get("x")

        y = parameters.get("y")



        if self.mouse_tools:

            return await self.mouse_tools.hover(
                x,
                y
            )



        return {

            "x": x,

            "y": y,

            "status": "hovered"

        }