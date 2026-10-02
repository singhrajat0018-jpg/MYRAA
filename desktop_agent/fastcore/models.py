"""MYRAA FastCore — Data Models.

Structured output schema for the FastCore local routing/classification model.
FastCore produces a compact, typed routing decision — never free-form prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums (mirrors TaskRouter taxonomy)
# ---------------------------------------------------------------------------

class TaskType(str, Enum):
    """Canonical task classification."""
    CONVERSATION = "conversation"
    DIRECT_KNOWLEDGE = "direct_knowledge"
    LOCAL_REASONING = "local_reasoning"
    CURRENT_INFORMATION = "current_information"
    WEB_RESEARCH = "web_research"
    DESKTOP_ACTION = "desktop_action"
    BROWSER_ACTION = "browser_action"
    VISION_TASK = "vision_task"
    FILE_TASK = "file_task"
    TRADING_TASK = "trading_task"
    CODING_TASK = "coding_task"
    DESIGN_TASK = "design_task"
    MULTIMODAL_TASK = "multimodal_task"
    WEATHER_TASK = "weather_task"
    NEWS_TASK = "news_task"


class ResponseMode(str, Enum):
    """How to produce the response."""
    FAST_ANSWER = "fast_answer"
    REASONING = "reasoning"
    RESEARCH = "research"
    ACTION = "action"
    VISION = "vision"
    TRADING = "trading"
    CODING = "coding"
    DESIGN = "design"
    MULTIMODAL = "multimodal"
    WEATHER = "weather"
    NEWS = "news"


class InformationSource(str, Enum):
    """Where to get information."""
    NONE = "none"
    LOCAL_MODEL = "local_model"
    WIKIPEDIA = "wikipedia"
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    SCREEN = "screen"
    TOOL_EXECUTION = "tool_execution"
    WEATHER_API = "weather_api"
    NEWS_API = "news_api"


class Complexity(str, Enum):
    """Task complexity level."""
    TRIVIAL = "trivial"        # greetings, acknowledgements
    SIMPLE = "simple"          # factual questions, simple commands
    MODERATE = "moderate"      # reasoning, multi-step desktop
    COMPLEX = "complex"        # research, coding, design
    EXPERT = "expert"          # deep analysis, multi-system


class ModelRoute(str, Enum):
    """Which model/system to route to."""
    FASTCORE_DIRECT = "fastcore_direct"      # FastCore handles directly
    LOCAL_SMALL = "local_small"              # Qwen3.5 4B
    LOCAL_VISION = "local_vision"            # Gemma3 4B (vision)
    LOCAL_LARGE = "local_large"              # MiniMax-M3
    DETERMINISTIC = "deterministic"          # No model needed


class SafetyClass(str, Enum):
    """Safety classification."""
    SAFE = "safe"
    NEEDS_VERIFICATION = "needs_verification"
    DANGEROUS = "dangerous"
    FINANCIAL = "financial"
    FORBIDDEN = "forbidden"


# ---------------------------------------------------------------------------
# Structured Output
# ---------------------------------------------------------------------------

@dataclass
class FastCoreOutput:
    """Structured output from the FastCore model.

    This is what the model produces on every inference call.
    All fields are typed enums or bounded values — never free-form text.
    """
    task_type: TaskType
    response_mode: ResponseMode
    information_source: InformationSource
    complexity: Complexity
    model_route: ModelRoute
    safety_class: SafetyClass
    confidence: float                  # 0.0 – 1.0
    tools_required: bool
    tool_names: List[str] = field(default_factory=list)
    freshness_required: bool = False
    entities: Dict[str, str] = field(default_factory=dict)
    escalate: bool = False             # True → hand off to stronger model
    reasoning: str = ""                # short, for logging only

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "response_mode": self.response_mode.value,
            "information_source": self.information_source.value,
            "complexity": self.complexity.value,
            "model_route": self.model_route.value,
            "safety_class": self.safety_class.value,
            "confidence": round(self.confidence, 4),
            "tools_required": self.tools_required,
            "tool_names": self.tool_names,
            "freshness_required": self.freshness_required,
            "entities": self.entities,
            "escalate": self.escalate,
            "reasoning": self.reasoning,
        }


@dataclass
class TrainingExample:
    """A single training example for FastCore."""
    input_text: str
    input_type: str                    # "user_message" | "voice_command" | "text_command"
    task_type: TaskType
    response_mode: ResponseMode
    information_source: InformationSource
    complexity: Complexity
    model_route: ModelRoute
    safety_class: SafetyClass
    tools_required: bool
    tool_names: List[str] = field(default_factory=list)
    freshness_required: bool = False
    entities: Dict[str, str] = field(default_factory=dict)
    escalate: bool = False
    confidence: float = 0.9
    teacher_votes: Dict[str, str] = field(default_factory=dict)
    final_label: str = ""              # resolved label after teacher disagreement
    dataset_family: str = ""           # which dataset family this belongs to

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_text": self.input_text,
            "input_type": self.input_type,
            "task_type": self.task_type.value,
            "response_mode": self.response_mode.value,
            "information_source": self.information_source.value,
            "complexity": self.complexity.value,
            "model_route": self.model_route.value,
            "safety_class": self.safety_class.value,
            "tools_required": self.tools_required,
            "tool_names": self.tool_names,
            "freshness_required": self.freshness_required,
            "entities": self.entities,
            "escalate": self.escalate,
            "confidence": self.confidence,
            "teacher_votes": self.teacher_votes,
            "final_label": self.final_label,
            "dataset_family": self.dataset_family,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrainingExample":
        return cls(
            input_text=d["input_text"],
            input_type=d["input_type"],
            task_type=TaskType(d["task_type"]),
            response_mode=ResponseMode(d["response_mode"]),
            information_source=InformationSource(d["information_source"]),
            complexity=Complexity(d["complexity"]),
            model_route=ModelRoute(d["model_route"]),
            safety_class=SafetyClass(d["safety_class"]),
            tools_required=d["tools_required"],
            tool_names=d.get("tool_names", []),
            freshness_required=d.get("freshness_required", False),
            entities=d.get("entities", {}),
            escalate=d.get("escalate", False),
            confidence=d.get("confidence", 0.9),
            teacher_votes=d.get("teacher_votes", {}),
            final_label=d.get("final_label", ""),
            dataset_family=d.get("dataset_family", ""),
        )


@dataclass
class FastCoreConfig:
    """Configuration for FastCore model training and inference."""
    model_name: str = "fastcore"
    model_version: str = "0.1.0"
    dataset_version: str = "0.1.0"
    base_model: str = "Qwen/Qwen3-0.6B"     # smallest Qwen3 for base
    max_length: int = 256                      # input max tokens
    max_output: int = 128                      # output max tokens
    quantization: str = "INT8"                 # target quantization
    confidence_threshold: float = 0.8          # above = direct, below = escalate
    timeout_ms: float = 100.0                  # max inference latency
    cache_size: int = 1024                     # routing cache entries
