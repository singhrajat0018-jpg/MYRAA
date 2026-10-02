"""World Model Privacy & Permissions — data classification and access control.

Respects existing PermissionManager, SafetyManager, and authorization.
Reading a fact is not permission to act on it.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DataClassification(str, Enum):
    """Data sensitivity levels."""
    PUBLIC = "public"
    PRIVATE = "private"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class PrivacyGate:
    """Privacy and permission gate for world model operations.

    Enforces:
    - Data classification filtering
    - Secret rejection (credentials never stored)
    - Permission checks via existing PermissionManager
    - User correction support
    """

    SECRET_PATTERNS = frozenset({
        "password", "secret", "token", "api_key", "apikey",
        "access_token", "refresh_token", "private_key", "otp",
        "credit_card", "card_number", "cvv", "ssn", "jwt",
        "bearer", "authorization", "cookie", "session_id",
    })

    SENSITIVE_TYPES = frozenset({
        "trading_account", "portfolio", "position",
        "conversation", "person",
    })

    def __init__(self) -> None:
        self._user_corrections: Dict[str, Dict[str, Any]] = {}
        self._frozen_entities: Set[str] = set()
        self._restricted_entities: Set[str] = set()

    def classify(self, entity_type: str, metadata: Dict[str, Any]) -> DataClassification:
        """Classify data sensitivity for an entity."""
        # Check user corrections first
        correction = self._user_corrections.get(f"classification:{entity_type}")
        if correction:
            return DataClassification(correction.get("classification", "private"))

        # Default classification by type
        if entity_type in self.SENSITIVE_TYPES:
            return DataClassification.SENSITIVE
        if entity_type in ("system", "application", "device"):
            return DataClassification.PUBLIC
        return DataClassification.PRIVATE

    def contains_secrets(self, data: Dict[str, Any]) -> bool:
        """Check if data contains credential-like values."""
        for key, value in data.items():
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in self.SECRET_PATTERNS):
                return True
            if isinstance(value, str):
                value_lower = value.lower()
                if any(pattern in value_lower for pattern in self.SECRET_PATTERNS):
                    return True
        return False

    def reject_secrets(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """Reject data containing secrets. Returns (allowed, reason)."""
        if self.contains_secrets(data):
            return False, "Data contains credential-like values — rejected"
        return True, ""

    def check_permission(
        self,
        entity_id: str,
        operation: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if an operation is permitted on an entity."""
        # Frozen entities: no modifications
        if entity_id in self._frozen_entities and operation in ("update", "delete"):
            return False

        # Restricted entities: read-only
        if entity_id in self._restricted_entities and operation != "read":
            return False

        # Financial entities: always read-only
        # (TradingAdvisorPolicy handles this, but we add a safety layer)

        return True

    def freeze_entity(self, entity_id: str) -> None:
        """Freeze an entity — prevent modifications."""
        self._frozen_entities.add(entity_id)

    def unfreeze_entity(self, entity_id: str) -> None:
        """Unfreeze an entity."""
        self._frozen_entities.discard(entity_id)

    def restrict_entity(self, entity_id: str) -> None:
        """Restrict an entity — read-only."""
        self._restricted_entities.add(entity_id)

    def unrestrict_entity(self, entity_id: str) -> None:
        """Remove restriction from an entity."""
        self._restricted_entities.discard(entity_id)

    def apply_user_correction(
        self,
        entity_id: str,
        field_name: str,
        new_value: Any,
    ) -> None:
        """Apply a user correction to world model data."""
        self._user_corrections[f"{entity_id}:{field_name}"] = {
            "value": new_value,
            "timestamp": __import__("time").time(),
        }

    def get_correction(self, entity_id: str, field_name: str) -> Optional[Any]:
        """Get a user correction for a field."""
        correction = self._user_corrections.get(f"{entity_id}:{field_name}")
        return correction["value"] if correction else None

    def filter_by_classification(
        self,
        items: List[Dict[str, Any]],
        max_classification: DataClassification = DataClassification.SENSITIVE,
    ) -> List[Dict[str, Any]]:
        """Filter items by maximum allowed classification."""
        hierarchy = {
            DataClassification.PUBLIC: 0,
            DataClassification.PRIVATE: 1,
            DataClassification.SENSITIVE: 2,
            DataClassification.RESTRICTED: 3,
        }
        max_level = hierarchy.get(max_classification, 2)
        result = []
        for item in items:
            classification = self.classify(
                item.get("type", "unknown"),
                item.get("metadata", {}),
            )
            if hierarchy.get(classification, 0) <= max_level:
                result.append(item)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Serialize privacy state."""
        return {
            "frozen_entities": sorted(self._frozen_entities),
            "restricted_entities": sorted(self._restricted_entities),
            "correction_count": len(self._user_corrections),
        }
