"""
MYRAA Brain - Decision Engine

The Decision Engine is responsible for deciding HOW MYRAA should respond.

It does NOT execute tools.

Responsibilities
----------------
• Understand user intent
• Estimate confidence
• Decide if planning is required
• Decide if clarification is required
• Decide if memory/context is needed
• Produce a BrainDecision for the Planner
"""

from __future__ import annotations
from .semantic.semantic_models import SemanticTask
from dataclasses import dataclass
from typing import List, Optional

from .models import (
    BrainDecision,
    BrainContext,
    DecisionType,
)


@dataclass
class UserIntent:
    """
    Internal representation of the user's request.
    """

    original_text: str

    normalized: str

    goal: str

    confidence: float = 0.0

    requires_tools: bool = False

    requires_memory: bool = False

    requires_vision: bool = False

    requires_planning: bool = False

    requires_confirmation: bool = False

    ambiguous: bool = False


class DecisionEngine:

    """
    Converts natural language into an executable decision.
    """

    DIRECT_ACTION_KEYWORDS = {
        "open",
        "close",
        "launch",
        "search",
        "play",
        "read",
        "copy",
        "paste",
        "volume",
        "mute",
        "brightness",
        "take screenshot",
        "show",
    }

    PLANNING_KEYWORDS = {
        "organize",
        "prepare",
        "clean",
        "setup",
        "arrange",
        "backup",
        "create project",
        "workflow",
        "install",
        "configure",
    }

    MEMORY_KEYWORDS = {
        "remember",
        "recall",
        "last time",
        "previous",
        "history",
        "my preference",
    }

    VISION_KEYWORDS = {
        "look",
        "see",
        "screen",
        "screenshot",
        "read screen",
        "image",
        "photo",
    }

    DANGEROUS_KEYWORDS = {
        "delete",
        "shutdown",
        "restart",
        "format",
        "factory reset",
        "remove",
    }

    def __init__(self):

        pass

    # -----------------------------------------------------

    def analyze(
        self,
        text: str,
        context: Optional[BrainContext] = None,
    ) -> BrainDecision:

        intent = self._extract_intent(text)

        confidence = self._calculate_confidence(intent)

        decision_type = self._select_decision_type(intent)

        reasoning = self._build_reasoning(intent)

        return BrainDecision(
            goal=intent.goal,
            decision_type=decision_type,
            confidence=confidence,
            reasoning=reasoning,
            needs_confirmation=intent.requires_confirmation,
        )

    # -----------------------------------------------------

    def _extract_intent(self, text: str) -> UserIntent:

        normalized = text.lower().strip()

        intent = UserIntent(
            original_text=text,
            normalized=normalized,
            goal=text,
        )

        for keyword in self.DIRECT_ACTION_KEYWORDS:
            if keyword in normalized:
                intent.requires_tools = True

        for keyword in self.PLANNING_KEYWORDS:
            if keyword in normalized:
                intent.requires_planning = True

        for keyword in self.MEMORY_KEYWORDS:
            if keyword in normalized:
                intent.requires_memory = True

        for keyword in self.VISION_KEYWORDS:
            if keyword in normalized:
                intent.requires_vision = True

        for keyword in self.DANGEROUS_KEYWORDS:
            if keyword in normalized:
                intent.requires_confirmation = True

        if len(normalized.split()) <= 1:
            intent.ambiguous = True

        return intent

    # -----------------------------------------------------

    def _calculate_confidence(
        self,
        intent: UserIntent,
    ) -> float:

        confidence = 0.55

        if intent.requires_tools:
            confidence += 0.15

        if intent.requires_planning:
            confidence += 0.10

        if intent.requires_memory:
            confidence += 0.05

        if intent.requires_vision:
            confidence += 0.05

        if intent.ambiguous:
            confidence -= 0.25

        return max(0.0, min(1.0, confidence))

    # -----------------------------------------------------

    def _select_decision_type(
        self,
        intent: UserIntent,
    ) -> DecisionType:

        if intent.ambiguous:
            return DecisionType.QUESTION

        if intent.requires_memory:
            return DecisionType.MEMORY

        if intent.requires_vision:
            return DecisionType.VISION

        if intent.requires_planning:
            return DecisionType.PLAN

        return DecisionType.DIRECT

    # -----------------------------------------------------

    def _build_reasoning(
        self,
        intent: UserIntent,
    ) -> List[str]:

        reasoning = []

        reasoning.append(
            f"Goal identified: {intent.goal}"
        )

        if intent.requires_tools:
            reasoning.append(
                "Desktop tools are required."
            )

        if intent.requires_planning:
            reasoning.append(
                "Task requires multi-step planning."
            )

        if intent.requires_memory:
            reasoning.append(
                "Memory lookup is recommended."
            )

        if intent.requires_vision:
            reasoning.append(
                "Vision module should be consulted."
            )

        if intent.requires_confirmation:
            reasoning.append(
                "User confirmation is required."
            )

        if intent.ambiguous:
            reasoning.append(
                "User request is ambiguous."
            )

        return reasoning


        # -----------------------------------------------------
    # Context Enrichment
    # -----------------------------------------------------

    def enrich_with_context(
        self,
        intent: UserIntent,
        context: Optional[BrainContext],
    ) -> UserIntent:
        """
        Improve the intent using desktop context.

        This method never changes the user's goal.
        It only fills missing information that MYRAA
        already knows.
        """

        if context is None:
            return intent

        if context.active_app:

            app = context.active_app.lower()

            if "code" in app or "vscode" in app:
                intent.confidence += 0.05

            if "chrome" in app:
                intent.confidence += 0.03

            if "edge" in app:
                intent.confidence += 0.03

        if context.clipboard:
            intent.confidence += 0.02

        return intent

    # -----------------------------------------------------
    # Clarification Detection
    # -----------------------------------------------------

    def needs_clarification(
        self,
        intent: UserIntent,
    ) -> bool:
        """
        Determine if MYRAA should ask
        a follow-up question.
        """

        if intent.ambiguous:
            return True

        if intent.confidence < 0.55:
            return True

        return False

    # -----------------------------------------------------
    # Candidate Action Generation
    # -----------------------------------------------------

    def generate_candidate_actions(
        self,
        intent: UserIntent,
    ) -> List[str]:

        actions: List[str] = []

        text = intent.normalized

        # Applications

        if "chrome" in text:
            actions.append("openApplication")

        if "notepad" in text:
            actions.append("openApplication")

        if "calculator" in text:
            actions.append("openApplication")

        if "spotify" in text:
            actions.append("openApplication")

        if "folder" in text:
            actions.append("openFolder")

        # Browser

        if "google" in text:
            actions.append("searchGoogle")

        if "youtube" in text:
            actions.append("searchYouTube")

        if "github" in text:
            actions.append("searchGitHub")

        # Screenshot

        if "screenshot" in text:
            actions.append("takeScreenshot")

        if "screen" in text:
            actions.append("readScreen")

        # Files

        if "create file" in text:
            actions.append("createFile")

        if "read file" in text:
            actions.append("readFile")

        if "delete file" in text:
            actions.append("deleteFile")

        if "rename" in text:
            actions.append("renameFile")

        if "move" in text:
            actions.append("moveFile")

        return actions

    # -----------------------------------------------------
    # Candidate Ranking
    # -----------------------------------------------------

    def rank_actions(
        self,
        actions: List[str],
        intent: UserIntent,
    ) -> List[str]:
        """
        Future:
            ML ranking
            Memory ranking
            User preference ranking

        Current:
            Remove duplicates while preserving order.
        """

        ranked = []

        seen = set()

        for action in actions:

            if action in seen:
                continue

            ranked.append(action)

            seen.add(action)

        return ranked

    # -----------------------------------------------------
    # Final Decision Builder
    # -----------------------------------------------------

    def build_final_decision(
        self,
        text: str,
        context: Optional[BrainContext] = None,
    ) -> BrainDecision:

        intent = self._extract_intent(text)

        intent = self.enrich_with_context(
            intent,
            context,
        )

        confidence = self._calculate_confidence(intent)

        intent.confidence = confidence

        actions = self.generate_candidate_actions(intent)

        actions = self.rank_actions(actions, intent)

        reasoning = self._build_reasoning(intent)

        reasoning.append(
            f"Candidate actions: {', '.join(actions) if actions else 'None'}"
        )

        if self.needs_clarification(intent):

            return BrainDecision(
                goal=intent.goal,
                decision_type=DecisionType.QUESTION,
                confidence=confidence,
                reasoning=reasoning,
                needs_confirmation=False,
            )

        return BrainDecision(
            goal=intent.goal,
            decision_type=self._select_decision_type(intent),
            confidence=confidence,
            reasoning=reasoning,
            needs_confirmation=intent.requires_confirmation,
        )


        # -----------------------------------------------------
    # Intent Classification
    # -----------------------------------------------------

    def classify_intent(
        self,
        text: str,
    ) -> str:
        """
        High-level classification.

        Categories:
            desktop
            browser
            files
            system
            coding
            memory
            vision
            workflow
            conversation
        """

        t = text.lower()

        browser = [
            "google",
            "youtube",
            "github",
            "browser",
            "website",
            "search",
            "chrome",
            "edge",
        ]

        files = [
            "file",
            "folder",
            "rename",
            "delete",
            "move",
            "copy",
            "document",
        ]

        coding = [
            "python",
            "code",
            "vscode",
            "program",
            "script",
            "compile",
            "debug",
            "project",
        ]

        system = [
            "shutdown",
            "restart",
            "volume",
            "brightness",
            "battery",
            "gpu",
            "temperature",
            "cpu",
        ]

        vision = [
            "screen",
            "image",
            "photo",
            "ocr",
            "screenshot",
            "look",
            "see",
        ]

        workflow = [
            "prepare",
            "organize",
            "workflow",
            "routine",
            "automate",
            "schedule",
        ]

        memory = [
            "remember",
            "recall",
            "history",
            "last",
            "before",
        ]

        for word in browser:
            if word in t:
                return "browser"

        for word in files:
            if word in t:
                return "files"

        for word in coding:
            if word in t:
                return "coding"

        for word in system:
            if word in t:
                return "system"

        for word in vision:
            if word in t:
                return "vision"

        for word in workflow:
            if word in t:
                return "workflow"

        for word in memory:
            if word in t:
                return "memory"

        return "conversation"

    # -----------------------------------------------------
    # Goal Extraction
    # -----------------------------------------------------

    def extract_goal(
        self,
        text: str,
    ) -> str:
        """
        Convert the user's request into
        a concise goal statement.
        """

        goal = text.strip()

        replacements = [
            "please",
            "can you",
            "could you",
            "would you",
            "for me",
        ]

        lower = goal.lower()

        for item in replacements:
            lower = lower.replace(item, "")

        goal = lower.strip()

        if len(goal) == 0:
            goal = text

        return goal.capitalize()

    # -----------------------------------------------------
    # Multi-Step Prediction
    # -----------------------------------------------------

    def predicts_multiple_steps(
        self,
        text: str,
    ) -> bool:

        t = text.lower()

        keywords = [

            "organize",

            "prepare",

            "setup",

            "configure",

            "backup",

            "install",

            "workflow",

            "clean",

            "project",

            "create application",

        ]

        return any(k in t for k in keywords)

    # -----------------------------------------------------
    # Memory Requirement
    # -----------------------------------------------------

    def requires_memory_lookup(
        self,
        text: str,
    ) -> bool:

        t = text.lower()

        keywords = [

            "remember",

            "last",

            "previous",

            "history",

            "again",

            "same",

            "continue",

        ]

        return any(k in t for k in keywords)

    # -----------------------------------------------------
    # Vision Requirement
    # -----------------------------------------------------

    def requires_screen_understanding(
        self,
        text: str,
    ) -> bool:

        t = text.lower()

        keywords = [

            "look",

            "screen",

            "image",

            "button",

            "window",

            "screenshot",

            "read this",

            "see",

        ]

        return any(k in t for k in keywords)

        # -----------------------------------------------------
    # Tool Recommendation Score
    # -----------------------------------------------------

    def score_tool(
        self,
        tool_name: str,
        intent: UserIntent,
    ) -> float:
        """
        Assign a heuristic score to a candidate tool.
        Later versions can incorporate usage history,
        execution success rates, and user preferences.
        """

        score = 0.50

        text = intent.normalized

        if tool_name == "openApplication" and "open" in text:
            score += 0.30

        elif tool_name.startswith("search") and "search" in text:
            score += 0.25

        elif tool_name == "takeScreenshot" and "screenshot" in text:
            score += 0.35

        elif tool_name == "readScreen" and "screen" in text:
            score += 0.35

        elif tool_name == "createFile" and "create" in text:
            score += 0.25

        elif tool_name == "deleteFile":
            score -= 0.15

        if intent.requires_confirmation:
            score -= 0.10

        return max(0.0, min(1.0, score))

    # -----------------------------------------------------
    # Best Tool Selection
    # -----------------------------------------------------

    def choose_best_action(
        self,
        actions: List[str],
        intent: UserIntent,
    ) -> Optional[str]:

        if not actions:
            return None

        best_tool = None
        best_score = -1.0

        for tool in actions:

            score = self.score_tool(tool, intent)

            if score > best_score:
                best_score = score
                best_tool = tool

        return best_tool

    # -----------------------------------------------------
    # Retry Decision
    # -----------------------------------------------------

    def should_retry(
        self,
        attempts: int,
        error_message: str,
    ) -> bool:
        """
        Decide if an operation should be retried.
        """

        if attempts >= 3:
            return False

        message = error_message.lower()

        transient_errors = (
            "timeout",
            "network",
            "busy",
            "temporary",
            "connection",
        )

        return any(word in message for word in transient_errors)

    # -----------------------------------------------------
    # Self-Correction
    # -----------------------------------------------------

    def suggest_alternative(
        self,
        failed_tool: str,
    ) -> Optional[str]:
        """
        Suggest a fallback tool if one fails.
        """

        fallback_map = {
            "searchGoogle": "searchWeb",
            "desktopBrowserOpen": "openWebsite",
            "takeScreenshot": "readScreen",
        }

        return fallback_map.get(failed_tool)

    # -----------------------------------------------------
    # Execution Priority
    # -----------------------------------------------------

    def priority(
        self,
        intent: UserIntent,
    ) -> int:
        """
        Higher number = higher execution priority.
        """

        if intent.requires_confirmation:
            return 1

        if intent.requires_planning:
            return 2

        if intent.requires_memory:
            return 3

        if intent.requires_vision:
            return 4

        if intent.requires_tools:
            return 5

        return 6

    # -----------------------------------------------------
    # Public Entry Point
    # -----------------------------------------------------

    def decide(
        self,
        task: SemanticTask,
        context: Optional[BrainContext] = None,
    ) -> BrainDecision:
        """
        Main entry point used by the Brain.
        """

        print("\n" + "=" * 60)
        print("DecisionEngine.decide()")
        print("=" * 60)
        print("Task Type       :", type(task))
        print("Raw Text        :", task.raw_text)
        print("Intent          :", task.intent)
        print("Metadata Type   :", type(task.metadata))
        print("Metadata        :", repr(task.metadata))
        print("'action' exists :", "action" in task.metadata)
        print("=" * 60)

        active_goal = None

        if context is not None:
            active_goal = context.metadata.get("active_goal")

        # -----------------------------------------------------
        # Structured Function Call
        # -----------------------------------------------------

        if "action" in task.metadata:

            print(">>> DIRECT ACTION DECISION")
            print("Action     :", task.metadata["action"])
            print("Parameters :", task.metadata.get("parameters", {}))

            if active_goal:
                print(f"Current Goal: {active_goal}")

            return BrainDecision(
                goal=task.raw_text,
                decision_type=DecisionType.DIRECT,
                confidence=1.0,
                reasoning=[
                    "Structured function call received."
                ],
                action=task.metadata["action"],
                parameters=task.metadata.get("parameters", {}),
                needs_confirmation=False,
            )

        print(">>> NORMAL NLP PATH EXECUTED")

        text = task.raw_text

        intent = self._extract_intent(text)

        intent = self.enrich_with_context(
            intent,
            context,
        )

        confidence = self._calculate_confidence(intent)

        intent.confidence = confidence

        actions = self.generate_candidate_actions(intent)

        actions = self.rank_actions(actions, intent)

        best_action = self.choose_best_action(
            actions,
            intent,
        )

        reasoning = self._build_reasoning(intent)

        if best_action:
            reasoning.append(
                f"Recommended tool: {best_action}"
            )

        reasoning.append(
            f"Intent category: {self.classify_intent(text)}"
        )

        reasoning.append(
            f"Execution priority: {self.priority(intent)}"
        )

        decision = BrainDecision(
            goal=self.extract_goal(text),
            decision_type=self._select_decision_type(intent),
            confidence=confidence,
            reasoning=reasoning,
            needs_confirmation=intent.requires_confirmation,
        )

        return decision  