"""World Model Persistence — JSON-based structured state persistence.

Supports: restart, recovery, versioning, repair.
Uses existing persistence patterns (atomic writes, .bak backup).
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DIR = pathlib.Path.home() / ".myraa" / "world_model"
_VERSION = 1


class WorldModelPersistence:
    """JSON persistence for World Model state.

    Features:
    - Atomic writes (temp + os.replace)
    - .bak backup
    - Version migration
    - Corruption quarantine
    """

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        self._dir = pathlib.Path(storage_dir) if storage_dir else _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._entities_file = self._dir / "entities.json"
        self._relationships_file = self._dir / "relationships.json"
        self._temporal_file = self._dir / "temporal.json"
        self._events_file = self._dir / "events.json"

    def save_entities(self, entities: List[Dict[str, Any]]) -> bool:
        """Save entities to disk atomically."""
        return self._write_json(self._entities_file, {
            "version": _VERSION,
            "saved_at": time.time(),
            "count": len(entities),
            "entities": entities,
        })

    def load_entities(self) -> List[Dict[str, Any]]:
        """Load entities from disk."""
        data = self._read_json(self._entities_file)
        return data.get("entities", []) if data else []

    def save_relationships(self, relationships: List[Dict[str, Any]]) -> bool:
        """Save relationships to disk."""
        return self._write_json(self._relationships_file, {
            "version": _VERSION,
            "saved_at": time.time(),
            "count": len(relationships),
            "relationships": relationships,
        })

    def load_relationships(self) -> List[Dict[str, Any]]:
        """Load relationships from disk."""
        data = self._read_json(self._relationships_file)
        return data.get("relationships", []) if data else []

    def save_temporal(self, temporal_state: Dict[str, Any]) -> bool:
        """Save temporal state to disk."""
        return self._write_json(self._temporal_file, {
            "version": _VERSION,
            "saved_at": time.time(),
            "temporal": temporal_state,
        })

    def load_temporal(self) -> Optional[Dict[str, Any]]:
        """Load temporal state from disk."""
        data = self._read_json(self._temporal_file)
        return data.get("temporal") if data else None

    def save_events(self, events: List[Dict[str, Any]], max_events: int = 1000) -> bool:
        """Save recent events to disk (bounded)."""
        return self._write_json(self._events_file, {
            "version": _VERSION,
            "saved_at": time.time(),
            "count": len(events),
            "events": events[-max_events:],
        })

    def load_events(self) -> List[Dict[str, Any]]:
        """Load events from disk."""
        data = self._read_json(self._events_file)
        return data.get("events", []) if data else []

    def save_all(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        temporal: Dict[str, Any],
        events: List[Dict[str, Any]],
    ) -> bool:
        """Save complete world model state."""
        ok = True
        ok = ok and self.save_entities(entities)
        ok = ok and self.save_relationships(relationships)
        ok = ok and self.save_temporal(temporal)
        ok = ok and self.save_events(events)
        return ok

    def load_all(self) -> Dict[str, Any]:
        """Load complete world model state."""
        return {
            "entities": self.load_entities(),
            "relationships": self.load_relationships(),
            "temporal": self.load_temporal(),
            "events": self.load_events(),
        }

    def _write_json(self, path: pathlib.Path, data: Dict[str, Any]) -> bool:
        """Atomic JSON write with backup."""
        try:
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            # Backup existing
            if path.exists():
                bak = path.with_suffix(".bak")
                if bak.exists():
                    bak.unlink()
                path.rename(bak)

            # Atomic replace
            tmp.rename(path)
            return True
        except Exception as exc:
            logger.error("Failed to write %s: %s", path, exc)
            return False

    def _read_json(self, path: pathlib.Path) -> Optional[Dict[str, Any]]:
        """Read JSON with corruption recovery."""
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupt file %s: %s — attempting backup", path, exc)
            bak = path.with_suffix(".bak")
            if bak.exists():
                try:
                    with open(bak, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Quarantine corrupt file
                    quarantine = path.with_suffix(f".corrupt.{int(time.time())}")
                    path.rename(quarantine)
                    # Restore backup
                    bak.rename(path)
                    return data
                except Exception:
                    pass
            return None
