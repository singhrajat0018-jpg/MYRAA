"""
MYRAA Cognitive Engine

Action Adapter Package

Contains all execution adapters used
by ExecutorBridge.
"""


from .base_adapter import BaseAdapter


from .adapter_registry import AdapterRegistry


from .application_adapter import ApplicationAdapter


from .browser_adapter import BrowserAdapter


from .file_adapter import FileAdapter


from .keyboard_adapter import KeyboardAdapter


from .mouse_adapter import MouseAdapter


from .system_adapter import SystemAdapter


from .vision_adapter import VisionAdapter


from .media_adapter import MediaAdapter

from .adapter_executor import AdapterExecutor



__all__ = [

    "BaseAdapter",

    "AdapterRegistry",

    "ApplicationAdapter",

    "BrowserAdapter",

    "FileAdapter",

    "KeyboardAdapter",

    "MouseAdapter",

    "SystemAdapter",

    "VisionAdapter",

    "MediaAdapter",

]