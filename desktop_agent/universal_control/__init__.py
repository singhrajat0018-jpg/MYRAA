"""Phase E: Universal App/Website Control — consumes existing ContinuousVisionController."""

from .ui_element import UniversalElement, ElementType, InteractiveRole
from .ui_discovery import UIDiscovery, DiscoveryResult
from .semantic_mapper import SemanticMapper, MappingResult
from .universal_controller import UniversalController, ControlResult
from .app_profile import AppProfile, AppCapability
from .workflow_memory import WorkflowMemory, WorkflowStep

__all__ = [
    "UniversalElement", "ElementType", "InteractiveRole",
    "UIDiscovery", "DiscoveryResult",
    "SemanticMapper", "MappingResult",
    "UniversalController", "ControlResult",
    "AppProfile", "AppCapability",
    "WorkflowMemory", "WorkflowStep",
]
