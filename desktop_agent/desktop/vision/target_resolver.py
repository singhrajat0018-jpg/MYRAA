"""
MYRAA Vision V3
Target Resolver

Resolves natural language descriptions to actionable UI targets.
Builds upon EPIC-14A perception architecture (ScreenState, UIElement).
"""

from __future__ import annotations

import time
import re
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field

from .screen_state import ScreenState, UIElement, BoundingBox, ActiveWindow
from .ui_models import UIElementType, InteractiveType
from .interaction_target import InteractionTarget
from .text_normalizer import (
    normalize_text,
    get_normalized_form,
    is_synonym_match,
    HINDI_ORDINAL_MAP,
    ENGLISH_ORDINAL_MAP,
    ORDINAL_MAP,
    extract_ordinal
)
from .ordinal_resolver import OrdinalResolver
from .target_resolution_result import TargetResolutionResult, TargetResolutionStatus


@dataclass
class TargetResolutionContext:
    """
    Context information for target resolution.

    Provides application/window context and temporal information
    to improve resolution accuracy.
    """
    active_window: Optional[ActiveWindow] = None
    application: str = ""
    timestamp: float = field(default_factory=time.time)
    max_target_age: float = 30.0  # Maximum age in seconds for target validity


class TargetResolver:
    """
    Resolves natural language descriptions to actionable UI targets.

    Builds upon EPIC-14A perception architecture:
    - Uses ScreenState for structured desktop understanding
    - Works with UIElement objects (bounds, center, text, confidence, etc.)
    - Reuses existing perception layer - no duplicate perception/OCR/coordinate systems
    - Resolution-only: produces targets but executes zero actions

    Resolution strategies (in priority order):
    1. Exact text match
    2. Normalized/synonym text match
    3. Role/type match
    4. Ordinal references (first/second/pehla wala)
    5. Spatial references (above/below/left/right)
    6. Contextual references (application/window)
    7. Hybrid combinations
    """

    def __init__(self):
        """Initialize the target resolver."""
        self.ordinal_resolver = OrdinalResolver()
        self._last_resolution_time: float = 0.0
        self._resolution_cache: Dict[str, TargetResolutionResult] = {}
        self._cache_timeout: float = 5.0  # Cache resolutions for 5 seconds

    def resolve_target(
        self,
        description: str,
        screen_state: ScreenState,
        context: Optional[TargetResolutionContext] = None
    ) -> TargetResolutionResult:
        """
        Resolve a target description against the current screen state.

        Args:
            description: Natural language description of target (e.g., "search bar", "first video")
            screen_state: Current structured perception of desktop
            context: Optional context information (application, window, etc.)

        Returns:
            TargetResolutionResult with status, target, confidence, and reasoning
        """
        # Input validation
        if not description or not screen_state:
            return TargetResolutionResult(
                status=TargetResolutionStatus.UNRESOLVED,
                reason="Invalid input: description or screen_state is empty"
            )

        if not screen_state.elements:
            return TargetResolutionResult(
                status=TargetResolutionStatus.UNRESOLVED,
                reason="No UI elements detected in screen state"
            )

        # Check cache first
        cache_key = f"{description}:{screen_state.timestamp}"
        current_time = time.time()
        if (current_time - self._last_resolution_time < self._cache_timeout and
            cache_key in self._resolution_cache):
            cached_result = self._resolution_cache[cache_key]
            # Return cached result if target is still valid
            if cached_result.target and cached_result.target.is_valid(context.max_target_age if context else 30.0):
                return cached_result

        # Use provided context or create default
        if context is None:
            context = TargetResolutionContext(
                active_window=screen_state.active_window,
                application=screen_state.active_window.application if screen_state.active_window else "",
                timestamp=screen_state.timestamp
            )

        # Start resolution process
        start_time = time.time()

        # Step 1: Filter elements by active window (if context specifies)
        candidates = self._filter_by_active_window(screen_state.elements, context)

        if not candidates:
            return TargetResolutionResult(
                status=TargetResolutionStatus.UNRESOLVED,
                reason="No elements found in active window context",
                timestamp=current_time
            )

        # Step 2: Try exact text match first (highest confidence)
        exact_result = self._try_exact_match(description, candidates, context)
        if exact_result.is_successful() and exact_result.confidence > 0.9:
            self._cache_result(cache_key, exact_result)
            return exact_result

        # Step 3: Try normalized/synonym match
        normalized_result = self._try_normalized_match(description, candidates, context)
        if normalized_result.is_successful() and normalized_result.confidence > 0.8:
            # Only use if better than exact match or exact match failed
            if not exact_result.is_successful() or normalized_result.confidence > exact_result.confidence:
                self._cache_result(cache_key, normalized_result)
                return normalized_result

        # Step 4: Try role/type match
        role_result = self._try_role_match(description, candidates, context)
        if role_result.is_successful() and role_result.confidence > 0.7:
            # Only use if better than previous matches
            if (not exact_result.is_successful() or role_result.confidence > exact_result.confidence) and \
               (not normalized_result.is_successful() or role_result.confidence > normalized_result.confidence):
                self._cache_result(cache_key, role_result)
                return role_result

        # Step 5: Try ordinal references
        ordinal_result = self._try_ordinal_match(description, candidates, context)
        if ordinal_result.is_successful():
            self._cache_result(cache_key, ordinal_result)
            return ordinal_result

        # Step 6: Try spatial references
        spatial_result = self._try_spatial_match(description, candidates, context)
        if spatial_result.is_successful():
            self._cache_result(cache_key, spatial_result)
            return spatial_result

        # Step 7: Try contextual references
        contextual_result = self._try_contextual_match(description, candidates, context)
        if contextual_result.is_successful():
            self._cache_result(cache_key, contextual_result)
            return contextual_result

        # Step 8: Hybrid approach - combine multiple signals
        hybrid_result = self._try_hybrid_match(description, candidates, context)
        if hybrid_result.is_successful():
            self._cache_result(cache_key, hybrid_result)
            return hybrid_result

        # If we got here, no clear winner - return best candidate with explanation
        # Determine best result from attempts
        results = [exact_result, normalized_result, role_result, ordinal_result,
                  spatial_result, contextual_result, hybrid_result]
        successful_results = [r for r in results if r.is_successful()]

        if successful_results:
            # Return the result with highest confidence
            best_result = max(successful_results, key=lambda r: r.confidence)
            self._cache_result(cache_key, best_result)
            return best_result
        else:
            # No successful matches - return unresolved with best effort info
            best_confidence = max((r.confidence for r in results), default=0.0)
            reason = "No confident match found"
            if best_confidence > 0.1:
                reason = f"Low confidence matches found (best: {best_confidence:.2f})"

            unresolved_result = TargetResolutionResult(
                status=TargetResolutionStatus.UNRESOLVED,
                confidence=best_confidence,
                reason=reason,
                timestamp=current_time
            )
            self._cache_result(cache_key, unresolved_result)
            return unresolved_result

    def _filter_by_active_window(self, elements: List[UIElement], context: TargetResolutionContext) -> List[UIElement]:
        """Filter elements to only those in the active application/window if context specifies."""
        # If no specific application context, return all elements
        if not context.application:
            return elements

        # Filter by application context (simplified - in practice would check element metadata/window)
        # For now, return all elements since we don't have application tracking per element
        # This could be enhanced with window/element association from perception layer
        return elements

    def _try_exact_match(
        self,
        description: str,
        candidates: List[UIElement],
        context: TargetResolutionContext
    ) -> TargetResolutionResult:
        """Try exact text match (case-sensitive)."""
        if not description:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        matches = []
        for elem in candidates:
            if elem.text == description:
                matches.append(elem)

        if len(matches) == 1:
            # Single exact match - highest confidence
            target = self._create_interaction_target(
                matches[0],
                "exact_text_match",
                f"Exact text match: '{description}'",
                context
            )
            return TargetResolutionResult(
                status=TargetResolutionStatus.RESOLVED,
                target=target,
                confidence=0.95,
                reason="Exact text match found",
                resolution_method="exact_text_match",
                timestamp=time.time()
            )
        elif len(matches) > 1:
            # Multiple exact matches - ambiguous
            targets = [
                self._create_interaction_target(
                    elem,
                    "exact_text_match",
                    f"Exact text match: '{description}' (ambiguous)",
                    context
                )
                for elem in matches
            ]
            return TargetResolutionResult(
                status=TargetResolutionStatus.AMBIGUOUS,
                candidates=targets,
                confidence=0.9,  # High confidence but ambiguous
                reason=f"Multiple exact matches found for '{description}'",
                resolution_method="exact_text_match",
                timestamp=time.time()
            )
        else:
            # No exact matches
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

    def _try_normalized_match(
        self,
        description: str,
        candidates: List[UIElement],
        context: TargetResolutionContext
    ) -> TargetResolutionResult:
        """Try normalized/synonym text match."""
        if not description:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        normalized_desc = normalize_text(description)
        if not normalized_desc:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        matches = []
        for elem in candidates:
            normalized_elem_text = normalize_text(elem.text)
            if normalized_elem_text == normalized_desc:
                matches.append(elem)
            # Also check synonym mappings
            elif is_synonym_match(description, elem.text):
                matches.append(elem)

        if len(matches) == 1:
            # Single normalized match
            target = self._create_interaction_target(
                matches[0],
                "normalized_text_match",
                f"Normalized text match: '{description}' -> '{normalized_desc}'",
                context
            )
            return TargetResolutionResult(
                status=TargetResolutionStatus.RESOLVED,
                target=target,
                confidence=0.85,
                reason=f"Normalized text match: '{description}'",
                resolution_method="normalized_text_match",
                timestamp=time.time()
            )
        elif len(matches) > 1:
            # Multiple normalized matches - ambiguous
            targets = [
                self._create_interaction_target(
                    elem,
                    "normalized_text_match",
                    f"Normalized text match: '{description}' (ambiguous)",
                    context
                )
                for elem in matches
            ]
            return TargetResolutionResult(
                status=TargetResolutionStatus.AMBIGUOUS,
                candidates=targets,
                confidence=0.8,
                reason=f"Multiple normalized matches for '{description}'",
                resolution_method="normalized_text_match",
                timestamp=time.time()
            )
        else:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

    def _try_role_match(
        self,
        description: str,
        candidates: List[UIElement],
        context: TargetResolutionContext
    ) -> TargetResolutionResult:
        """Try role/UI element type match."""
        if not description:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        # Get normalized form to determine target type
        target_type = get_normalized_form(description)

        # Map normalized text to UI element types
        type_mapping = {
            # Input types
            "SEARCH_INPUT": [UIElementType.TEXTBOX, UIElementType.TEXTAREA],
            "TEXT_INPUT": [UIElementType.TEXTBOX, UIElementType.TEXTAREA],
            "PASSWORD_INPUT": [UIElementType.TEXTBOX],

            # Button types
            "PLAY_CONTROL": [UIElementType.BUTTON],
            "PAUSE_CONTROL": [UIElementType.BUTTON],
            "STOP_CONTROL": [UIElementType.BUTTON],
            "SUBMIT_BUTTON": [UIElementType.BUTTON],
            "CANCEL_BUTTON": [UIElementType.BUTTON],
            "OK_BUTTON": [UIElementType.BUTTON],
            "CLOSE_BUTTON": [UIElementType.BUTTON],
            "MENU_BUTTON": [UIElementType.BUTTON],
            "HOME_BUTTON": [UIElementType.BUTTON],
            "BACK_BUTTON": [UIElementType.BUTTON],
            "FORWARD_BUTTON": [UIElementType.BUTTON],
            "REFRESH_BUTTON": [UIElementType.BUTTON],
            "DOWNLOAD_BUTTON": [UIElementType.BUTTON],
            "UPLOAD_BUTTON": [UIElementType.BUTTON],
            "SAVE_BUTTON": [UIElementType.BUTTON],
            "OPEN_BUTTON": [UIElementType.BUTTON],
            "NEW_BUTTON": [UIElementType.BUTTON],
            "DELETE_BUTTON": [UIElementType.BUTTON],
            "EDIT_BUTTON": [UIElementType.BUTTON],
            "COPY_BUTTON": [UIElementType.BUTTON],
            "PASTE_BUTTON": [UIElementType.BUTTON],
            "SEARCH_BUTTON": [UIElementType.BUTTON],
            "FILTER_BUTTON": [UIElementType.BUTTON],
            "SORT_BUTTON": [UIElementType.BUTTON],

            # Generic
            "BUTTON": [UIElementType.BUTTON],
            "INPUT": [UIElementType.TEXTBOX, UIElementType.TEXTAREA],
            "TEXT": [UIElementType.TEXT],
            "IMAGE": [UIElementType.IMAGE],
            "ICON": [UIElementType.ICON],
            "LINK": [UIElementType.LINK],
            "CHECKBOX": [UIElementType.CHECKBOX],
            "RADIO_BUTTON": [UIElementType.RADIO],
            "DROPDOWN": [UIElementType.DROPDOWN],
            "TAB": [UIElementType.TAB]
        }

        target_ui_types = type_mapping.get(target_type.value, [])

        if not target_ui_types:
            # Fallback to interactive elements if no specific type mapping
            target_ui_types = [t for t in UIElementType
                             if InteractiveType.NONE != self._get_interactive_type(t)]

        matches = []
        for elem in candidates:
            if elem.type in target_ui_types:
                matches.append(elem)

        if len(matches) == 1:
            target = self._create_interaction_target(
                matches[0],
                "role_match",
                f"Role match: {description} -> {matches[0].type.value}",
                context
            )
            return TargetResolutionResult(
                status=TargetResolutionStatus.RESOLVED,
                target=target,
                confidence=0.75,
                reason=f"Role match: {description}",
                resolution_method="role_match",
                timestamp=time.time()
            )
        elif len(matches) > 1:
            # Role match with multiple candidates - try to disambiguate with text similarity
            # Score by text similarity to description
            scored_matches = []
            for elem in matches:
                # Simple similarity score based on common words
                desc_words = set(description.lower().split())
                elem_words = set(elem.text.lower().split())
                if desc_words and elem_words:
                    similarity = len(desc_words & elem_words) / len(desc_words | elem_words)
                else:
                    similarity = 0.0
                scored_matches.append((elem, similarity))

            # Sort by similarity score
            scored_matches.sort(key=lambda x: x[1], reverse=True)

            if scored_matches and scored_matches[0][1] > 0.3:  # Minimum similarity threshold
                best_elem, best_score = scored_matches[0]
                # Check if second best is significantly different to avoid ambiguity
                if len(scored_matches) < 2 or scored_matches[0][1] - scored_matches[1][1] > 0.2:
                    target = self._create_interaction_target(
                        best_elem,
                        "role_match",
                        f"Role + text match: {description}",
                        context
                    )
                    return TargetResolutionResult(
                        status=TargetResolutionStatus.RESOLVED,
                        target=target,
                        confidence=0.7 + (best_score * 0.2),  # 0.7-0.9 range
                        reason=f"Role match with text similarity: {description}",
                        resolution_method="role_match",
                        timestamp=time.time()
                    )

            # Too similar or no clear winner - ambiguous
            targets = [
                self._create_interaction_target(
                    elem,
                    "role_match",
                    f"Role match: {description} (ambiguous)",
                    context
                )
                for elem in matches[:3]  # Limit candidates returned
            ]
            return TargetResolutionResult(
                status=TargetResolutionStatus.AMBIGUOUS,
                candidates=targets,
                confidence=0.7,
                reason=f"Multiple role matches for '{description}'",
                resolution_method="role_match",
                timestamp=time.time()
            )
        else:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

    def _try_ordinal_match(
        self,
        description: str,
        candidates: List[UIElement],
        context: TargetResolutionContext
    ) -> TargetResolutionResult:
        """Try ordinal reference match (first, second, pehla wala, etc.)."""
        ordinal_num = extract_ordinal(description)
        if ordinal_num is None:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        # Remove ordinal words from description to get base description
        base_desc = description.lower()
        for ordinal_word in ORDINAL_MAP.keys():
            base_desc = base_desc.replace(ordinal_word, "").strip()
        # Clean up extra spaces
        base_desc = re.sub(r'\s+', ' ', base_desc).strip()

        # If we have a base description, filter candidates by it first
        if base_desc:
            filtered_candidates = []
            for elem in candidates:
                if is_synonym_match(base_desc, elem.text) or normalize_text(base_desc) in normalize_text(elem.text):
                    filtered_candidates.append(elem)
            candidates_to_use = filtered_candidates if filtered_candidates else candidates
        else:
            candidates_to_use = candidates

        # Use ordinal resolver to get the specific element
        ordinal_result_num, filtered_candidates = self.ordinal_resolver.resolve_ordinal_from_position(
            description,
            candidates_to_use
        )

        if ordinal_result_num is None:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        if not filtered_candidates:
            return TargetResolutionResult(
                status=TargetResolutionStatus.UNRESOLVED,
                reason=f"Ordinal {ordinal_num} out of range (only {len(candidates_to_use)} candidates)"
            )

        if len(filtered_candidates) == 1:
            target = self._create_interaction_target(
                filtered_candidates[0],
                "ordinal_match",
                f"Ordinal match: {description} -> {ordinal_num}th element",
                context
            )
            # Confidence based on how specific the ordinal reference was
            confidence = 0.8
            if base_desc:  # Had both ordinal and descriptive text
                confidence = 0.85

            return TargetResolutionResult(
                status=TargetResolutionStatus.RESOLVED,
                target=target,
                confidence=confidence,
                reason=f"Ordinal match: {description}",
                resolution_method="ordinal_match",
                timestamp=time.time()
            )
        else:
            # Shouldn't happen with our resolver logic, but handle just in case
            targets = [
                self._create_interaction_target(
                    elem,
                    "ordinal_match",
                    f"Ordinal match: {description} (ambiguous)",
                    context
                )
                for elem in filtered_candidates[:3]
            ]
            return TargetResolutionResult(
                status=TargetResolutionStatus.AMBIGUOUS,
                candidates=targets,
                confidence=0.75,
                reason=f"Ambiguous ordinal match for '{description}'",
                resolution_method="ordinal_match",
                timestamp=time.time()
            )

    def _try_spatial_match(
        self,
        description: str,
        candidates: List[UIElement],
        context: TargetResolutionContext
    ) -> TargetResolutionResult:
        """Try spatial reference match (above/below/left/right)."""
        desc_lower = description.lower()

        # Check for spatial references
        spatial_patterns = {
            'above': ['above', 'up', 'top', 'higher'],
            'below': ['below', 'down', 'bottom', 'lower'],
            'left': ['left', 'left side'],
            'right': ['right', 'right side']
        }

        detected_direction = None
        reference_description = None

        for direction, patterns in spatial_patterns.items():
            for pattern in patterns:
                if pattern in desc_lower:
                    detected_direction = direction
                    # Extract the reference description by removing spatial words
                    reference_description = desc_lower.replace(pattern, "").strip()
                    # Clean up extra words like "the", "one", etc.
                    reference_description = re.sub(r'\b(the|one|wala|waala)\b', '', reference_description).strip()
                    reference_description = re.sub(r'\s+', ' ', reference_description).strip()
                    break
            if detected_direction:
                break

        if not detected_direction:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        # If we have a reference description, find elements matching it
        if reference_description:
            # Find candidate reference elements
            ref_elements = []
            for elem in candidates:
                if is_synonym_match(reference_description, elem.text) or \
                   normalize_text(reference_description) in normalize_text(elem.text):
                    ref_elements.append(elem)

            if not ref_elements:
                return TargetResolutionResult(
                    status=TargetResolutionStatus.UNRESOLVED,
                    reason=f"Reference element '{reference_description}' not found"
                )

            # Use the first reference element (could be enhanced to handle multiple refs)
            ref_elem = ref_elements[0]
            ref_bounds = ref_elem.bounds
        else:
            # Pure spatial reference like "top one", "bottom one" - use screen edges
            screen_state = getattr(candidates[0], '_screen_state', None) if candidates else None
            if not screen_state:
                # Fallback: use geometric center of all candidates
                if candidates:
                    avg_x = sum(elem.bounds.center[0] for elem in candidates) / len(candidates)
                    avg_y = sum(elem.bounds.center[1] for elem in candidates) / len(candidates)
                    ref_bounds = BoundingBox(int(avg_x), int(avg_y), 1, 1)
                else:
                    return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED, reason="No candidates for spatial reference")
            else:
                # Use screen bounds
                screen_bounds = BoundingBox(0, 0, screen_state.screen_width, screen_state.screen_height)
                ref_bounds = screen_bounds

        # Find candidates that match the spatial relationship
        spatial_matches = []
        for elem in candidates:
            elem_bounds = elem.bounds
            ref_center_x, ref_center_y = ref_bounds.center

            if detected_direction == 'above':
                # Element is above reference if its bottom is above reference's top
                if elem_bounds.bottom < ref_bounds.y:
                    spatial_matches.append(elem)
            elif detected_direction == 'below':
                # Element is below reference if its top is below reference's bottom
                if elem_bounds.y > ref_bounds.bottom:
                    spatial_matches.append(elem)
            elif detected_direction == 'left':
                # Element is left of reference if its right is left of reference's left
                if elem_bounds.right < ref_bounds.x:
                    spatial_matches.append(elem)
            elif detected_direction == 'right':
                # Element is right of reference if its left is right of reference's right
                if elem_bounds.x > ref_bounds.right:
                    spatial_matches.append(elem)

        if not spatial_matches:
            return TargetResolutionResult(
                status=TargetResolutionStatus.UNRESOLVED,
                reason=f"No elements found {detected_direction} of reference"
            )

        if len(spatial_matches) == 1:
            target = self._create_interaction_target(
                spatial_matches[0],
                "spatial_match",
                f"Spatial match: {description}",
                context
            )
            confidence = 0.75
            if reference_description:
                confidence = 0.8  # Higher confidence when we have both spatial and reference

            return TargetResolutionResult(
                status=TargetResolutionStatus.RESOLVED,
                target=target,
                confidence=confidence,
                reason=f"Spatial match: {description}",
                resolution_method="spatial_match",
                timestamp=time.time()
            )
        else:
            # Multiple spatial matches - ambiguous
            # Try to pick the closest one
            if reference_description:
                ref_center_x, ref_center_y = ref_bounds.center
                scored_matches = []
                for elem in spatial_matches:
                    elem_center_x, elem_center_y = elem.bounds.center
                    distance = ((elem_center_x - ref_center_x) ** 2 + (elem_center_y - ref_center_y) ** 2) ** 0.5
                    scored_matches.append((elem, distance))

                scored_matches.sort(key=lambda x: x[1])  # Sort by distance (closest first)
                best_elem, best_distance = scored_matches[0]

                # Check if second closest is significantly farther
                if len(scored_matches) < 2 or scored_matches[0][1] + 50 < scored_matches[1][1]:  # 50px threshold
                    target = self._create_interaction_target(
                        best_elem,
                        "spatial_match",
                        f"Spatial match: {description} (closest)",
                        context
                    )
                    return TargetResolutionResult(
                        status=TargetResolutionStatus.RESOLVED,
                        target=target,
                        confidence=0.7,
                        reason=f"Spatial match: {description} (closest element)",
                        resolution_method="spatial_match",
                        timestamp=time.time()
                    )

            # Return ambiguous result
            targets = [
                self._create_interaction_target(
                    elem,
                    "spatial_match",
                    f"Spatial match: {description} (ambiguous)",
                    context
                )
                for elem in spatial_matches[:3]
            ]
            return TargetResolutionResult(
                status=TargetResolutionStatus.AMBIGUOUS,
                candidates=targets,
                confidence=0.7,
                reason=f"Multiple spatial matches for '{description}'",
                resolution_method="spatial_match",
                timestamp=time.time()
            )

    def _try_contextual_match(
        self,
        description: str,
        candidates: List[UIElement],
        context: TargetResolutionContext
    ) -> TargetResolutionResult:
        """Try contextual reference match (there, this one, that one)."""
        desc_lower = description.lower().strip()

        contextual_indicators = ['there', 'this one', 'that one', 'it']

        is_contextual = any(indicator in desc_lower for indicator in contextual_indicators)
        if not is_contextual:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        # For now, treat contextual references as requesting the most prominent/interactive element
        # In a full implementation, this would refer to previously resolved targets
        # For this implementation, we'll fall back to general matching with lower confidence

        # Remove contextual words to get base description
        base_desc = desc_lower
        for indicator in contextual_indicators:
            base_desc = base_desc.replace(indicator, "").strip()
        base_desc = re.sub(r'\s+', ' ', base_desc).strip()

        if base_desc:
            # Try to match the base description
            return self._try_normalized_match(base_desc, candidates, context)
        else:
            # Pure contextual reference - return most likely interactive element
            interactive_elements = [
                elem for elem in candidates
                if elem.interactive != InteractiveType.NONE
            ]

            if not interactive_elements:
                return TargetResolutionResult(
                    status=TargetResolutionStatus.UNRESOLVED,
                    reason="No interactive elements found for contextual reference"
                )

            if len(interactive_elements) == 1:
                target = self._create_interaction_target(
                    interactive_elements[0],
                    "contextual_match",
                    f"Contextual match: {description}",
                    context
                )
                return TargetResolutionResult(
                    status=TargetResolutionStatus.RESOLVED,
                    target=target,
                    confidence=0.6,  # Lower confidence for pure contextual
                    reason=f"Contextual match: {description}",
                    resolution_method="contextual_match",
                    timestamp=time.time()
                )
            else:
                # Multiple interactive elements - ambiguous
                targets = [
                    self._create_interaction_target(
                        elem,
                        "contextual_match",
                        f"Contextual match: {description} (ambiguous)",
                        context
                    )
                    for elem in interactive_elements[:3]
                ]
                return TargetResolutionResult(
                    status=TargetResolutionStatus.AMBIGUOUS,
                    candidates=targets,
                    confidence=0.6,
                    reason=f"Multiple interactive elements for contextual reference '{description}'",
                    resolution_method="contextual_match",
                    timestamp=time.time()
                )

    def _try_hybrid_match(
        self,
        description: str,
        candidates: List[UIElement],
        context: TargetResolutionContext
    ) -> TargetResolutionResult:
        """Try hybrid match combining multiple signals."""
        # This is a simplified hybrid approach - in practice could be more sophisticated

        # Try combining text match with role match
        if not description:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        # Score each candidate based on multiple factors
        scored_candidates = []

        for elem in candidates:
            score = 0.0
            reasons = []

            # Text similarity score (0-0.4)
            if elem.text and description:
                desc_lower = description.lower()
                elem_lower = elem.text.lower()
                if desc_lower in elem_lower or elem_lower in desc_lower:
                    text_score = 0.4
                    reasons.append("text containment")
                else:
                    # Fuzzy similarity based on common words
                    desc_words = set(desc_lower.split())
                    elem_words = set(elem_lower.split())
                    if desc_words and elem_words:
                        jaccard = len(desc_words & elem_words) / len(desc_words | elem_words)
                        text_score = 0.4 * jaccard
                        if jaccard > 0.2:
                            reasons.append(f"text similarity ({jaccard:.2f})")
                    else:
                        text_score = 0.0
            else:
                text_score = 0.0

            score += text_score

            # Role compatibility score (0-0.3)
            target_type = get_normalized_form(description)
            type_mapping = {
                "SEARCH_INPUT": [UIElementType.TEXTBOX, UIElementType.TEXTAREA],
                "TEXT_INPUT": [UIElementType.TEXTBOX, UIElementType.TEXTAREA],
                "PASSWORD_INPUT": [UIElementType.TEXTBOX],
                "PLAY_CONTROL": [UIElementType.BUTTON],
                "PAUSE_CONTROL": [UIElementType.BUTTON],
                "STOP_CONTROL": [UIElementType.BUTTON],
                "SUBMIT_BUTTON": [UIElementType.BUTTON],
                "CANCEL_BUTTON": [UIElementType.BUTTON],
                "OK_BUTTON": [UIElementType.BUTTON],
                "CLOSE_BUTTON": [UIElementType.BUTTON],
                "MENU_BUTTON": [UIElementType.BUTTON],
                "HOME_BUTTON": [UIElementType.BUTTON],
                "BACK_BUTTON": [UIElementType.BUTTON],
                "FORWARD_BUTTON": [UIElementType.BUTTON],
                "REFRESH_BUTTON": [UIElementType.BUTTON],
                "DOWNLOAD_BUTTON": [UIElementType.BUTTON],
                "UPLOAD_BUTTON": [UIElementType.BUTTON],
                "SAVE_BUTTON": [UIElementType.BUTTON],
                "OPEN_BUTTON": [UIElementType.BUTTON],
                "NEW_BUTTON": [UIElementType.BUTTON],
                "DELETE_BUTTON": [UIElementType.BUTTON],
                "EDIT_BUTTON": [UIElementType.BUTTON],
                "COPY_BUTTON": [UIElementType.BUTTON],
                "PASTE_BUTTON": [UIElementType.BUTTON],
                "SEARCH_BUTTON": [UIElementType.BUTTON],
                "FILTER_BUTTON": [UIElementType.BUTTON],
                "SORT_BUTTON": [UIElementType.BUTTON],
                "BUTTON": [UIElementType.BUTTON],
                "INPUT": [UIElementType.TEXTBOX, UIElementType.TEXTAREA],
                "TEXT": [UIElementType.TEXT],
                "IMAGE": [UIElementType.IMAGE],
                "ICON": [UIElementType.ICON],
                "LINK": [UIElementType.LINK],
                "CHECKBOX": [UIElementType.CHECKBOX],
                "RADIO_BUTTON": [UIElementType.RADIO],
                "DROPDOWN": [UIElementType.DROPDOWN],
                "TAB": [UIElementType.TAB]
            }

            target_ui_types = type_mapping.get(target_type.value, [])
            if not target_ui_types:
                target_ui_types = [t for t in UIElementType
                                 if InteractiveType.NONE != self._get_interactive_type(t)]

            if elem.type in target_ui_types:
                role_score = 0.3
                reasons.append(f"role match ({elem.type.value})")
            elif elem.interactive != InteractiveType.NONE:
                role_score = 0.15  # Partial credit for being interactive
                reasons.append("interactive element")
            else:
                role_score = 0.0

            score += role_score

            # Confidence score from element itself (0-0.2)
            confidence_score = elem.confidence * 0.2
            if elem.confidence > 0.7:
                reasons.append(f"high element confidence ({elem.confidence:.2f})")

            score += confidence_score

            # Prefer visible, enabled elements (0-0.1)
            visibility_score = 0.0
            if elem.visible:
                visibility_score += 0.05
                reasons.append("visible")
            if elem.enabled:
                visibility_score += 0.05
                reasons.append("enabled")

            score += visibility_score

            scored_candidates.append((elem, score, ", ".join(reasons)))

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        if not scored_candidates:
            return TargetResolutionResult(status=TargetResolutionStatus.UNRESOLVED)

        best_elem, best_score, best_reasons = scored_candidates[0]

        # Check if we have a clear winner (significant gap to second place)
        if len(scored_candidates) > 1:
            second_score = scored_candidates[1][1]
            if best_score - second_score < 0.15:  # Less than 0.15 gap is ambiguous
                # Return ambiguous result with top candidates
                top_candidates = []
                for elem, score, reasons in scored_candidates[:3]:  # Top 3
                    target = self._create_interaction_target(
                        elem,
                        "hybrid_match",
                        f"Hybrid match: {description} ({reasons})",
                        context
                    )
                    top_candidates.append(target)

                return TargetResolutionResult(
                    status=TargetResolutionStatus.AMBIGUOUS,
                    candidates=top_candidates,
                    confidence=best_score,
                    reason=f"Hybrid match: {description} (ambiguous - top score: {best_score:.2f})",
                    resolution_method="hybrid_match",
                    timestamp=time.time()
                )

        # Clear winner - return resolved
        if best_score > 0.2:  # Minimum threshold for considering it a match
            target = self._create_interaction_target(
                best_elem,
                "hybrid_match",
                f"Hybrid match: {description} ({best_reasons})",
                context
            )
            return TargetResolutionResult(
                status=TargetResolutionStatus.RESOLVED,
                target=target,
                confidence=min(best_score, 0.9),  # Cap at 0.9 for hybrid
                reason=f"Hybrid match: {description}",
                resolution_method="hybrid_match",
                timestamp=time.time()
            )
        else:
            return TargetResolutionResult(
                status=TargetResolutionStatus.UNRESOLVED,
                confidence=best_score,
                reason=f"Low confidence hybrid match for '{description}' (score: {best_score:.2f})",
                timestamp=time.time()
            )

    def _create_interaction_target(
        self,
        ui_element: UIElement,
        resolution_method: str,
        reasoning: str,
        context: TargetResolutionContext
    ) -> InteractionTarget:
        """Create an InteractionTarget from a UIElement with resolution metadata."""
        return InteractionTarget(
            id=ui_element.id,
            type=ui_element.type,
            text=ui_element.text,
            confidence=ui_element.confidence,
            bounds=ui_element.bounds,
            clickable=ui_element.clickable,
            enabled=ui_element.enabled,
            visible=ui_element.visible,
            metadata=ui_element.metadata.copy(),

            # Resolution metadata
            resolution_method=resolution_method,
            reasoning=reasoning,

            # Validity tracking
            timestamp=time.time(),
            valid=True,

            # Context information
            active_window=context.active_window,
            application_context=context.application,

            # Target-specific properties
            center_point=ui_element.bounds.center,
            center_reason="geometric_center"
        )

    def _get_interactive_type(self, ui_type: UIElementType) -> InteractiveType:
        """Get InteractiveType from UIElementType (duplicated from UIElement for independence)."""
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

    def _cache_result(self, key: str, result: TargetResolutionResult) -> None:
        """Cache a resolution result."""
        self._resolution_cache[key] = result
        self._last_resolution_time = time.time()

        # Simple cache cleanup - remove old entries
        current_time = time.time()
        keys_to_delete = [
            k for k, v in self._resolution_cache.items()
            if current_time - v.timestamp > self._cache_timeout
        ]
        for k in keys_to_delete:
            del self._resolution_cache[k]

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._resolution_cache.clear()
        self._last_resolution_time = 0.0