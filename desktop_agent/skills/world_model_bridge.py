"""WorldModelBridge — auto-updates World Model after verified worker completion.

Only updates AFTER: successful verification + sufficient confidence + known entity mapping.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorldModelBridge:
    """Bridges worker results to World Model updates.

    Rules:
    - Only update AFTER verified completion
    - Only update with sufficient confidence
    - Use CONFIDENT/INFERRED/UNKNOWN for state confidence
    - Do not create duplicate entities
    - Reuse Phase H entity/relationship APIs
    """

    def __init__(self) -> None:
        self._world_model = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            from ..world_model.model import WorldModel
            self._world_model = WorldModel()
            self._loaded = True
            logger.info("WorldModelBridge loaded")
        except ImportError:
            logger.warning("WorldModel not available — world updates disabled")
            self._loaded = True

    def update_after_worker(
        self,
        worker_id: str,
        skill_id: str,
        task_description: str,
        result: Dict[str, Any],
        verification: Dict[str, Any],
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Update World Model after verified worker completion."""
        self._ensure_loaded()
        if self._world_model is None:
            return False

        if not verification.get("verified", False):
            logger.debug("Skipping world update: verification failed")
            return False

        confidence = verification.get("confidence", 0.0)
        if confidence < 0.5:
            logger.debug("Skipping world update: low confidence %.2f", confidence)
            return False

        try:
            return self._do_update(
                worker_id, skill_id, task_description,
                result, verification, artifacts or [],
            )
        except Exception as exc:
            logger.error("World model update failed: %s", exc)
            return False

    def _do_update(
        self,
        worker_id: str,
        skill_id: str,
        task_description: str,
        result: Dict[str, Any],
        verification: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> bool:
        """Perform the actual world model update."""
        from ..world_model.entity import EntityType, EntityState, EntitySource
        from ..world_model.events import WorldEvent, EventType

        wm = self._world_model
        task_lower = task_description.lower()

        # Map skill to entity type
        entity_type = self._skill_to_entity_type(skill_id, task_lower)
        entity_state = self._result_to_state(result)

        # Find or create the relevant entity
        entity_name = self._extract_entity_name(skill_id, task_description, result)
        entities = wm.find_entity(entity_type=entity_type, name=entity_name, limit=1)

        if entities:
            # Update existing entity
            entity = entities[0]
            wm.update_entity(
                entity.id,
                state=entity_state,
                confidence=verification.get("confidence", 0.5),
                metadata={"last_worker": worker_id, "last_task": task_description},
            )
        else:
            # Create new entity
            entity = wm.create_entity(
                entity_type=entity_type,
                name=entity_name,
                state=entity_state,
                source=EntitySource.SYSTEM,
                confidence=verification.get("confidence", 0.5),
                tags={skill_id},
                description=task_description,
            )

        # Update artifacts as file entities
        for artifact in artifacts:
            if artifact.get("path"):
                file_entities = wm.find_entity(
                    entity_type=EntityType.FILE,
                    name=artifact["path"],
                    limit=1,
                )
                if not file_entities:
                    wm.create_entity(
                        entity_type=EntityType.FILE,
                        name=artifact["path"],
                        state=EntityState.ACTIVE,
                        source=EntitySource.SYSTEM,
                        confidence=0.9,
                        tags={skill_id},
                    )

        # Emit event
        wm.ingest_event(WorldEvent(
            id=f"evt_worker_{worker_id}_{int(time.time())}",
            type=EventType.ENTITY_UPDATED,
            entity_id=entity.id if entities else "",
            timestamp=time.time(),
            data={
                "worker": worker_id,
                "skill": skill_id,
                "task": task_description,
                "confidence": verification.get("confidence", 0.5),
            },
            source="worker_system",
            importance=0.5,
        ))

        logger.info(
            "World model updated: %s/%s (confidence: %.2f)",
            entity_type.value, entity_name, verification.get("confidence", 0.5),
        )
        return True

    def _skill_to_entity_type(self, skill_id: str, task_lower: str):
        from ..world_model.entity import EntityType
        mapping = {
            "coding": EntityType.FILE,
            "research": EntityType.TASK,
            "trading": EntityType.STOCK,
            "vision": EntityType.APPLICATION,
            "desktop": EntityType.APPLICATION,
            "projects": EntityType.PROJECT,
            "documents": EntityType.FILE,
            "automation": EntityType.TASK,
            "diagnostics": EntityType.SYSTEM,
            "memory": EntityType.MEMORY,
            "verification": EntityType.TASK,
        }
        return mapping.get(skill_id, EntityType.TASK)

    def _result_to_state(self, result: Dict[str, Any]):
        from ..world_model.entity import EntityState
        if result.get("ok"):
            return EntityState.COMPLETED
        return EntityState.FAILED

    def _extract_entity_name(
        self,
        skill_id: str,
        task_description: str,
        result: Dict[str, Any],
    ) -> str:
        """Extract a meaningful entity name from the task/result."""
        # Try to get name from result
        result_data = result.get("result", {})
        if isinstance(result_data, dict):
            for key in ("name", "path", "application", "symbol", "query"):
                if key in result_data:
                    return str(result_data[key])

        # Fallback: use task description (truncated)
        return task_description[:50] if task_description else f"task_{skill_id}"


# Global singleton
_world_model_bridge: Optional[WorldModelBridge] = None


def get_world_model_bridge() -> WorldModelBridge:
    global _world_model_bridge
    if _world_model_bridge is None:
        _world_model_bridge = WorldModelBridge()
    return _world_model_bridge
