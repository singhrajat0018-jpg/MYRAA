"""
Tests for ScreenState and related perception components.
"""

import unittest
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Mock the necessary modules for testing
try:
    from desktop_agent.desktop.vision.screen_state import (
        ScreenState,
        ActiveWindow,
        TextRegionWithGeometry,
        ChangedRegion,
    )
    from desktop_agent.desktop.vision.screen_state_builder import ScreenStateBuilder
    from desktop_agent.desktop.vision.semantic_to_ui_mapper import (
        map_semantic_role_to_ui_type,
        map_ui_type_to_semantic_role
    )
    from desktop_agent.desktop.vision.visual_hierarchy import (
        VisualHierarchyDetector,
        HierarchyRelation
    )
    from desktop_agent.desktop.vision.ui_models import (
        BoundingBox,
        UIElement,
        InteractiveType,
        UIElementType
    )
    from desktop_agent.desktop.vision.fusion_engine import (
        SemanticNode,
        SemanticRole,
        SemanticScreen
    )

    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"Modules not available for testing: {e}")


@unittest.skipIf(not MODULES_AVAILABLE, "Required modules not available")
class TestScreenState(unittest.TestCase):
    """Test ScreenState functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.screen_state = ScreenState(
            timestamp=1234567890.0,
            screen_width=1920,
            screen_height=1080
        )

        self.active_window = ActiveWindow(
            title="Test Window",
            application="test_app.exe",
            hwnd=12345
        )

    def test_screen_state_creation(self):
        """Test basic ScreenState creation."""
        self.assertEqual(self.screen_state.screen_width, 1920)
        self.assertEqual(self.screen_state.screen_height, 1080)
        self.assertEqual(self.screen_state.timestamp, 1234567890.0)
        self.assertIsInstance(self.screen_state.elements, list)
        self.assertIsInstance(self.screen_state.text_regions, list)
        self.assertIsInstance(self.screen_state.changed_regions, list)

    def test_active_window_property(self):
        """Test active window property."""
        screen_state = ScreenState(active_window=self.active_window)
        self.assertEqual(screen_state.active_window.title, "Test Window")
        self.assertEqual(screen_state.active_window.application, "test_app.exe")
        self.assertEqual(screen_state.active_window.hwnd, 12345)

    def test_ui_element_creation(self):
        """Test UIElement creation and properties."""
        element = UIElement(
            id=1,
            type=UIElementType.BUTTON,
            text="Click Me",
            bounds=BoundingBox(100, 100, 80, 30),
            confidence=0.95
        )

        self.assertEqual(element.id, 1)
        self.assertEqual(element.type, UIElementType.BUTTON)
        self.assertEqual(element.text, "Click Me")
        self.assertEqual(element.bounds.x, 100)
        self.assertEqual(element.bounds.y, 100)
        self.assertEqual(element.bounds.width, 80)
        self.assertEqual(element.bounds.height, 30)
        self.assertEqual(element.confidence, 0.95)
        self.assertEqual(element.center, (140, 115))  # (100+40, 100+15)
        self.assertTrue(element.visible)
        self.assertEqual(element.interactive, InteractiveType.BUTTON)

    def test_get_elements_by_type(self):
        """Test getting elements by type."""
        button_element = UIElement(
            id=1,
            type=UIElementType.BUTTON,
            text="Button",
            bounds=BoundingBox(0, 0, 50, 30),
            confidence=0.9
        )

        text_element = UIElement(
            id=2,
            type=UIElementType.TEXT,
            text="Label",
            bounds=BoundingBox(60, 0, 50, 20),
            confidence=0.8
        )

        screen_state = ScreenState(elements=[button_element, text_element])
        buttons = screen_state.get_elements_by_type(UIElementType.BUTTON)
        texts = screen_state.get_elements_by_type(UIElementType.TEXT)

        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].id, 1)
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].id, 2)

    def test_get_interactive_elements(self):
        """Test getting interactive elements."""
        button = UIElement(
            id=1,
            type=UIElementType.BUTTON,
            text="Button",
            bounds=BoundingBox(0, 0, 50, 30),
            confidence=0.9
        )

        text = UIElement(
            id=2,
            type=UIElementType.TEXT,
            text="Label",
            bounds=BoundingBox(60, 0, 50, 20),
            confidence=0.8
        )

        checkbox = UIElement(
            id=3,
            type=UIElementType.CHECKBOX,
            text="",
            bounds=BoundingBox(120, 0, 20, 20),
            confidence=0.7
        )

        screen_state = ScreenState(elements=[button, text, checkbox])
        interactive = screen_state.get_interactive_elements()

        self.assertEqual(len(interactive), 2)  # Button and checkbox
        interactive_ids = [elem.id for elem in interactive]
        self.assertIn(1, interactive_ids)
        self.assertIn(3, interactive_ids)
        self.assertNotIn(2, interactive_ids)  # Text is not interactive

    def test_get_element_at_position(self):
        """Test getting element at specific position."""
        element = UIElement(
            id=1,
            type=UIElementType.BUTTON,
            text="Button",
            bounds=BoundingBox(100, 100, 80, 30),  # From (100,100) to (180,130)
            confidence=0.9
        )

        screen_state = ScreenState(elements=[element])

        # Test inside element
        found = screen_state.get_element_at_position(140, 115)  # Center
        self.assertIsNotNone(found)
        self.assertEqual(found.id, 1)

        # Test inside element (corner)
        found = screen_state.get_element_at_position(120, 120)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, 1)

        # Test outside element
        found = screen_state.get_element_at_position(50, 50)
        self.assertIsNone(found)

        found = screen_state.get_element_at_position(200, 200)
        self.assertIsNone(found)

    def test_to_dict(self):
        """Test serialization to dictionary."""
        element = UIElement(
            id=1,
            type=UIElementType.BUTTON,
            text="Test",
            bounds=BoundingBox(10, 20, 50, 30),
            confidence=0.85
        )

        active_window = ActiveWindow(
            title="Test App",
            application="test.exe",
            hwnd=54321
        )

        screen_state = ScreenState(
            timestamp=1234567890.5,
            screen_width=1920,
            screen_height=1080,
            active_window=active_window,
            elements=[element]
        )

        result = screen_state.to_dict()

        self.assertEqual(result['timestamp'], 1234567890.5)
        self.assertEqual(result['screen_width'], 1920)
        self.assertEqual(result['screen_height'], 1080)
        self.assertEqual(result['active_window']['title'], "Test App")
        self.assertEqual(result['active_window']['application'], "test.exe")
        self.assertEqual(result['active_window']['hwnd'], 54321)
        self.assertEqual(len(result['elements']), 1)
        self.assertEqual(result['elements'][0]['id'], 1)
        self.assertEqual(result['elements'][0]['type'], "button")
        self.assertEqual(result['elements'][0]['text'], "Test")
        self.assertEqual(result['elements'][0]['bounds']['x'], 10)
        self.assertEqual(result['elements'][0]['bounds']['y'], 20)
        self.assertEqual(result['elements'][0]['confidence'], 0.85)
        self.assertEqual(result['elements'][0]['center'], [35, 35])


@unittest.skipIf(not MODULES_AVAILABLE, "Required modules not available")
class TestSemanticToUIMapper(unittest.TestCase):
    """Test semantic role to UI type mapping."""

    def test_basic_mapping(self):
        """Test basic semantic role mapping."""
        # Test some common mappings
        self.assertEqual(
            map_semantic_role_to_ui_type(SemanticRole.BUTTON),
            UIElementType.BUTTON
        )
        self.assertEqual(
            map_semantic_role_to_ui_type(SemanticRole.TEXT),
            UIElementType.TEXT
        )
        self.assertEqual(
            map_semantic_role_to_ui_type(SemanticRole.TEXTBOX),
            UIElementType.TEXTBOX
        )
        self.assertEqual(
            map_semantic_role_to_ui_type(SemanticRole.CHECKBOX),
            UIElementType.CHECKBOX
        )
        self.assertEqual(
            map_semantic_role_to_ui_type(SemanticRole.IMAGE),
            UIElementType.IMAGE
        )
        self.assertEqual(
            map_semantic_role_to_ui_type(SemanticRole.WINDOW),
            UIElementType.WINDOW
        )

    def test_reverse_mapping(self):
        """Test reverse mapping."""
        self.assertEqual(
            map_ui_type_to_semantic_role(UIElementType.BUTTON),
            SemanticRole.BUTTON
        )
        self.assertEqual(
            map_ui_type_to_semantic_role(UIElementType.TEXT),
            SemanticRole.TEXT
        )
        self.assertEqual(
            map_ui_type_to_semantic_role(UIElementType.TEXTBOX),
            SemanticRole.TEXTBOX
        )
        self.assertEqual(
            map_ui_type_to_semantic_role(UIElementType.CHECKBOX),
            SemanticRole.CHECKBOX
        )

    def test_unknown_role(self):
        """Test handling of unknown roles."""
        # Create a mock unknown role
        class MockRole(str):
            pass

        mock_role = MockRole("unknown_role")
        # This should not crash and return UNKNOWN
        # Note: In practice, the function expects SemanticRole enum
        # so we test with actual unknown enum values if they exist
        pass


@unittest.skipIf(not MODULES_AVAILABLE, "Required modules not available")
class TestVisualHierarchy(unittest.TestCase):
    """Test visual hierarchy detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.detector = VisualHierarchyDetector()

    def test_containment_detection(self):
        """Test detection of containment relationships."""
        # Create parent element (large rectangle)
        parent = UIElement(
            id=1,
            type=UIElementType.WINDOW,
            text="Window",
            bounds=BoundingBox(0, 0, 200, 150),
            confidence=0.9
        )

        # Create child element (small rectangle inside parent)
        child = UIElement(
            id=2,
            type=UIElementType.BUTTON,
            text="OK",
            bounds=BoundingBox(50, 50, 60, 30),  # Inside parent
            confidence=0.8
        )

        hierarchy = self.detector.detect_hierarchy([parent, child])

        # Should detect containment relationship
        self.assertGreater(len(hierarchy.relations), 0)

        # Find the containment relation
        containment_relations = [
            rel for rel in hierarchy.relations
            if rel.relation_type == 'contains'
        ]
        self.assertGreaterEqual(len(containment_relations), 1)

        # Check that parent->child relationship exists
        parent_to_child = [
            rel for rel in containment_relations
            if rel.parent_id == 1 and rel.child_id == 2
        ]
        self.assertGreaterEqual(len(parent_to_child), 1)

    def test_labeling_detection(self):
        """Test detection of labeling relationships."""
        # Create label element
        label = UIElement(
            id=1,
            type=UIElementType.LABEL,
            text="Username:",
            bounds=BoundingBox(10, 10, 80, 20),
            confidence=0.9
        )

        # Create input element to the right of label
        input_elem = UIElement(
            id=2,
            type=UIElementType.TEXTBOX,
            text="",
            bounds=BoundingBox(100, 10, 120, 25),
            confidence=0.85
        )

        hierarchy = self.detector.detect_hierarchy([label, input_elem])

        # Should detect labeling relationship
        labeling_relations = [
            rel for rel in hierarchy.relations
            if rel.relation_type == 'labeled_by'
        ]
        self.assertGreaterEqual(len(labeling_relations), 1)

        # Check that label->input relationship exists
        label_to_input = [
            rel for rel in labeling_relations
            if rel.parent_id == 1 and rel.child_id == 2
        ]
        self.assertGreaterEqual(len(label_to_input), 1)

    def test_get_children_and_parent(self):
        """Test getting children and parents."""
        parent = UIElement(
            id=1,
            type=UIElementType.WINDOW,
            text="Window",
            bounds=BoundingBox(0, 0, 200, 150),
            confidence=0.9
        )

        child1 = UIElement(
            id=2,
            type=UIElementType.BUTTON,
            text="Button 1",
            bounds=BoundingBox(20, 20, 60, 30),
            confidence=0.8
        )

        child2 = UIElement(
            id=3,
            type=UIElementType.BUTTON,
            text="Button 2",
            bounds=BoundingBox(100, 20, 60, 30),
            confidence=0.8
        )

        hierarchy = self.detector.detect_hierarchy([parent, child1, child2])

        # Manually add a containment relation for testing
        # (In real scenario, detector would find this based on geometry)
        hierarchy.relations.append(
            HierarchyRelation(parent_id=1, child_id=2, relation_type='contains', confidence=0.9)
        )
        hierarchy.relations.append(
            HierarchyRelation(parent_id=1, child_id=3, relation_type='contains', confidence=0.9)
        )

        # Test get_children
        children = hierarchy.get_children(1)
        self.assertEqual(len(children), 2)
        child_ids = [c.id for c in children]
        self.assertIn(2, child_ids)
        self.assertIn(3, child_ids)

        # Test get_parent
        parent_of_2 = hierarchy.get_parent(2)
        self.assertIsNotNone(parent_of_2)
        self.assertEqual(parent_of_2.id, 1)

        parent_of_3 = hierarchy.get_parent(3)
        self.assertIsNotNone(parent_of_3)
        self.assertEqual(parent_of_3.id, 1)

        # Test get_ancestors
        ancestors_of_2 = hierarchy.get_ancestors(2)
        self.assertEqual(len(ancestors_of_2), 1)
        self.assertEqual(ancestors_of_2[0].id, 1)

        # Test get_descendants
        descendants_of_1 = hierarchy.get_descendants(1)
        self.assertEqual(len(descendants_of_1), 2)
        descendant_ids = [d.id for d in descendants_of_1]
        self.assertIn(2, descendant_ids)
        self.assertIn(3, descendant_ids)


if __name__ == '__main__':
    unittest.main()