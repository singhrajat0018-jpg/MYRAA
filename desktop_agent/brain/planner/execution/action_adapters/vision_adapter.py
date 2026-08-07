"""
MYRAA Cognitive Engine

Vision Action Adapter

Handles computer vision operations.

Supported:

- CAPTURE_SCREEN
- OCR_SCREEN
- FIND_ELEMENT
- VERIFY_ELEMENT
- VERIFY_SCREEN
"""

from __future__ import annotations


from typing import Any, Dict


from .base_adapter import BaseAdapter


from ...models.action_types import ActionType


from ..exceptions import ExecutionError



class VisionAdapter(BaseAdapter):
    """
    Adapter for screen vision operations.
    """



    def __init__(
        self,
        vision_tools=None,
    ) -> None:


        super().__init__(
            name="vision_adapter"
        )


        self.vision_tools = (
            vision_tools
        )



    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {


            ActionType.CAPTURE_SCREEN,

            ActionType.OCR_SCREEN,

            ActionType.FIND_ELEMENT,

            ActionType.VERIFY_ELEMENT,

            ActionType.VERIFY_SCREEN,

        }



    # =====================================================
    # Execute
    # =====================================================

    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:



        if action_type == ActionType.CAPTURE_SCREEN:

            return await self._capture_screen(
                parameters
            )



        if action_type == ActionType.OCR_SCREEN:

            return await self._ocr_screen(
                parameters
            )



        if action_type == ActionType.FIND_ELEMENT:

            return await self._find_element(
                parameters
            )



        if action_type == ActionType.VERIFY_ELEMENT:

            return await self._verify_element(
                parameters
            )



        if action_type == ActionType.VERIFY_SCREEN:

            return await self._verify_screen(
                parameters
            )



        raise ExecutionError(
            f"Unsupported vision action: {action_type}"
        )



    # =====================================================
    # Vision Operations
    # =====================================================


    async def _capture_screen(
        self,
        parameters,
    ):


        if self.vision_tools:

            return await self.vision_tools.capture_screen()



        return {

            "status": "captured",

            "image": None

        }



    async def _ocr_screen(
        self,
        parameters,
    ):


        if self.vision_tools:

            return await self.vision_tools.ocr_screen()



        return {

            "text": "",

            "status": "ocr_completed"

        }



    async def _find_element(
        self,
        parameters,
    ):


        element = parameters.get(
            "element"
        )


        if not element:

            raise ExecutionError(
                "Element description missing"
            )



        if self.vision_tools:

            return await self.vision_tools.find_element(
                element
            )



        return {

            "element": element,

            "found": False

        }



    async def _verify_element(
        self,
        parameters,
    ):


        element = parameters.get(
            "element"
        )


        if self.vision_tools:

            return await self.vision_tools.verify_element(
                element
            )



        return {

            "element": element,

            "verified": False

        }



    async def _verify_screen(
        self,
        parameters,
    ):


        expected = parameters.get(
            "expected"
        )


        if self.vision_tools:

            return await self.vision_tools.verify_screen(
                expected
            )



        return {

            "expected": expected,

            "verified": False

        }