"""Neural Intelligence Engine — canonical model contracts.

Every specialist model must expose these dataclasses for consistent
inference, fusion, and telemetry across the system.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ModelDomain(Enum):
    VISION = "vision"
    TRADING = "trading"
    VOICE = "voice"
    PREDICTION = "prediction"
    PERSONALIZATION = "personalization"
    MULTIMODAL = "multimodal"
    GENERAL = "general"


class ModelModality(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    MULTIMODAL = "multimodal"
    STRUCTURED = "structured"
    TIME_SERIES = "time_series"


class ModelDeployment(Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class ModelStatus(Enum):
    ACTIVE = "active"
    STAGED = "staged"
    TESTING = "testing"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    RETIRED = "retired"


class LatencyClass(Enum):
    REALTIME = "realtime"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"


@dataclass(frozen=True)
class ModelSpec:
    """Immutable specification for a registered model."""
    model_id: str
    domain: ModelDomain
    version: str
    modality: ModelModality
    capabilities: list[str]
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    latency_class: LatencyClass
    deployment: ModelDeployment
    resource_requirements: dict[str, Any]
    confidence_support: bool = True
    uncertainty_support: bool = True
    provider: str = ""
    description: str = ""
    max_input_tokens: int = 8192
    max_output_tokens: int = 4096

    def matches_modality(self, modality: ModelModality) -> bool:
        return self.modality == modality or self.modality == ModelModality.MULTIMODAL

    def matches_domain(self, domain: ModelDomain) -> bool:
        return self.domain == domain or self.domain == ModelDomain.GENERAL


@dataclass
class ModelResult:
    """Normalized output from any specialist model inference."""
    model_id: str
    output: Any
    confidence: float
    uncertainty: float
    latency_ms: float
    timestamp: float
    source: str
    warnings: list[str] = field(default_factory=list)
    quality: float = 1.0
    version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    cached: bool = False

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.7

    @property
    def is_uncertain(self) -> bool:
        return self.uncertainty >= 0.5 or self.confidence < 0.3

    @property
    def is_stale(self, max_age_s: float = 30.0) -> bool:
        return (time.time() - self.timestamp) > max_age_s

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "confidence": round(self.confidence, 3),
            "uncertainty": round(self.uncertainty, 3),
            "latency_ms": round(self.latency_ms, 1),
            "quality": round(self.quality, 3),
            "cached": self.cached,
            "warnings": self.warnings,
            "source": self.source,
        }


@dataclass
class InferenceRequest:
    """Canonical request to the neural engine."""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    domain: ModelDomain = ModelDomain.GENERAL
    modality: ModelModality = ModelModality.TEXT
    input_data: Any = None
    context: dict[str, Any] = field(default_factory=dict)
    preferred_model_id: Optional[str] = None
    latency_budget_ms: float = 5000.0
    confidence_threshold: float = 0.3
    require_uncertainty: bool = False
    fallback_allowed: bool = True
    cache_key: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not hasattr(self, 'request_id') or not self.request_id:
            self.request_id = uuid.uuid4().hex[:12]


@dataclass
class FusionResult:
    """Result of combining multiple specialist model outputs."""
    request_id: str
    domain: ModelDomain
    outputs: list[ModelResult]
    fused_output: Any
    combined_confidence: float
    combined_uncertainty: float
    disagreement_score: float
    ensemble_size: int
    latency_ms: float
    warnings: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def has_disagreement(self) -> bool:
        return self.disagreement_score > 0.3

    @property
    def is_reliable(self) -> bool:
        return (
            self.combined_confidence >= 0.6
            and self.combined_uncertainty < 0.4
            and not self.has_disagreement
        )
