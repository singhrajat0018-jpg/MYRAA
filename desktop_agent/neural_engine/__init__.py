"""MYRAA Neural Intelligence Engine — Phase F.

Central neural intelligence substrate connecting specialist models
for vision, trading, design, voice, prediction, personalization,
and multimodal intelligence.

Architecture:
SUPER-BRAIN → NEURAL ENGINE → SPECIALIST MODELS → NEURAL FUSION
→ CONFIDENCE/UNCERTAINTY → DOMAIN ENGINES → VERIFICATION → SUPER-BRAIN

The Neural Engine ENHANCES existing MYRAA intelligence.
It does NOT replace Super-Brain, Memory, Vision, Trading, or Verification.
Neural predictions are EVIDENCE, not automatically truth.
"""

from __future__ import annotations

from .model_contract import (
    ModelSpec,
    ModelResult,
    InferenceRequest,
    FusionResult,
    ModelDomain,
    ModelModality,
    ModelDeployment,
    ModelStatus,
    LatencyClass,
)

from .engine import NeuralEngine

__all__ = [
    "NeuralEngine",
    "ModelSpec",
    "ModelResult",
    "InferenceRequest",
    "FusionResult",
    "ModelDomain",
    "ModelModality",
    "ModelDeployment",
    "ModelStatus",
    "LatencyClass",
]
