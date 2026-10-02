"""NeuralRouter — NeuralEngine-assisted skill selection with heuristic fallback.

Architecture:
TaskRouter → candidate skills → NeuralEngine scoring (optional) →
SkillRegistry validation → permission check → AgentPlanner

NeuralEngine assists ranking. It must NOT bypass permissions, safety,
SkillRegistry, Super-Brain, or verification.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .skill import Skill, SkillDomain
from .registry import SkillRegistry

logger = logging.getLogger(__name__)


class NeuralRouter:
    """NeuralEngine-assisted skill routing with heuristic fallback.

    When NeuralEngine is unavailable, falls back to existing heuristic routing.
    """

    def __init__(self, registry: Optional[SkillRegistry] = None) -> None:
        self._registry = registry or SkillRegistry()
        self._neural_engine = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            from ..neural_engine.engine import NeuralEngine
            self._neural_engine = NeuralEngine.singleton()
            logger.info("NeuralRouter: NeuralEngine available")
        except Exception:
            logger.info("NeuralRouter: NeuralEngine unavailable — using heuristic fallback")
            self._neural_engine = None

    def rank_skills(
        self,
        candidates: List[Skill],
        task_description: str,
        task_type: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Skill, float, str]]:
        """Rank candidate skills for a task.

        Returns list of (skill, confidence, reason) tuples, sorted by confidence.
        """
        if not candidates:
            return []

        self._ensure_loaded()

        # Try NeuralEngine ranking
        if self._neural_engine is not None:
            try:
                return self._neural_rank(candidates, task_description, task_type, context)
            except Exception as exc:
                logger.warning("NeuralEngine ranking failed, using heuristic: %s", exc)

        # Heuristic fallback
        return self._heuristic_rank(candidates, task_description, task_type, context)

    def _neural_rank(
        self,
        candidates: List[Skill],
        task_description: str,
        task_type: str,
        context: Optional[Dict[str, Any]],
    ) -> List[Tuple[Skill, float, str]]:
        """Use NeuralEngine to rank skills."""
        from ..neural_engine.model_contract import InferenceRequest, ModelDomain

        # Map task_type to NeuralEngine domain
        domain_map = {
            "coding_task": ModelDomain.GENERAL,
            "research": ModelDomain.GENERAL,
            "trading_task": ModelDomain.TRADING,
            "vision_task": ModelDomain.VISION,
            "desktop_action": ModelDomain.GENERAL,
        }
        domain = domain_map.get(task_type, ModelDomain.GENERAL)

        # Build inference request
        skill_names = [s.name for s in candidates]
        request = InferenceRequest(
            domain=domain,
            input_data={
                "task": task_description,
                "task_type": task_type,
                "candidates": skill_names,
                "context": context or {},
            },
            latency_budget_ms=100.0,
            confidence_threshold=0.3,
        )

        result = self._neural_engine.infer(request)

        if result.confidence < 0.3:
            logger.debug("NeuralEngine low confidence (%.2f), using heuristic", result.confidence)
            return self._heuristic_rank(candidates, task_description, task_type, context)

        # Parse neural output to rank candidates
        output = result.output
        if isinstance(output, dict) and "ranking" in output:
            ranking = output["ranking"]
            ranked = []
            for skill in candidates:
                score = ranking.get(skill.name, 0.5)
                ranked.append((skill, score, f"NeuralEngine score: {score:.2f}"))
            ranked.sort(key=lambda x: x[1], reverse=True)
            return ranked

        # If neural output doesn't have ranking, fall back
        return self._heuristic_rank(candidates, task_description, task_type, context)

    def _heuristic_rank(
        self,
        candidates: List[Skill],
        task_description: str,
        task_type: str,
        context: Optional[Dict[str, Any]],
    ) -> List[Tuple[Skill, float, str]]:
        """Heuristic skill ranking based on health, capabilities, and task match."""
        scored = []
        task_lower = task_description.lower()

        for skill in candidates:
            score = 0.5  # base
            reasons = []

            # Health score
            health_score = skill.health.success_rate
            score += health_score * 0.2
            if health_score > 0.8:
                reasons.append(f"high success rate ({health_score:.2f})")

            # Task match
            if skill.name.lower() in task_lower:
                score += 0.2
                reasons.append("name match in task")

            # Domain match
            if task_type and skill.domain.value in task_type.lower():
                score += 0.1
                reasons.append(f"domain match ({skill.domain.value})")

            # Latency (lower is better)
            if skill.health.avg_latency_ms > 0:
                latency_bonus = max(0, 0.1 - skill.health.avg_latency_ms / 10000)
                score += latency_bonus

            # Availability
            if skill.state.value == "available":
                score += 0.05
            elif skill.state.value == "degraded":
                score -= 0.1
                reasons.append("degraded")

            reason = "; ".join(reasons) if reasons else "heuristic default"
            scored.append((skill, min(1.0, score), reason))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def select_best(
        self,
        domain: SkillDomain,
        task_description: str = "",
        task_type: str = "",
        required_tools: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Skill]:
        """Select the best skill for a task."""
        candidates = self._registry.discover(domain=domain)
        if not candidates:
            candidates = self._registry.discover(domain=domain, state=None)

        if not candidates:
            return None

        # Filter by required tools
        if required_tools:
            candidates = [
                s for s in candidates
                if all(t in s.required_tools for t in required_tools)
            ]

        if not candidates:
            return None

        ranked = self.rank_skills(candidates, task_description, task_type, context)
        if ranked:
            return ranked[0][0]
        return candidates[0]


# Global singleton
_neural_router: Optional[NeuralRouter] = None


def get_neural_router() -> NeuralRouter:
    global _neural_router
    if _neural_router is None:
        _neural_router = NeuralRouter()
    return _neural_router
