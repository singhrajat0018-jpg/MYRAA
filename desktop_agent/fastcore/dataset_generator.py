"""MYRAA FastCore — Dataset Generation Pipeline.

Generates training data for FastCore using the deterministic classifier
as the initial teacher. Later, real LLM teachers (Qwen3.5, Gemma 3,
MiniMax-M3) can be plugged in for label refinement.
"""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    TrainingExample,
    TaskType,
    ResponseMode,
    InformationSource,
    Complexity,
    ModelRoute,
    SafetyClass,
)
from .classifier import FastCoreClassifier


# ---------------------------------------------------------------------------
# Dataset Families
# ---------------------------------------------------------------------------

# Each family is a list of (input_text, expectedoverrides) tuples.
# The classifier generates the base label; overrides fix known edge cases.

FAMILY_CONVERSATION: List[Dict[str, Any]] = [
    {"text": "Hello", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Hi", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Hey", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Hello Myraa", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Hey Myra", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "How are you", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Good morning", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Thanks", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Thank you", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Bye", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Goodbye", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "What can you do", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Who are you", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Stay with me", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "I'm bored", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Let's talk", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "OK", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Sure", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Yes", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "No", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Please", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "What's up", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Sup", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
    {"text": "Nice to meet you", "task": "conversation", "source": "none", "complexity": "trivial", "route": "fastcore_direct"},
]

FAMILY_KNOWLEDGE: List[Dict[str, Any]] = [
    {"text": "What is Python", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "What is RAM", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "What is recursion", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "Who is Alan Turing", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "What is a CPU", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "Explain OOP", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "Define function", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "How does a CPU work", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "What is machine learning", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False},
    {"text": "Difference between Python and Java", "task": "direct_knowledge", "source": "local_model", "complexity": "moderate", "route": "local_small", "tools": False},
]

FAMILY_CURRENT: List[Dict[str, Any]] = [
    {"text": "Latest Python version", "task": "current_information", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "freshness": True},
    {"text": "Current stock price of Apple", "task": "trading_task", "source": "tavily", "complexity": "moderate", "route": "local_large", "tools": True, "freshness": True, "safety": "financial"},
    {"text": "Today's news", "task": "current_information", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "freshness": True},
    {"text": "What happened today", "task": "current_information", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "freshness": True},
    {"text": "Recent breakthroughs in AI", "task": "current_information", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "freshness": True},
    {"text": "Market live updates", "task": "trading_task", "source": "tavily", "complexity": "moderate", "route": "local_large", "tools": True, "freshness": True, "safety": "financial"},
]

FAMILY_DESKTOP: List[Dict[str, Any]] = [
    {"text": "Open Notepad", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["openApplication"]},
    {"text": "Close Chrome", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["closeApplication"]},
    {"text": "Volume up", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["system_control"]},
    {"text": "Mute", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["system_control"]},
    {"text": "Shutdown the PC", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["power_action"]},
    {"text": "Take a screenshot", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["screenshot"]},
    {"text": "Copy selected text", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["clipboard"]},
    {"text": "Minimize window", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["window_control"]},
    {"text": "Click the button", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["input_control"]},
    {"text": "Brightness down", "task": "desktop_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["system_control"]},
]

FAMILY_BROWSER: List[Dict[str, Any]] = [
    {"text": "Open YouTube", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["browser"]},
    {"text": "Search on Google", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["browser"]},
    {"text": "Navigate to github.com", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["browser"]},
    {"text": "Browse websites", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["browser"]},
    {"text": "Watch a video on YouTube", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["browser"]},
]

FAMILY_FILE: List[Dict[str, Any]] = [
    {"text": "Create a file called test.txt", "task": "file_task", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["createFile"]},
    {"text": "Read the config file", "task": "file_task", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["readFile"]},
    {"text": "Delete old logs", "task": "file_task", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["deleteFile"]},
    {"text": "Rename report.docx to final.docx", "task": "file_task", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["renameFile"]},
    {"text": "List files in Documents", "task": "file_task", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["listFiles"]},
]

FAMILY_VISION: List[Dict[str, Any]] = [
    {"text": "What's on my screen", "task": "vision_task", "source": "screen", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["screenshot", "vision"]},
    {"text": "What do you see", "task": "vision_task", "source": "screen", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["screenshot", "vision"]},
    {"text": "Read this chart", "task": "vision_task", "source": "screen", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["screenshot", "vision"]},
    {"text": "Analyze this screenshot", "task": "vision_task", "source": "screen", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["screenshot", "vision"]},
    {"text": "OCR this image", "task": "vision_task", "source": "screen", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["screenshot", "vision"]},
]

FAMILY_TRADING: List[Dict[str, Any]] = [
    {"text": "Analyze NIFTY", "task": "trading_task", "source": "local_model", "complexity": "moderate", "route": "local_large", "tools": True, "tool_names": ["trading_engine"], "safety": "financial"},
    {"text": "What is the stock price of Reliance", "task": "trading_task", "source": "tavily", "complexity": "moderate", "route": "local_large", "tools": True, "freshness": True, "safety": "financial"},
    {"text": "Show my portfolio", "task": "trading_task", "source": "local_model", "complexity": "moderate", "route": "local_large", "tools": True, "safety": "financial"},
    {"text": "Bank NIFTY trend", "task": "trading_task", "source": "local_model", "complexity": "moderate", "route": "local_large", "tools": True, "freshness": True, "safety": "financial"},
]

FAMILY_CODING: List[Dict[str, Any]] = [
    {"text": "Build a Python project", "task": "coding_task", "source": "tool_execution", "complexity": "complex", "route": "local_large", "tools": True, "tool_names": ["code_execution"]},
    {"text": "Write a script to sort files", "task": "coding_task", "source": "tool_execution", "complexity": "complex", "route": "local_large", "tools": True, "tool_names": ["code_execution"]},
    {"text": "Debug this code", "task": "coding_task", "source": "tool_execution", "complexity": "complex", "route": "local_large", "tools": True, "tool_names": ["code_execution"]},
    {"text": "Create a web scraper", "task": "coding_task", "source": "tool_execution", "complexity": "complex", "route": "local_large", "tools": True, "tool_names": ["code_execution"]},
]

FAMILY_DESIGN: List[Dict[str, Any]] = [
    {"text": "Design a futuristic bike", "task": "design_task", "source": "local_model", "complexity": "complex", "route": "local_large", "tools": True, "tool_names": ["design_intelligence"]},
    {"text": "Sketch a motorcycle concept", "task": "design_task", "source": "local_model", "complexity": "complex", "route": "local_large", "tools": True, "tool_names": ["design_intelligence"]},
    {"text": "Create a 3D model of a chair", "task": "design_task", "source": "local_model", "complexity": "complex", "route": "local_large", "tools": True, "tool_names": ["design_intelligence"]},
]

FAMILY_RESEARCH: List[Dict[str, Any]] = [
    {"text": "Search for Python documentation", "task": "web_research", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["web_search"]},
    {"text": "Find official NVIDIA page", "task": "web_research", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["web_search"]},
    {"text": "Research latest AI models", "task": "web_research", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["web_search"]},
    {"text": "Compare React and Vue", "task": "direct_knowledge", "source": "local_model", "complexity": "moderate", "route": "local_small", "tools": False},
]

FAMILY_HARD_NEGATIVE: List[Dict[str, Any]] = [
    # These are specifically designed to test edge cases
    {"text": "Hello, can you search Python", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "note": "has action verb despite greeting prefix"},
    {"text": "Tell me about today's Python news", "task": "current_information", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "freshness": True, "note": "current info, not static knowledge"},
    {"text": "Can you open the Python website", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "note": "browser action despite knowledge topic"},
    {"text": "What is the latest version of Python", "task": "current_information", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "freshness": True, "note": "knowledge question with freshness"},
    {"text": "Search YouTube for AI news", "task": "browser_action", "source": "tool_execution", "complexity": "simple", "route": "deterministic", "tools": True, "tool_names": ["browser"], "note": "browser search, not research"},
    {"text": "Read the screen and tell me what's there", "task": "vision_task", "source": "screen", "complexity": "moderate", "route": "local_small", "tools": True, "tool_names": ["screenshot", "vision"], "note": "vision with action verb"},
    {"text": "Create a file with today's news", "task": "file_task", "source": "tool_execution", "complexity": "moderate", "route": "deterministic", "tools": True, "note": "file creation with research content"},
    {"text": "What's the weather like today", "task": "current_information", "source": "tavily", "complexity": "moderate", "route": "local_small", "tools": True, "freshness": True, "note": "current info, no freshness keyword but implies it"},
    {"text": "Open Notepad and write a Python script", "task": "desktop_action", "source": "tool_execution", "complexity": "moderate", "route": "deterministic", "tools": True, "note": "multi-action desktop task"},
    {"text": "Explain how to use the open command", "task": "direct_knowledge", "source": "local_model", "complexity": "simple", "route": "local_small", "tools": False, "note": "knowledge about a tool, not a tool action"},
]

# All families
ALL_FAMILIES = {
    "conversation": FAMILY_CONVERSATION,
    "knowledge": FAMILY_KNOWLEDGE,
    "current": FAMILY_CURRENT,
    "desktop": FAMILY_DESKTOP,
    "browser": FAMILY_BROWSER,
    "file": FAMILY_FILE,
    "vision": FAMILY_VISION,
    "trading": FAMILY_TRADING,
    "coding": FAMILY_CODING,
    "design": FAMILY_DESIGN,
    "research": FAMILY_RESEARCH,
    "hard_negative": FAMILY_HARD_NEGATIVE,
}


# ---------------------------------------------------------------------------
# Dataset Generator
# ---------------------------------------------------------------------------

class DatasetGenerator:
    """Generates training datasets for FastCore."""

    def __init__(self):
        self.classifier = FastCoreClassifier()

    def generate(self, families: Optional[List[str]] = None) -> List[TrainingExample]:
        """Generate training examples from specified families (or all)."""
        target_families = families or list(ALL_FAMILIES.keys())
        examples: List[TrainingExample] = []

        for family_name in target_families:
            family_data = ALL_FAMILIES.get(family_name, [])
            for item in family_data:
                example = self._make_example(family_name, item)
                examples.append(example)

        return examples

    def _make_example(self, family_name: str, item: Dict[str, Any]) -> TrainingExample:
        """Create a TrainingExample from a family item."""
        text = item["text"]

        # Get classifier prediction
        prediction = self.classifier.classify(text)

        # Apply overrides from the item
        task_type = TaskType(item.get("task", prediction.task_type.value))
        source = InformationSource(item.get("source", prediction.information_source.value))
        complexity = Complexity(item.get("complexity", prediction.complexity.value))
        route = ModelRoute(item.get("route", prediction.model_route.value))
        tools = item.get("tools", prediction.tools_required)
        tool_names = item.get("tool_names", prediction.tool_names)
        freshness = item.get("freshness", prediction.freshness_required)
        safety = SafetyClass(item.get("safety", prediction.safety_class.value))

        # Determine response mode from task type
        mode_map = {
            "conversation": ResponseMode.FAST_ANSWER,
            "direct_knowledge": ResponseMode.FAST_ANSWER,
            "local_reasoning": ResponseMode.REASONING,
            "current_information": ResponseMode.RESEARCH,
            "web_research": ResponseMode.RESEARCH,
            "desktop_action": ResponseMode.ACTION,
            "browser_action": ResponseMode.ACTION,
            "vision_task": ResponseMode.VISION,
            "file_task": ResponseMode.ACTION,
            "trading_task": ResponseMode.TRADING,
            "coding_task": ResponseMode.CODING,
            "design_task": ResponseMode.DESIGN,
            "multimodal_task": ResponseMode.MULTIMODAL,
        }
        response_mode = ResponseMode(mode_map.get(task_type.value, prediction.response_mode.value))

        # Teacher votes (from classifier)
        teacher_votes = {"deterministic": task_type.value}

        return TrainingExample(
            input_text=text,
            input_type="user_message",
            task_type=task_type,
            response_mode=response_mode,
            information_source=source,
            complexity=complexity,
            model_route=route,
            safety_class=safety,
            tools_required=tools,
            tool_names=tool_names,
            freshness_required=freshness,
            confidence=0.9,
            teacher_votes=teacher_votes,
            final_label=task_type.value,
            dataset_family=family_name,
        )

    def save(self, examples: List[TrainingExample], path: str) -> Dict[str, Any]:
        """Save dataset to JSON. Returns stats."""
        data = [e.to_dict() for e in examples]

        # Deduplicate by input_text
        seen = set()
        unique = []
        for item in data:
            key = hashlib.md5(item["input_text"].lower().encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique.append(item)

        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "w", encoding="utf-8") as f:
            json.dump(unique, f, indent=2, ensure_ascii=False)

        stats = {
            "total": len(unique),
            "families": {},
            "task_types": {},
            "paths": str(path),
        }
        for item in unique:
            fam = item.get("dataset_family", "unknown")
            stats["families"][fam] = stats["families"].get(fam, 0) + 1
            tt = item.get("task_type", "unknown")
            stats["task_types"][tt] = stats["task_types"].get(tt, 0) + 1

        return stats
