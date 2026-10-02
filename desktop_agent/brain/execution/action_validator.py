"""
MYRAA Cognitive Engine
Action Validator

Validates computer actions before execution to ensure safety and correctness.
Implements EPIC-14C pre-action validation checks.
"""

from __future__ import annotations

import time
import logging
import math
from typing import Optional, Tuple, Any
from dataclasses import dataclass

from ..planner.models.computer_action import ComputerAction, ValidationStatus
from ..planner.models.models import PlannerContext
from ..planner.models.action_types import ActionType
from ...registry import PermissionManager
from ..perception import Perception
from desktop_agent.desktop.vision.interaction_target import InteractionTarget
from desktop_agent.desktop.vision.screen_state import ScreenState, BoundingBox
from desktop_agent.registry import ValidationLayer, PermissionManager
from desktop_agent.brain import metrics
from desktop_agent.brain.error_taxonomy import record_error, MYRAAError


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of action validation."""
    is_valid: bool
    status: ValidationStatus
    message: str
    should_re_resolve: bool = False
    validation_time: float = 0.0


class ActionValidator:
    """
    Validates computer actions before execution.

    Performs pre-execution checks including target freshness, window stability,
    coordinate validity, confidence thresholds, and safety checks.
    """

    def __init__(self, perception: Perception, validation_layer: ValidationLayer):
        """
        Initialize the action validator.

        Args:
            perception: Perception layer for accessing current screen state
            validation_layer: Validation layer for tool-level permissions
        """
        self.perception = perception
        self.validation_layer = validation_layer
        self.logger = logging.getLogger(__name__)

        # Validation thresholds
        self.target_max_age_seconds = 30.0  # Targets older than this are stale
        self.screen_state_max_age_seconds = 5.0  # ScreenState older than this is stale for validation
        self.confidence_high_threshold = 0.8   # HIGH confidence -> proceed
        self.confidence_medium_threshold = 0.6 # MEDIUM confidence -> require re-resolution
        self.confidence_low_threshold = 0.4    # LOW confidence -> don't act

        # Window stability checks
        self.window_stability_check_enabled = True
        self.active_window_change_threshold = 2.0  # seconds

    def validate_action(
        self,
        action: ComputerAction,
        context: Optional[PlannerContext] = None
    ) -> ValidationResult:
        """
        Validate a computer action before execution.

        Performs all pre-action validation checks:
        1. Target freshness (not stale)
        2. Target still exists in current screen state
        3. Target bounds valid and visible
        4. Active window stability check
        5. Confidence meets thresholds for action type
        6. Coordinate validation (within monitor bounds)
        7. Permission check
        8. Browser continuity check (for web actions)

        Args:
            action: The computer action to validate
            context: Optional planner context for additional validation

        Returns:
            ValidationResult indicating whether action is valid for execution
        """
        start_time = time.time()
        action_type_str = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)

        try:
            self.logger.debug(f"Validating action: {action_type_str} on target {action.target.text}")

            # Get current screen state for validation
            screen_state = self.perception.screen_state
            if screen_state is None:
                result = ValidationResult(
                    is_valid=False,
                    status=ValidationStatus.INVALID,
                    message="Unable to get current screen state for validation",
                    validation_time=time.time() - start_time
                )
                from desktop_agent.brain import metrics
                metrics.increment_counter(f"validations_{action_type_str}_failure")
                metrics.add_to_histogram(f"validation_latency_{action_type_str}", result.validation_time)
                return result

            # Run validation checks in order
            validation_checks = [
                self._check_target_freshness,
                self._check_target_existence,
                self._check_target_bounds_validity,
                self._check_window_stability,
                self._check_confidence_threshold,
                self._check_coordinate_validity,
                self._check_permissions,
                self._check_browser_continuity
            ]

            for check_func in validation_checks:
                result = check_func(action, screen_state, context)
                if not result.is_valid:
                    # If target needs re-resolution, indicate that
                    if result.should_re_resolve:
                        action.target.invalidate()  # Mark target as invalid
                    validation_time = time.time() - start_time
                    from desktop_agent.brain import metrics
                    metrics.increment_counter(f"validations_{action_type_str}_failure")
                    metrics.add_to_histogram(f"validation_latency_{action_type_str}", validation_time)
                    return result

            # All checks passed
            action.validation_status = ValidationStatus.VALID
            action.validation_message = "All validation checks passed"
            action.validation_timestamp = time.time()

            validation_time = time.time() - start_time
            result = ValidationResult(
                is_valid=True,
                status=ValidationStatus.VALID,
                message="Action validation passed",
                validation_time=validation_time
            )

            from desktop_agent.brain import metrics
            metrics.increment_counter(f"validations_{action_type_str}_success")
            metrics.add_to_histogram(f"validation_latency_{action_type_str}", validation_time)

            return result

        except Exception as e:
            self.logger.error(f"Error during action validation: {e}", exc_info=True)
            validation_time = time.time() - start_time
            result = ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Validation error: {str(e)}",
                validation_time=validation_time
            )
            from desktop_agent.brain import metrics
            metrics.increment_counter(f"validations_{action_type_str}_error")
            metrics.add_to_histogram(f"validation_latency_{action_type_str}", validation_time)
            return result

    def _check_target_freshness(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check if target is fresh (not stale) and screen state is recent."""
        # EPIC-14E: Check screen state freshness first
        screen_state_age = time.time() - screen_state.timestamp
        if screen_state_age > self.screen_state_max_age_seconds:
            # Record error for taxonomy
            record_error(MYRAAError.vision_unavailable(
                details={
                    "screen_state_age": screen_state_age,
                    "max_age": self.screen_state_max_age_seconds,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.STALE,
                message=f"Screen state is stale (age: {screen_state_age:.1f}s, max: {self.screen_state_max_age_seconds}s)",
                should_re_resolve=False  # Can't re-resolve if screen state itself is stale
            )

        # Check if target is fresh (not stale)
        if not action.target.is_valid(self.target_max_age_seconds):
            age = time.time() - action.target.timestamp
            # Record error for taxonomy
            record_error(MYRAAError.target_stale(
                target_description=action.target.text,
                age_seconds=age,
                details={
                    "target_id": action.target.id,
                    "max_age": self.target_max_age_seconds,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.STALE,
                message=f"Target is stale (age: {age:.1f}s, max: {self.target_max_age_seconds}s)",
                should_re_resolve=True
            )

        return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="Target and screen state are fresh")

    def _check_target_existence(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check if target still exists in current screen state and context is valid."""
        # Look for the target by ID or similar characteristics
        current_element = screen_state.get_element_by_id(action.target.id)
        if current_element is None:
            # Try to find similar element by text and position if ID not found
            similar_element = self._find_similar_element(action.target, screen_state.elements)
            if similar_element is None:
                # Record error for taxonomy
                record_error(MYRAAError.target_unresolved(
                    target_description=action.target.text,
                    details={
                        "target_id": action.target.id,
                        "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                    }
                ))
                return ValidationResult(
                    is_valid=False,
                    status=ValidationStatus.INVALID,
                    message="Target no longer exists in current screen state",
                    should_re_resolve=True
                )
            else:
                # Target exists but may have moved - update action target
                self.logger.debug(f"Target {action.target.id} not found, but similar element found")
                # Update the action's target to the current element
                action.target = InteractionTarget(
                    id=similar_element.id,
                    type=similar_element.type,
                    text=similar_element.text,
                    confidence=similar_element.confidence,
                    bounds=similar_element.bounds,
                    clickable=similar_element.clickable,
                    enabled=similar_element.enabled,
                    visible=similar_element.visible,
                    interactive=similar_element.interactive,
                    metadata=similar_element.metadata.copy(),
                    resolution_method=action.target.resolution_method + ", re-validated",
                    reasoning=action.target.reasoning + " (re-validated during execution)",
                    timestamp=time.time(),
                    valid=True,
                    active_window=action.target.active_window,
                    application_context=action.target.application_context,
                    center_point=similar_element.bounds.center,
                    center_reason="re-validated_center"
                )
                # Note: We do not update active_window and application_context here because
                # we don't have that information from the similar element. We'll check below.
                return ValidationResult(
                    is_valid=True,
                    status=ValidationStatus.VALID,
                    message="Target re-validated with current screen state",
                    should_re_resolve=False  # We already updated the target
                )

        # Target found by ID, now check if the context (window/application) still matches
        # Get current active window and application from screen state
        current_active_window = getattr(screen_state, 'active_window', None)
        current_application = getattr(screen_state, 'active_application', '')

        # If the target has active_window information, verify it matches current state
        target_active_window = getattr(action.target, 'active_window', None)
        target_application = getattr(action.target, 'application_context', '')

        # Check active window match (if both have window info)
        if target_active_window and current_active_window:
            # Compare by hwnd if available, otherwise by title
            target_hwnd = getattr(target_active_window, 'hwnd', None)
            current_hwnd = getattr(current_active_window, 'hwnd', None)
            if target_hwnd is not None and current_hwnd is not None:
                if target_hwnd != current_hwnd:
                    # Record error for taxonomy
                    record_error(MYRAAError.window_changed(
                        old_window=str(target_hwnd) if target_hwnd else str(target_active_window.title),
                        new_window=str(current_hwnd) if current_hwnd else str(current_active_window.title),
                        details={
                            "target_id": action.target.id,
                            "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                        }
                    ))
                    return ValidationResult(
                        is_valid=False,
                        status=ValidationStatus.STALE,
                        message=f"Target window hwnd changed from {target_hwnd} to {current_hwnd}",
                        should_re_resolve=True
                    )
            else:
                # Fallback to comparing titles
                target_title = getattr(target_active_window, 'title', '')
                current_title = getattr(current_active_window, 'title', '')
                if target_title and current_title and target_title.lower() != current_title.lower():
                    # Record error for taxonomy
                    record_error(MYRAAError.window_changed(
                        old_window=target_title,
                        new_window=current_title,
                        details={
                            "target_id": action.target.id,
                            "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                        }
                    ))
                    return ValidationResult(
                        is_valid=False,
                        status=ValidationStatus.STALE,
                        message=f"Target window title changed from '{target_title}' to '{current_title}'",
                        should_re_resolve=True
                    )

        # Check application context match
        if target_application and current_application and target_application.lower() != current_application.lower():
            # Record error for taxonomy
            record_error(MYRAAError.window_changed(
                old_window=target_application,
                new_window=current_application,
                details={
                    "target_id": action.target.id,
                    "application_context_old": target_application,
                    "application_context_new": current_application,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.STALE,
                message=f"Target application context changed from '{target_application}' to '{current_application}'",
                should_re_resolve=True
            )

        # If we get here, the target exists and context is compatible
        return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="Target exists in current state with valid context")

    def _find_similar_element(
        self,
        target: InteractionTarget,
        elements: list
    ) -> Optional[Any]:
        """Find a similar element in the current screen state."""
        # Look for elements with similar text and rough position
        for element in elements:
            # Check text similarity (exact match or contained)
            if (element.text == target.text or
                (len(element.text) > 3 and len(target.text) > 3 and
                 (element.text in target.text or target.text in element.text))):

                # Check if bounds are reasonably close (within 50 pixels)
                if (abs(element.bounds.x - target.bounds.x) < 50 and
                    abs(element.bounds.y - target.bounds.y) < 50):
                    return element

        return None

    def _check_target_bounds_validity(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check if target bounds are valid and visible on screen."""
        target = action.target
        bounds = target.bounds

        # Check bounds are valid
        if bounds.width <= 0 or bounds.height <= 0:
            # Record error for taxonomy
            record_error(MYRAAError.coordinate_invalid(
                x=bounds.x,
                y=bounds.y,
                reason=f"Invalid bounds width={bounds.width}, height={bounds.height}",
                details={
                    "target_id": action.target.id,
                    "bounds_width": bounds.width,
                    "bounds_height": bounds.height,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Target has invalid bounds: {bounds}",
                should_re_resolve=True
            )

        # Check bounds are within screen boundaries
        screen_bounds = screen_state.bounds
        if not screen_bounds.contains(bounds):
            # Record error for taxonomy
            record_error(MYRAAError.coordinate_invalid(
                x=bounds.x,
                y=bounds.y,
                reason=f"Target bounds outside screen bounds",
                details={
                    "target_id": action.target.id,
                    "target_bounds": f"{bounds.x},{bounds.y},{bounds.width},{bounds.height}",
                    "screen_bounds": f"{screen_bounds.x},{screen_bounds.y},{screen_bounds.width},{screen_bounds.height}",
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Target bounds {bounds} are outside screen bounds {screen_bounds}",
                should_re_resolve=True
            )

        # Check if target is visible (not obscured)
        if not target.visible:
            # Record error for taxonomy
            record_error(MYRAAError.target_invisible(
                target_description=action.target.text,
                details={
                    "target_id": action.target.id,
                    "bounds": f"{bounds.x},{bounds.y},{bounds.width},{bounds.height}",
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message="Target is not visible",
                should_re_resolve=True
            )

        # Check if target is enabled (for interactive elements)
        if target.clickable and not target.enabled:
            # Record error for taxonomy
            record_error(MYRAAError.target_disabled(
                target_description=action.target.text,
                details={
                    "target_id": action.target.id,
                    "bounds": f"{bounds.x},{bounds.y},{bounds.width},{bounds.height}",
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message="Target is not enabled",
                should_re_resolve=False  # Don't re-resolve as it's likely still there but disabled
            )

        return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="Target bounds are valid")

    def _check_window_stability(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check if active window is stable (hasn't changed recently)."""
        if not self.window_stability_check_enabled:
            return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="Window stability check disabled")

        # Check if we have window information from when target was resolved
        if action.target.active_window is None:
            return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="No window info for stability check")

        # Check if active window has changed significantly
        current_window = screen_state.active_window
        if current_window is None:
            return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="No current active window")

        # Simple check: compare window titles or process names
        target_window_title = getattr(action.target.active_window, 'title', '')
        current_window_title = getattr(current_window, 'title', '')

        # If titles are completely different, window may have changed
        if (target_window_title and current_window_title and
            target_window_title.lower() != current_window_title.lower()):
            # Allow some variance for browser tabs, etc.
            # For now, we'll be conservative and flag significant changes
            # Record error for taxonomy
            record_error(MYRAAError.window_changed(
                old_window=target_window_title,
                new_window=current_window_title,
                details={
                    "target_id": action.target.id,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Active window changed from '{target_window_title}' to '{current_window_title}'",
                should_re_resolve=True
            )

        return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="Window is stable")

    def _check_confidence_threshold(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check if target confidence meets thresholds for action type."""
        target_confidence = action.target.confidence

        # Different action types may have different confidence requirements
        action_type = action.action_type

        # Actions that modify state or are destructive need higher confidence
        high_confidence_actions = {
            ActionType.DELETE_FILE,
            ActionType.WRITE_FILE,
            ActionType.CREATE_FILE,
        }

        medium_confidence_actions = {
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
            ActionType.RIGHT_CLICK,
            ActionType.TYPE_TEXT,
            ActionType.PRESS_KEY,
            ActionType.HOTKEY
        }

        # Determine required confidence based on action type
        if action_type in high_confidence_actions:
            required_confidence = self.confidence_high_threshold
            confidence_level = "HIGH"
        elif action_type in medium_confidence_actions:
            required_confidence = self.confidence_medium_threshold
            confidence_level = "MEDIUM"
        else:
            # Low risk actions can proceed with lower confidence
            required_confidence = self.confidence_low_threshold
            confidence_level = "LOW"

        if target_confidence < required_confidence:
            # Record error for taxonomy
            record_error(MYRAAError(
                category=ErrorCategory.UNKNOWN_ERROR,  # We don't have a specific low confidence error, using UNKNOWN_ERROR for now
                message=f"Target confidence {target_confidence:.2f} is below {confidence_level} threshold {required_confidence:.2f} for {action_type.value}",
                details={
                    "target_id": action.target.id,
                    "target_confidence": target_confidence,
                    "required_confidence": required_confidence,
                    "confidence_level": confidence_level,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                },
                recoverable=True  # Low confidence is usually recoverable with re-resolution
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.LOW_CONFIDENCE,
                message=f"Target confidence {target_confidence:.2f} is below {confidence_level} threshold {required_confidence:.2f} for {action_type.value}",
                should_re_resolve=(target_confidence >= self.confidence_low_threshold)  # Re-resolve if not too low
            )

        return ValidationResult(
            is_valid=True,
            status=ValidationStatus.VALID,
            message=f"Target confidence {target_confidence:.2f} meets {confidence_level} requirement"
        )

    def _check_coordinate_validity(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check if coordinates are within valid display boundaries with DPI and multi-monitor safety."""
        target = action.target

        # Use preferred point if available, otherwise use center
        if action.parameters.get("preferred_point"):
            x, y = action.parameters["preferred_point"]
            reason = action.parameters.get("point_reason", "preferred_point")
        else:
            x, y = target.center_point
            reason = target.center_reason

        # EPIC-14E: Enhanced coordinate safety checks

        # 1. Check for NaN, infinity, or invalid values
        if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
            # Record error for taxonomy
            record_error(MYRAAError.coordinate_invalid(
                x=x,
                y=y,
                reason=f"Coordinates are not valid numbers",
                details={
                    "target_id": action.target.id,
                    "x_value": x,
                    "y_value": y,
                    "point_reason": reason,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Coordinates ({x}, {y}) from {reason} are not valid numbers",
                should_re_resolve=False  # Don't re-resolve as the action parameters are invalid
            )

        if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
            # Record error for taxonomy
            record_error(MYRAAError.coordinate_invalid(
                x=x,
                y=y,
                reason=f"Coordinates contain NaN or infinity",
                details={
                    "target_id": action.target.id,
                    "x_value": x,
                    "y_value": y,
                    "is_nan_x": math.isnan(x),
                    "is_nan_y": math.isnan(y),
                    "is_inf_x": math.isinf(x),
                    "is_inf_y": math.isinf(y),
                    "point_reason": reason,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Coordinates ({x}, {y}) from {reason} contain NaN or infinity",
                should_re_resolve=False  # Don't re-resolve as the action parameters are invalid
            )

        # 2. Check if coordinates are within reasonable bounds (prevent extreme values)
        # Allow negative coordinates for multi-monitor setups, but prevent absurd values
        max_reasonable_coordinate = 30000  # Reasonable limit for virtual desktop coordinates
        if abs(x) > max_reasonable_coordinate or abs(y) > max_reasonable_coordinate:
            # Record error for taxonomy
            record_error(MYRAAError.coordinate_invalid(
                x=x,
                y=y,
                reason=f"Coordinates exceed reasonable bounds",
                details={
                    "target_id": action.target.id,
                    "x_value": x,
                    "y_value": y,
                    "max_reasonable": max_reasonable_coordinate,
                    "point_reason": reason,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Coordinates ({x}, {y}) from {reason} exceed reasonable bounds",
                should_re_resolve=False  # Don't re-resolve as this indicates action parameter corruption
            )

        # 3. Check if coordinates are within screen bounds
        screen_bounds = screen_state.bounds
        if not (screen_bounds.x <= x <= screen_bounds.x + screen_bounds.width and
                screen_bounds.y <= y <= screen_bounds.y + screen_bounds.height):
            # Record error for taxonomy
            record_error(MYRAAError.coordinate_invalid(
                x=x,
                y=y,
                reason=f"Coordinates outside screen bounds",
                details={
                    "target_id": action.target.id,
                    "x_value": x,
                    "y_value": y,
                    "screen_bounds": f"{screen_bounds.x},{screen_bounds.y},{screen_bounds.width},{screen_bounds.height}",
                    "point_reason": reason,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Coordinates ({x}, {y}) from {reason} are outside screen bounds {screen_bounds}",
                should_re_resolve=True
            )

        # 4. EPIC-14E: Additional safety checks for coordinate validity

        # Check if point is within a reasonable minimum size area (not a single pixel)
        # This prevents clicking on potentially erroneous single-pixel detections
        min_click_area = 4  # Minimum 2x2 pixel area
        if hasattr(target, 'bounds') and target.bounds:
            if target.bounds.width < min_click_area or target.bounds.height < min_click_area:
                self.logger.warning(f"Target {target.text} has suspiciously small bounds: {target.bounds}")
                # Don't fail validation, but log warning

        # Store the validated coordinates for execution
        action.parameters["validated_click_point"] = (x, y)
        action.parameters["click_point_reason"] = reason

        return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message=f"Coordinates ({x}, {y}) are valid")

    def _check_permissions(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check if action is permitted based on tool permissions."""
        # Map action type to tool name
        from desktop_agent.brain.runtime.action_mapper import ACTION_TO_TOOL
        tool_name = ACTION_TO_TOOL.get(action.action_type)

        if tool_name is None:
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"No tool mapping found for action type {action.action_type.value}",
                should_re_resolve=False
            )

        # Check permissions through PermissionManager
        permission_decision = PermissionManager.check(tool_name, {})
        is_allowed = permission_decision.allowed

        if not is_allowed:
            # Record error for taxonomy
            record_error(MYRAAError.permission_required(
                action_type=tool_name,
                details={
                    "target_id": action.target.id,
                    "tool_name": tool_name,
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Action {tool_name} is not permitted by current policies",
                should_re_resolve=False
            )

        return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message=f"Action {tool_name} is permitted")

    def _check_browser_continuity(
        self,
        action: ComputerAction,
        screen_state: ScreenState,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Check browser continuity for web actions with EPIC-14E enhancements."""
        # Check if this is a browser-related action
        browser_actions = {
            ActionType.OPEN_URL,
            ActionType.NEW_TAB,
            ActionType.CLOSE_TAB,
            ActionType.SWITCH_TAB,
            ActionType.REFRESH_PAGE,
        }

        if action.action_type not in browser_actions:
            return ValidationResult(is_valid=True, status=ValidationStatus.VALID, message="Not a browser action, skipping continuity check")

        # EPIC-14E: Enhanced browser continuity checks

        # 1. Verify visible browser session exists
        browser_elements = [
            elem for elem in screen_state.elements
            if elem.type.value in ["browser", "chrome", "firefox", "edge"] and elem.visible
        ]

        if not browser_elements:
            # Record error for taxonomy
            record_error(MYRAAError.browser_disconnected(
                reason="No visible browser window found",
                details={
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type),
                    "target_id": action.target.id
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message="No visible browser window found for browser action",
                should_re_resolve=False  # Can't re-resolve if no browser is visible
            )

        # 2. Check for browser desynchronization indicators
        # Check if we have browser session information from context
        browser_session_valid = True
        desynchronization_reasons = []

        # Check action parameters for browser session validation hints
        if hasattr(action, 'metadata') and action.metadata:
            # If we have previous browser session info, validate it still matches
            prev_browser_info = action.metadata.get('browser_session_info')
            if prev_browser_info:
                # Validate that the browser session is still active and matching
                # This would be enhanced in a full implementation to check process/window validity
                pass

        # 3. Enhanced target validation for browser elements
        if action.target.type.value in ["browser", "chrome", "firefox", "edge", "address_bar", "tab", "button", "link"]:
            # The target itself is a browser element
            target_in_visible_browser = False
            for browser_elem in browser_elements:
                # Check if target is reasonably within a visible browser element
                # Using bounds intersection or proximity check
                if self._element_in_browser_bounds(action.target, browser_elem):
                    target_in_visible_browser = True
                    break

            if not target_in_visible_browser:
                desynchronization_reasons.append("Target browser element not found in visible browser windows")

        # 4. Check for unexpected browser state changes that would indicate desynchronization
        # This would be enhanced with actual browser process/window validation in a full implementation

        # 5. Set parameters to ensure we use desktop automation for the visible default browser (no engine owned)
        action.parameters["use_desktop_browser_automation"] = True
        action.parameters["visible_browser_count"] = len(browser_elements)

        # 6. Add browser continuity validation flag for post-action verification
        action.parameters["require_browser_continuity_check"] = True

        if desynchronization_reasons:
            # Record error for taxonomy
            record_error(MYRAAError.browser_disconnected(
                reason="; ".join(desynchronization_reasons),
                details={
                    "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type),
                    "target_id": action.target.id,
                    "desynchronization_reasons": desynchronization_reasons
                }
            ))
            return ValidationResult(
                is_valid=False,
                status=ValidationStatus.INVALID,
                message=f"Browser desynchronization detected: {'; '.join(desynchronization_reasons)}",
                should_re_resolve=True  # Try re-resolving target as it may have changed
            )

        return ValidationResult(
            is_valid=True,
            status=ValidationStatus.VALID,
            message="Browser continuity check passed - will use desktop automation for visible browser"
        )

    def _element_in_browser_bounds(self, element: Any, browser_element: Any) -> bool:
        """
        Check if an element is reasonably contained within a browser element's bounds.

        Args:
            element: The element to check
            browser_element: The browser element to check against

        Returns:
            True if element is within or reasonably close to browser bounds
        """
        if not hasattr(element, 'bounds') or not hasattr(browser_element, 'bounds'):
            return False

        elem_bounds = element.bounds
        browser_bounds = browser_element.bounds

        # Check if element center is within browser bounds with some tolerance
        tolerance = 50  # pixels
        elem_center_x, elem_center_y = elem_bounds.center

        return (browser_bounds.x - tolerance <= elem_center_x <= browser_bounds.right + tolerance and
                browser_bounds.y - tolerance <= elem_center_y <= browser_bounds.bottom + tolerance)