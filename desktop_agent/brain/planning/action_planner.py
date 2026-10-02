"""
MYRAA Cognitive Engine
Action Planner

Translates user goals and resolved interaction targets into executable computer actions.
Implements EPIC-14C action planning functionality.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from ..planner.models.models import PlannerGoal, PlannerContext
from ..planner.models.action_types import ActionType
from ..planner.execution.execution_plan import ExecutionPlan
from ...desktop.vision.interaction_target import InteractionTarget
from ..planner.models.computer_action import ComputerAction, ValidationStatus, VerificationStatus


logger = logging.getLogger(__name__)


@dataclass
class ActionPlanningResult:
    """Result of action planning process."""
    success: bool
    actions: List[ComputerAction]
    message: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ActionPlanner:
    """
    Plans actions from user goals and resolved interaction targets.

    Responsible for translating high-level user intentions and resolved targets
    into concrete executable actions with appropriate parameters.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def plan_actions(
        self,
        goal: PlannerGoal,
        target: InteractionTarget,
        context: PlannerContext
    ) -> ActionPlanningResult:
        """
        Plan actions to achieve the given goal using the resolved target.

        Args:
            goal: The user's goal to achieve
            target: The resolved interaction target to act upon
            context: Current planner context (active window, etc.)

        Returns:
            ActionPlanningResult containing the planned actions
        """
        try:
            self.logger.info(f"Planning actions for goal: {goal.text} with target: {target.text}")

            # Determine what action(s) are needed based on goal and target
            actions = self._determine_actions(goal, target, context)

            if not actions:
                return ActionPlanningResult(
                    success=False,
                    actions=[],
                    message=f"Could not determine appropriate actions for goal '{goal.text}' and target '{target.text}'",
                    confidence=0.0
                )

            self.logger.info(f"Planned {len(actions)} actions: {[a.action_type.value for a in actions]}")

            return ActionPlanningResult(
                success=True,
                actions=actions,
                message=f"Successfully planned {len(actions)} actions for goal",
                confidence=min(goal.confidence, target.confidence),
                metadata={
                    "goal_text": goal.text,
                    "target_text": target.text,
                    "target_id": target.id
                }
            )

        except Exception as e:
            self.logger.error(f"Error during action planning: {e}", exc_info=True)
            return ActionPlanningResult(
                success=False,
                actions=[],
                message=f"Action planning failed: {str(e)}",
                confidence=0.0
            )

    def _determine_actions(
        self,
        goal: PlannerGoal,
        target: InteractionTarget,
        context: PlannerContext
    ) -> List[ComputerAction]:
        """
        Determine what actions are needed to achieve the goal with the given target.

        This is the core planning logic that maps user intentions to executable actions.
        """
        actions = []
        goal_text = goal.text.lower().strip()

        # Handle common goal patterns
        if any(word in goal_text for word in ["click", "press", "select", "choose", "tap"]):
            # Click action
            click_action = ComputerAction(
                action_type=ActionType.CLICK,
                target=target,
                parameters={}
            )
            actions.append(click_action)

        elif any(word in goal_text for word in ["double click", "double-click", "dblclick"]):
            # Double click action
            double_click_action = ComputerAction(
                action_type=ActionType.DOUBLE_CLICK,
                target=target,
                parameters={}
            )
            actions.append(double_click_action)

        elif any(word in goal_text for word in ["right click", "right-click", "context menu"]):
            # Right click action
            right_click_action = ComputerAction(
                action_type=ActionType.RIGHT_CLICK,
                target=target,
                parameters={}
            )
            actions.append(right_click_action)

        elif any(word in goal_text for word in ["type", "enter", "input", "write", "fill"]):
            # Type text action - extract text from goal or parameters
            text_to_type = self._extract_text_to_type(goal, target)
            if text_to_type:
                type_action = ComputerAction(
                    action_type=ActionType.TYPE_TEXT,
                    target=target,
                    parameters={"text": text_to_type}
                )
                actions.append(type_action)
            else:
                # Default to clicking if we can't determine what to type
                click_action = ComputerAction(
                    action_type=ActionType.CLICK,
                    target=target,
                    parameters={}
                )
                actions.append(click_action)

        elif any(word in goal_text for word in ["press", "hit", "push"]) and any(
            word in goal_text for word in ["enter", "return", "escape", "esc", "tab", "space"]):
            # Press key action
            key_to_press = self._extract_key_to_press(goal)
            if key_to_press:
                press_action = ComputerAction(
                    action_type=ActionType.PRESS_KEY,
                    target=target,  # Target may be used for focus context
                    parameters={"key": key_to_press}
                )
                actions.append(press_action)
            else:
                # Default to click
                click_action = ComputerAction(
                    action_type=ActionType.CLICK,
                    target=target,
                    parameters={}
                )
                actions.append(click_action)

        elif any(word in goal_text for word in ["move", "hover", "navigate to", "go to"]):
            # Move mouse action
            move_action = ComputerAction(
                action_type=ActionType.MOVE_MOUSE,
                target=target,
                parameters={}
            )
            actions.append(move_action)

        elif any(word in goal_text for word in ["drag", "drop"]):
            # Drag action - would need source and target, simplified for now
            drag_action = ComputerAction(
                action_type=ActionType.DRAG,
                target=target,
                parameters={}  # Would need source target in full implementation
            )
            actions.append(drag_action)

        elif any(word in goal_text for word in ["scroll", "scroll up", "scroll down"]):
            # Scroll action
            direction = "down" if "down" in goal_text else "up"
            scroll_action = ComputerAction(
                action_type=ActionType.SCROLL_DOWN if direction == "down" else ActionType.SCROLL_UP,
                target=target,
                parameters={}
            )
            actions.append(scroll_action)

        else:
            # Default action: click on the target
            # This is a safe fallback for most interaction goals
            click_action = ComputerAction(
                action_type=ActionType.CLICK,
                target=target,
                parameters={}
            )
            actions.append(click_action)

        # Apply any target-specific adjustments
        actions = self._apply_target_adjustments(actions, target, context)

        return actions

    def _extract_text_to_type(self, goal: PlannerGoal, target: InteractionTarget) -> Optional[str]:
        """Extract text to type from goal or use target context."""
        goal_text = goal.text.lower()

        # Look for quoted text or text after keywords like "type" or "enter"
        import re

        # Check for quoted text
        quoted_match = re.search(r'["\']([^"\']*)["\']', goal_text)
        if quoted_match:
            return quoted_match.group(1)

        # Check for text after common typing keywords
        typing_patterns = [
            r'type\s+(?:the\s+)?text\s+["\']([^"\']*)["\']',
            r'type\s+["\']([^"\']*)["\']',
            r'enter\s+["\']([^"\']*)["\']',
            r'input\s+["\']([^"\']*)["\']',
            r'write\s+["\']([^"\']*)["\']',
            r'fill\s+with\s+["\']([^"\']*)["\']'
        ]

        for pattern in typing_patterns:
            match = re.search(pattern, goal_text)
            if match:
                return match.group(1)

        # If target is an input field, we might want to type something related to the goal
        if target.type.value in ["text_field", "search_box", "input", "textarea"]:
            # Extract meaningful words from goal that aren't action verbs
            action_verbs = {"type", "enter", "input", "write", "fill", "click", "press", "select"}
            words = [w for w in goal_text.split() if w not in action_verbs and len(w) > 2]
            if words:
                return " ".join(words[:3])  # Limit to first 3 meaningful words

        return None

    def _extract_key_to_press(self, goal: PlannerGoal) -> Optional[str]:
        """Extract key to press from goal."""
        goal_text = goal.text.lower()

        # Map common key names to their actual key values
        key_mapping = {
            "enter": "enter",
            "return": "enter",
            "escape": "esc",
            "esc": "esc",
            "tab": "tab",
            "space": "space",
            "spacebar": "space",
            "backspace": "backspace",
            "delete": "delete",
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
            "home": "home",
            "end": "end",
            "page up": "pageup",
            "page down": "pagedown"
        }

        for key_name, key_value in key_mapping.items():
            if key_name in goal_text:
                return key_value

        return None

    def _apply_target_adjustments(
        self,
        actions: List[ComputerAction],
        target: InteractionTarget,
        context: PlannerContext
    ) -> List[ComputerAction]:
        """Apply target-specific adjustments to planned actions."""
        adjusted_actions = []

        for action in actions:
            # For click-like actions, we might want to adjust the interaction point
            if action.action_type in [ActionType.CLICK, ActionType.DOUBLE_CLICK, ActionType.RIGHT_CLICK]:
                # Check if target has a preferred interaction point
                if target.center_point and target.center_reason != "geometric_center":
                    # Store the preferred point in parameters for the executor to use
                    action.parameters["preferred_point"] = target.center_point
                    action.parameters["point_reason"] = target.center_reason

            # For typing actions, we might want to focus the target first
            elif action.action_type == ActionType.TYPE_TEXT:
                # Add a focus click before typing if the target might benefit from it
                if target.clickable and target.enabled:
                    focus_action = ComputerAction(
                        action_type=ActionType.CLICK,
                        target=target,
                        parameters={}
                    )
                    adjusted_actions.append(focus_action)

            adjusted_actions.append(action)

        return adjusted_actions