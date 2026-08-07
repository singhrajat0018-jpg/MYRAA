"""
MYRAA Cognitive Engine

Adapter Factory

Creates and registers all execution adapters.
"""

from __future__ import annotations


from .adapter_registry import AdapterRegistry


from .application_adapter import ApplicationAdapter


from .browser_adapter import BrowserAdapter


from .file_adapter import FileAdapter


from .keyboard_adapter import KeyboardAdapter


from .mouse_adapter import MouseAdapter


from .system_adapter import SystemAdapter


from .vision_adapter import VisionAdapter


from .media_adapter import MediaAdapter



class AdapterFactory:
    """
    Creates MYRAA execution adapter system.
    """



    @staticmethod
    def create_registry(
        application_tools=None,
        browser_tools=None,
        file_tools=None,
        keyboard_tools=None,
        mouse_tools=None,
        system_tools=None,
        vision_tools=None,
        media_tools=None,
    ) -> AdapterRegistry:
        """
        Build complete adapter registry.
        """


        registry = AdapterRegistry()



        # -------------------------------------------------
        # Register Application
        # -------------------------------------------------

        registry.register(

            ApplicationAdapter(

                application_tools

            )

        )



        # -------------------------------------------------
        # Register Browser
        # -------------------------------------------------

        registry.register(

            BrowserAdapter(

                browser_tools

            )

        )



        # -------------------------------------------------
        # Register Files
        # -------------------------------------------------

        registry.register(

            FileAdapter(

                file_tools

            )

        )



        # -------------------------------------------------
        # Register Keyboard
        # -------------------------------------------------

        registry.register(

            KeyboardAdapter(

                keyboard_tools

            )

        )



        # -------------------------------------------------
        # Register Mouse
        # -------------------------------------------------

        registry.register(

            MouseAdapter(

                mouse_tools

            )

        )



        # -------------------------------------------------
        # Register System
        # -------------------------------------------------

        registry.register(

            SystemAdapter(

                system_tools

            )

        )



        # -------------------------------------------------
        # Register Vision
        # -------------------------------------------------

        registry.register(

            VisionAdapter(

                vision_tools

            )

        )



        # -------------------------------------------------
        # Register Media
        # -------------------------------------------------

        registry.register(

            MediaAdapter(

                media_tools

            )

        )



        return registry