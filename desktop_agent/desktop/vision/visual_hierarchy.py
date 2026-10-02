"""
MYRAA Vision V3
Visual Hierarchy

Lightweight visual hierarchy detection for UI elements.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .ui_models import BoundingBox
from .screen_state import UIElement
from .fusion_engine import SemanticNode, SemanticRole


@dataclass
class HierarchyRelation:
    """Represents a relationship between two UI elements."""
    parent_id: int
    child_id: int
    relation_type: str  # 'contains', 'aligned', 'grouped', 'labeled_by'
    confidence: float = 1.0


@dataclass
class VisualHierarchy:
    """Lightweight visual hierarchy of UI elements."""
    elements: List[UIElement] = field(default_factory=list)
    relations: List[HierarchyRelation] = field(default_factory=list)

    def get_children(self, parent_id: int) -> List[UIElement]:
        """Get direct children of an element."""
        child_ids = [rel.child_id for rel in self.relations if rel.parent_id == parent_id]
        return [elem for elem in self.elements if elem.id in child_ids]

    def get_parent(self, child_id: int) -> Optional[UIElement]:
        """Get direct parent of an element."""
        parent_ids = [rel.parent_id for rel in self.relations if rel.child_id == child_id]
        if parent_ids:
            return next((elem for elem in self.elements if elem.id == parent_ids[0]), None)
        return None

    def get_ancestors(self, element_id: int) -> List[UIElement]:
        """Get all ancestors of an element."""
        ancestors = []
        current = self.get_parent(element_id)
        while current:
            ancestors.append(current)
            current = self.get_parent(current.id)
        return ancestors

    def get_descendants(self, element_id: int) -> List[UIElement]:
        """Get all descendants of an element."""
        descendants = []
        to_process = self.get_children(element_id)

        while to_process:
            current = to_process.pop(0)
            descendants.append(current)
            to_process.extend(self.get_children(current.id))

        return descendants


class VisualHierarchyDetector:
    """
    Detects lightweight visual hierarchy relationships between UI elements.

    This detects basic containment and alignment relationships without
    building a full DOM-like tree.
    """

    def __init__(self):
        self.containment_threshold = 0.8  # 80% containment for parent-child
        self.alignment_threshold = 10     # 10 pixels for alignment detection
        self.proximity_threshold = 25     # 25 pixels for grouping

    def detect_hierarchy(self, elements: List[UIElement]) -> VisualHierarchy:
        """
        Detect visual hierarchy from a list of UI elements.

        Args:
            elements: List of UI elements to analyze

        Returns:
            VisualHierarchy with detected relationships
        """
        hierarchy = VisualHierarchy(elements=elements)

        # Detect containment relationships (parent-child)
        self._detect_containment(hierarchy)

        # Detect labeling relationships (label -> input)
        self._detect_labeling(hierarchy)

        # Detect grouping relationships (proximity-based)
        self._detect_grouping(hierarchy)

        return hierarchy

    def _detect_containment(self, hierarchy: VisualHierarchy) -> None:
        """Detect containment relationships (one element inside another)."""
        for i, parent_elem in enumerate(hierarchy.elements):
            for j, child_elem in enumerate(hierarchy.elements):
                if i == j:
                    continue

                # Check if child is contained within parent
                containment_ratio = self._calculate_containment_ratio(
                    parent_elem.bounds, child_elem.bounds
                )

                if containment_ratio >= self.containment_threshold:
                    # Avoid assigning multiple parents - assign to smallest container
                    existing_parent = hierarchy.get_parent(child_elem.id)
                    if existing_parent:
                        existing_container_ratio = self._calculate_containment_ratio(
                            existing_parent.bounds, child_elem.bounds
                        )
                        if containment_ratio <= existing_container_ratio:
                            continue  # Keep existing parent (better fit)

                    relation = HierarchyRelation(
                        parent_id=parent_elem.id,
                        child_id=child_elem.id,
                        relation_type='contains',
                        confidence=containment_ratio
                    )
                    hierarchy.relations.append(relation)

    def _detect_labeling(self, hierarchy: VisualHierarchy) -> None:
        """Detect labeling relationships (label associated with input)."""
        labels = [elem for elem in hierarchy.elements if elem.type.name in ('LABEL', 'TEXT')]
        inputs = [elem for elem in hierarchy.elements
                 if elem.type.name in ('TEXTBOX', 'TEXTAREA', 'COMBOBOX', 'CHECKBOX', 'RADIO')]

        for label in labels:
            best_input = None
            best_score = 0.0

            for inp in inputs:
                # Check if label is positioned to left or above input
                score = self._calculate_label_association_score(label, inp)
                if score > best_score and score > 0.3:  # Minimum threshold
                    best_score = score
                    best_input = inp

            if best_input:
                relation = HierarchyRelation(
                    parent_id=label.id,
                    child_id=best_input.id,
                    relation_type='labeled_by',
                    confidence=best_score
                )
                hierarchy.relations.append(relation)

    def _detect_grouping(self, hierarchy: VisualHierarchy) -> None:
        """Detect grouping based on proximity and alignment."""
        # Group elements that are close together and aligned
        for i, elem1 in enumerate(hierarchy.elements):
            for j, elem2 in enumerate(hierarchy.elements[i+1:], i+1):
                # Skip if already related
                if self._are_related(hierarchy, elem1.id, elem2.id):
                    continue

                # Check proximity
                distance = self._calculate_element_distance(elem1, elem2)
                if distance <= self.proximity_threshold:
                    # Check alignment
                    alignment_score = self._calculate_alignment_score(elem1, elem2)
                    if alignment_score > 0.5:
                        relation = HierarchyRelation(
                            parent_id=elem1.id,
                            child_id=elem2.id,
                            relation_type='grouped',
                            confidence=alignment_score * (1.0 - distance / self.proximity_threshold)
                        )
                        hierarchy.relations.append(relation)

    def _calculate_containment_ratio(self, parent_bounds: BoundingBox, child_bounds: BoundingBox) -> float:
        """Calculate how much child is contained within parent (0.0 to 1.0)."""
        # Calculate intersection
        intersection_x = max(parent_bounds.x, child_bounds.x)
        intersection_y = max(parent_bounds.y, child_bounds.y)
        intersection_width = min(parent_bounds.right, child_bounds.right) - intersection_x
        intersection_height = min(parent_bounds.bottom, child_bounds.bottom) - intersection_y

        if intersection_width <= 0 or intersection_height <= 0:
            return 0.0

        intersection_area = intersection_width * intersection_height
        child_area = child_bounds.width * child_bounds.height

        if child_area == 0:
            return 0.0

        return intersection_area / child_area

    def _calculate_label_association_score(self, label: UIElement, input_elem: UIElement) -> float:
        """Calculate likelihood that label is associated with input element."""
        score = 0.0

        # Position preference: label left of or above input
        if (label.bounds.right <= input_elem.bounds.x + self.alignment_threshold and
            abs(label.bounds.y - input_elem.bounds.y) <= self.alignment_threshold * 2):
            score += 0.4  # Label to the left
        elif (label.bounds.bottom <= input_elem.bounds.y + self.alignment_threshold and
              abs(label.bounds.x - input_elem.bounds.x) <= self.alignment_threshold * 2):
            score += 0.4  # Label above

        # Vertical alignment bonus
        label_center_y = label.bounds.y + label.bounds.height // 2
        input_center_y = input_elem.bounds.y + input_elem.bounds.height // 2
        vertical_align = 1.0 - min(abs(label_center_y - input_center_y) / 20.0, 1.0)
        score += vertical_align * 0.3

        # Size compatibility (labels shouldn't be enormously larger than inputs)
        label_area = label.bounds.width * label.bounds.height
        input_area = input_elem.bounds.width * input_elem.bounds.height
        if input_area > 0:
            size_ratio = min(label_area, input_area) / max(label_area, input_area)
            score += size_ratio * 0.2

        # Text content hint (if label looks like a field label)
        label_text = label.text.lower().strip()
        input_hints = ['name', 'email', 'password', 'search', 'username', 'phone', 'address']
        if any(hint in label_text for hint in input_hints):
            score += 0.2

        return min(score, 1.0)

    def _are_related(self, hierarchy: VisualHierarchy, id1: int, id2: int) -> bool:
        """Check if two elements already have a relationship."""
        for rel in hierarchy.relations:
            if (rel.parent_id == id1 and rel.child_id == id2) or \
               (rel.parent_id == id2 and rel.child_id == id1):
                return True
        return False

    def _calculate_element_distance(self, elem1: UIElement, elem2: UIElement) -> float:
        """Calculate distance between centers of two elements."""
        center1 = elem1.bounds.center
        center2 = elem2.bounds.center
        return ((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2) ** 0.5

    def _calculate_alignment_score(self, elem1: UIElement, elem2: UIElement) -> float:
        """Calculate alignment score between two elements (0.0 to 1.0)."""
        # Check horizontal alignment (tops, bottoms, centers aligned)
        h_align = 0.0
        if abs(elem1.bounds.y - elem2.bounds.y) <= self.alignment_threshold:
            h_align = 1.0  # Top aligned
        elif abs(elem1.bounds.bottom - elem2.bounds.bottom) <= self.alignment_threshold:
            h_align = 1.0  # Bottom aligned
        elif abs((elem1.bounds.y + elem1.bounds.height//2) -
                (elem2.bounds.y + elem2.bounds.height//2)) <= self.alignment_threshold:
            h_align = 1.0  # Center aligned

        # Check vertical alignment (lefts, rights, centers aligned)
        v_align = 0.0
        if abs(elem1.bounds.x - elem2.bounds.x) <= self.alignment_threshold:
            v_align = 1.0  # Left aligned
        elif abs(elem1.bounds.right - elem2.bounds.right) <= self.alignment_threshold:
            v_align = 1.0  # Right aligned
        elif abs((elem1.bounds.x + elem1.bounds.width//2) -
                (elem2.bounds.x + elem2.bounds.width//2)) <= self.alignment_threshold:
            v_align = 1.0  # Center aligned

        return max(h_align, v_align)


# Global instance for use by screen state builder
visual_hierarchy_detector = VisualHierarchyDetector()