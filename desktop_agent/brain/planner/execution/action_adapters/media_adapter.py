"""
MYRAA Cognitive Engine

Media Action Adapter

Handles media operations.

Supported:

- PLAY_MEDIA
- STOP_MEDIA
"""

from __future__ import annotations


from typing import Any, Dict


from .base_adapter import BaseAdapter


from ...models.action_types import ActionType


from ..exceptions import ExecutionError



class MediaAdapter(BaseAdapter):
    """
    Adapter for media control.
    """



    def __init__(
        self,
        media_tools=None,
    ) -> None:


        super().__init__(
            name="media_adapter"
        )


        self.media_tools = (
            media_tools
        )



    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {


            ActionType.PLAY_MEDIA,

            ActionType.STOP_MEDIA,

        }



    # =====================================================
    # Execute
    # =====================================================

    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:



        if action_type == ActionType.PLAY_MEDIA:

            return await self._play_media(
                parameters
            )



        if action_type == ActionType.STOP_MEDIA:

            return await self._stop_media(
                parameters
            )



        raise ExecutionError(
            f"Unsupported media action: {action_type}"
        )



    # =====================================================
    # Media Operations
    # =====================================================


    async def _play_media(
        self,
        parameters,
    ):


        media = parameters.get(
            "media"
        )


        if not media:

            raise ExecutionError(
                "Media path or URL missing"
            )



        if self.media_tools:

            return await self.media_tools.play_media(
                media
            )



        return {

            "media": media,

            "status": "playing"

        }



    async def _stop_media(
        self,
        parameters,
    ):


        if self.media_tools:

            return await self.media_tools.stop_media()



        return {

            "status": "stopped"

        }