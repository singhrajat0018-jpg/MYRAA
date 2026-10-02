"""
MYRAA Vision V3
Screen State Builder

Builds ScreenState from DesktopState and vision pipeline outputs.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .desktop_state import DesktopState
from .screen_state import (
    ScreenState,
    ActiveWindow,
    TextRegionWithGeometry,
    ChangedRegion,
    UIElement,
    InteractiveType
)
from .vision_context import VisionContext
from .fusion_engine import SemanticNode, SemanticScreen, SemanticRole
from .semantic_to_ui_mapper import map_semantic_role_to_ui_type, map_ui_type_to_semantic_role
from .text_region import TextRegion
from .ui_models import BoundingBox, UIElementType
from .frame_difference import DifferenceResult, ChangedRegion as FrameChangedRegion
from .ocr_engine import OCREngine
from .ocr_backends.tesseract_backend import TesseractBackend as TesseractOCR
from .visual_hierarchy import VisualHierarchyDetector


@dataclass(slots=True)
class ElementTracker:
    """Tracks UI elements across frames for identity preservation."""
    _element_history: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    _next_element_id: int = 0
    _max_history_age: float = 5.0  # seconds
    _position_threshold: float = 20.0  # pixels
    _size_threshold: float = 0.3  # 30% size change threshold

    def get_or_create_element_id(
        self,
        element_data: Dict[str, Any],
        current_time: float
    ) -> int:
        """
        Get existing element ID or create new one based on spatial and temporal proximity.

        Args:
            element_data: Dictionary containing element properties (bounds, type, text, etc.)
            current_time: Current timestamp

        Returns:
            Element ID (existing or new)
        """
        # Clean old history
        self._clean_old_history(current_time)

        # Try to match with existing elements
        best_match_id = self._find_best_match(element_data)

        if best_match_id is not None:
            # Update existing element
            self._element_history[best_match_id].update({
                'data': element_data,
                'last_seen': current_time,
                'age': self._element_history[best_match_id].get('age', 0) + 1
            })
            return best_match_id
        else:
            # Create new element
            element_id = self._next_element_id
            self._next_element_id += 1
            self._element_history[element_id] = {
                'data': element_data,
                'last_seen': current_time,
                'age': 1,
                'created': current_time
            }
            return element_id

    def _find_best_match(self, element_data: Dict[str, Any]) -> Optional[int]:
        """Find the best matching existing element based on similarity."""
        best_match_id = None
        best_score = 0.0

        current_bounds = BoundingBox(
            element_data['bounds']['x'],
            element_data['bounds']['y'],
            element_data['bounds']['width'],
            element_data['bounds']['height']
        )
        current_center = current_bounds.center
        current_area = current_bounds.width * current_bounds.height

        for element_id, history in self._element_history.items():
            history_data = history['data']
            history_bounds = BoundingBox(
                history_data['bounds']['x'],
                history_data['bounds']['y'],
                history_data['bounds']['width'],
                history_data['bounds']['height']
            )

            # Calculate spatial similarity
            distance = ((current_center[0] - history_bounds.center[0]) ** 2 +
                       (current_center[1] - history_bounds.center[1]) ** 2) ** 0.5

            # Calculate size similarity
            history_area = history_bounds.width * history_bounds.height
            if max(current_area, history_area) > 0:
                size_similarity = 1.0 - abs(current_area - history_area) / max(current_area, history_area)
            else:
                size_similarity = 1.0 if current_area == history_area else 0.0

            # Calculate type similarity
            type_match = 1.0 if element_data.get('type') == history_data.get('type') else 0.0

            # Calculate text similarity (simple)
            text_similarity = 1.0 if element_data.get('text', '') == history_data.get('text', '') else 0.0

            # Combined score (weighted)
            score = (
                0.4 * (1.0 - min(distance / 100.0, 1.0)) +  # Distance score
                0.3 * size_similarity +                     # Size score
                0.2 * type_match +                          # Type score
                0.1 * text_similarity                       # Text score
            )

            if score > best_score and score > 0.6:  # Minimum threshold
                best_score = score
                best_match_id = element_id

        return best_match_id

    def _clean_old_history(self, current_time: float) -> None:
        """Remove old entries from history."""
        to_remove = []
        for element_id, history in self._element_history.items():
            if current_time - history['last_seen'] > self._max_history_age:
                to_remove.append(element_id)

        for element_id in to_remove:
            del self._element_history[element_id]


class ScreenStateBuilder:
    """
    Builds ScreenState from DesktopState and vision pipeline outputs.

    This is the perception layer that converts raw vision data into
    a structured ScreenState suitable for planning and reasoning.
    """

    def __init__(self):
        self.element_tracker = ElementTracker()
        self.ocr_engine = OCREngine(TesseractOCR())  # For direct OCR text region extraction
        self.last_frame_time: Optional[float] = None
        self.frame_count = 0

    def build_screen_state(self, desktop_state: DesktopState) -> ScreenState:
        """
        Build ScreenState from DesktopState.

        Args:
            desktop_state: Current desktop state from vision pipeline

        Returns:
            ScreenState with structured perception data
        """
        current_time = time.time()
        self.frame_count += 1

        # Initialize ScreenState
        screen_state = ScreenState(
            timestamp=current_time,
            source_frame_timestamp=desktop_state.timestamp
        )

        # Set screen dimensions from vision context
        if desktop_state.vision_context and desktop_state.vision_context.screen:
            screen_state.screen_width = desktop_state.vision_context.screen.width
            screen_state.screen_height = desktop_state.vision_context.screen.height

        # Set active window information
        screen_state.active_window = ActiveWindow(
            title=desktop_state.active_window_title,
            application=desktop_state.active_application,
            hwnd=desktop_state.active_window_hwnd
        )

        # Build UI elements from semantic nodes
        if desktop_state.vision_context and desktop_state.vision_context.screen:
            screen_state.elements = self._build_ui_elements(
                desktop_state.vision_context.screen.nodes,
                current_time
            )

            # Detect visual hierarchy
            hierarchy = visual_hierarchy_detector.detect_hierarchy(screen_state.elements)
            screen_state.metadata['visual_hierarchy'] = {
                'relations_count': len(hierarchy.relations),
                'hierarchy_detected': len(hierarchy.relations) > 0
            }

        # Extract text regions from OCR (direct from OCR engine for better coverage)
        screen_state.text_regions = self._extract_text_regions(
            desktop_state.vision_context,
            current_time
        )

        # Build changed regions from frame difference data
        screen_state.changed_regions = self._build_changed_regions(
            desktop_state.changed_regions,
            current_time
        )

        # Set overall confidence
        screen_state.metadata['confidence'] = desktop_state.confidence
        screen_state.metadata['frame_count'] = self.frame_count
        screen_state.metadata['node_count'] = desktop_state.node_count

        return screen_state

    def _build_ui_elements(
        self,
        semantic_nodes: List[SemanticNode],
        current_time: float
    ) -> List[UIElement]:
        """
        Convert SemanticNodes to UIElements with identity tracking.

        Args:
            semantic_nodes: List of semantic nodes from vision pipeline
            current_time: Current timestamp

        Returns:
            List of UIElements
        """
        ui_elements = []

        for node in semantic_nodes:
            # Skip nodes with no bounds or invalid bounds
            if not node.bounds or node.bounds.width <= 0 or node.bounds.height <= 0:
                continue

            # Map semantic role to UI element type
            ui_type = map_semantic_role_to_ui_type(node.role)

            # Determine interactive type
            interactive_type = self._get_interactive_type(ui_type, node)

            # Prepare element data for tracking
            element_data = {
                'type': ui_type.value,
                'text': node.text or '',
                'bounds': {
                    'x': node.bounds.x,
                    'y': node.bounds.y,
                    'width': node.bounds.width,
                    'height': node.bounds.height
                },
                'confidence': node.confidence
            }

            # Get or create element ID for identity tracking
            element_id = self.element_tracker.get_or_create_element_id(
                element_data, current_time
            )

            # Calculate enhanced confidence
            enhanced_confidence = self._calculate_element_confidence(node, element_id, current_time)

            # Create UIElement
            ui_element = UIElement(
                id=element_id,
                type=ui_type,
                text=node.text or '',
                bounds=BoundingBox(
                    node.bounds.x,
                    node.bounds.y,
                    node.bounds.width,
                    node.bounds.height
                ),
                confidence=enhanced_confidence,
                visible=True,
                metadata={
                    'semantic_role': node.role.value,
                    'layout': node.layout.value if node.layout else None,
                    'shape': node.shape.shape if node.shape else None,
                    'source': node.source,
                    'merged': node.merged,
                    'node_id': node.node_id,
                    'age': self.element_tracker._element_history.get(element_id, {}).get('age', 0)
                }
            )

            ui_elements.append(ui_element)

        # Sort elements by confidence (highest first) for better semantic reference resolution
        ui_elements.sort(key=lambda elem: elem.confidence, reverse=True)

        return ui_elements

    def _get_interactive_type(self, ui_type: UIElementType, node: SemanticNode) -> InteractiveType:
        """Determine if a UI element is interactive and what type."""
        interactive_mapping = {
            UIElementType.BUTTON: InteractiveType.BUTTON,
            UIElementType.TEXTBOX: InteractiveType.INPUT,
            UIElementType.TEXTAREA: InteractiveType.INPUT,
            UIElementType.CHECKBOX: InteractiveType.CHECKBOX,
            UIElementType.RADIO: InteractiveType.RADIO,
            UIElementType.DROPDOWN: InteractiveType.DROPDOWN,
            UIElementType.LINK: InteractiveType.LINK,
            UIElementType.MENU_ITEM: InteractiveType.MENU_ITEM,
            UIElementType.TAB: InteractiveType.TAB,
        }

        return interactive_mapping.get(ui_type, InteractiveType.NONE)

    def _calculate_element_confidence(
        self,
        node: SemanticNode,
        element_id: int,
        current_time: float
    ) -> float:
        """
        Calculate enhanced confidence for UI element.

        Combines:
        - Base confidence from SemanticNode (OCR + shape + layout fusion)
        - Age bonus (elements seen multiple times are more reliable)
        - Consistency bonus (similar position/size across recent frames)
        - Text stability bonus (consistent text content)
        - Geometric confidence (reasonable element dimensions)
        - Context bonus (application/window context appropriateness)
        """
        # Base confidence from the semantic fusion process
        base_confidence = max(0.0, min(node.confidence, 1.0))

        # Get history for this element
        history = self.element_tracker._element_history.get(element_id, {})
        age = history.get('age', 0)

        # Age bonus: elements tracked over multiple frames gain confidence
        age_bonus = min(0.25, age * 0.025)  # Up to 0.25 bonus for age

        # Consistency bonus: check temporal stability
        consistency_bonus = self._calculate_consistency_bonus(node, element_id, history)

        # Text stability bonus: consistent text increases confidence
        text_bonus = self._calculate_text_stability_bonus(node, element_id, history)

        # Geometric confidence: reasonable element sizes get bonus
        geometric_bonus = self._calculate_geometric_bonus(node)

        # Context bonus: application/window context appropriateness
        context_bonus = self._calculate_context_bonus(node, history)

        # Combine all confidence factors
        enhanced_confidence = (
            base_confidence * 0.4 +  # Base confidence is primary factor
            age_bonus * 0.2 +
            consistency_bonus * 0.15 +
            text_bonus * 0.1 +
            geometric_bonus * 0.1 +
            context_bonus * 0.05
        )

        return max(0.0, min(enhanced_confidence, 1.0))

    def _calculate_consistency_bonus(
        self,
        node: SemanticNode,
        element_id: int,
        history: Dict[str, Any]
    ) -> float:
        """Calculate bonus based on temporal consistency of element properties."""
        if 'last_data' not in history or history['age'] < 2:
            return 0.0

        last_data = history['last_data']
        current_bounds = (node.bounds.x, node.bounds.y, node.bounds.width, node.bounds.height)
        last_bounds = (
            last_data.get('bounds', {}).get('x', 0),
            last_data.get('bounds', {}).get('y', 0),
            last_data.get('bounds', {}).get('width', 0),
            last_data.get('bounds', {}).get('height', 0)
        )

        # Calculate position stability (lower variance = higher bonus)
        pos_diff = ((current_bounds[0] - last_bounds[0]) ** 2 +
                   (current_bounds[1] - last_bounds[1]) ** 2) ** 0.5
        pos_bonus = max(0.0, 0.1 - min(pos_diff / 50.0, 0.1))  # Up to 0.1 for stable position

        # Calculate size stability
        size_diff = abs(current_bounds[2] * current_bounds[3] -
                       last_bounds[2] * last_bounds[3])
        max_area = max(current_bounds[2] * current_bounds[3],
                      last_bounds[2] * last_bounds[3]) or 1
        size_bonus = max(0.0, 0.1 - min(size_diff / max_area, 0.1))  # Up to 0.1 for stable size

        return (pos_bonus + size_bonus) / 2  # Average of position and size stability

    def _calculate_text_stability_bonus(
        self,
        node: SemanticNode,
        element_id: int,
        history: Dict[str, Any]
    ) -> float:
        """Calculate bonus based on text consistency."""
        if 'last_data' not in history or history['age'] < 2:
            return 0.0

        last_data = history['last_data']
        last_text = last_data.get('text', '')
        current_text = node.text or ''

        if not last_text and not current_text:
            return 0.05  # Small bonus for consistently empty

        if not last_text or not current_text:
            return 0.0  # No bonus if one is empty

        # Simple text similarity (can be enhanced with Levenshtein distance etc.)
        if last_text == current_text:
            return 0.15  # High bonus for identical text
        elif len(last_text) > 0 and len(current_text) > 0:
            # Basic similarity based on length ratio
            len_ratio = min(len(last_text), len(current_text)) / max(len(last_text), len(current_text))
            return 0.1 * len_ratio  # Up to 0.1 for similar text

        return 0.0

    def _calculate_geometric_bonus(self, node: SemanticNode) -> float:
        """Calculate bonus based on geometric properties."""
        width, height = node.bounds.width, node.bounds.height

        # Very small elements are less reliable
        if width < 5 or height < 5:
            return -0.1  # Penalty for tiny elements

        # Very large elements might be false positives
        if width > 800 or height > 600:  # Assuming reasonable screen sizes
            return -0.05

#        # Reasonable aspect ratios for UI elements
#        aspect_ratio = width / max(height, 1)
#        if 0.1 <= aspect_ratio <= 10.0:  # Reasonable UI element aspect ratios
#            return 0.05
#
        return 0.05  # Small bonus for reasonable geometry

    def _calculate_context_bonus(
        self,
        node: SemanticNode,
        history: Dict[str, Any]
    ) -> float:
        """Calculate bonus based on application/window context."""
        # This would be enhanced with actual window/application context
        # For now, return a small baseline bonus
        return 0.02

    def _extract_text_regions(
        self,
        vision_context: Optional[VisionContext],
        current_time: float
    ) -> List[TextRegionWithGeometry]:
        """
        Extract text regions with geometry from OCR.

        This gets text regions directly from OCR engine for better coverage
        than just relying on TEXT semantic nodes.

        Args:
            vision_context: Current vision context
            current_time: Current timestamp

        Returns:
            List of text regions with geometric information
        """
        text_regions = []

        # In a full implementation, we would get the raw frame and run OCR
        # For now, we'll extract from semantic nodes that have source_text
        if vision_context and vision_context.screen:
            for node in vision_context.screen.nodes:
                if node.source_text and isinstance(node.source_text, TextRegion):
                    text_region = node.source_text
                    text_regions.append(TextRegionWithGeometry(
                        text=text_region.text,
                        bounds=BoundingBox(
                            text_region.bounds.x,
                            text_region.bounds.y,
                            text_region.bounds.width,
                            text_region.bounds.height
                        ),
                        confidence=text_region.confidence,
                        language=""  # Could be enhanced with language detection
                    ))

        return text_regions

    def _build_changed_regions(
        self,
        desktop_changed_regions: List[Any],
        current_time: float
    ) -> List[ChangedRegion]:
        """
        Build changed regions from desktop state changed regions.

        Args:
            desktop_changed_regions: Changed regions from DesktopState
            current_time: Current timestamp

        Returns:
            List of ChangedRegion for ScreenState
        """
        changed_regions = []

        for region in desktop_changed_regions:
            # Handle different types of changed regions
            if hasattr(region, 'x'):  # FrameDifference ChangedRegion
                changed_regions.append(ChangedRegion(
                    bounds=BoundingBox(region.x, region.y, region.width, region.height),
                    timestamp=current_time,
                    change_type="modified",
                    confidence=1.0
                ))
            elif isinstance(region, dict) and 'bounds' in region:  # Dictionary format
                bounds_data = region['bounds']
                changed_regions.append(ChangedRegion(
                    bounds=BoundingBox(
                        bounds_data['x'],
                        bounds_data['y'],
                        bounds_data['width'],
                        bounds_data['height']
                    ),
                    timestamp=region.get('timestamp', current_time),
                    change_type=region.get('change_type', 'modified'),
                    confidence=region.get('confidence', 1.0)
                ))
            elif isinstance(region, BoundingBox):  # Direct BoundingBox
                changed_regions.append(ChangedRegion(
                    bounds=region,
                    timestamp=current_time,
                    change_type="modified",
                    confidence=1.0
                ))

        return changed_regions


# Global instance for use by vision manager
visual_hierarchy_detector = VisualHierarchyDetector()
screen_state_builder = ScreenStateBuilder()