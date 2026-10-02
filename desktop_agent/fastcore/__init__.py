"""MYRAA FastCore — Ultra-fast local routing/classification model.

FastCore handles repetitive, structured, routing, classification, and
simple assistant decisions locally with very low latency. It minimizes
calls to larger models (Qwen3.5, Gemma 3, MiniMax-M3) unless those
systems are actually required.
"""

from .models import (
    FastCoreOutput,
    TrainingExample,
    FastCoreConfig,
    TaskType,
    ResponseMode,
    InformationSource,
    Complexity,
    ModelRoute,
    SafetyClass,
)
from .classifier import FastCoreClassifier
from .dataset_generator import DatasetGenerator

__all__ = [
    "FastCoreOutput",
    "TrainingExample",
    "FastCoreConfig",
    "TaskType",
    "ResponseMode",
    "InformationSource",
    "Complexity",
    "ModelRoute",
    "SafetyClass",
    "FastCoreClassifier",
    "DatasetGenerator",
]
