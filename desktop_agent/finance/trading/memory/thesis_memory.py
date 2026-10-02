"""
MYRAA Trading Intelligence — Trade Thesis Memory

Persistent storage for trade theses. Tracks the lifecycle of each thesis:
creation → active monitoring → resolution (win/loss/invalidated/expired).
Enables pattern recognition by querying similar historical setups.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from desktop_agent.finance.trading.models import TradeThesis


_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_THESIS_FILE = _DATA_DIR / "trade_theses.json"


def _load_json() -> List[Dict[str, Any]]:
    if not _THESIS_FILE.exists():
        return []
    try:
        with open(_THESIS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, OSError):
        return []


def _save_json(records: List[Dict[str, Any]]) -> None:
    with open(_THESIS_FILE, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)


def _dt_from_iso(raw: Optional[str]) -> Optional[datetime]:
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _record_to_thesis(rec: Dict[str, Any]) -> TradeThesis:
    return TradeThesis(
        thesis_id=rec.get("thesis_id", ""),
        symbol=rec.get("symbol", ""),
        direction=rec.get("direction", ""),
        entry_rationale=rec.get("entry_rationale", ""),
        invalidation=rec.get("invalidation", ""),
        date_created=_dt_from_iso(rec.get("date_created")) or datetime.utcnow(),
        date_resolved=_dt_from_iso(rec.get("date_resolved")),
        outcome=rec.get("outcome", ""),
        entry_price=rec.get("entry_price", 0.0),
        exit_price=rec.get("exit_price", 0.0),
        pnl_percent=rec.get("pnl_percent", 0.0),
        status=rec.get("status", "ACTIVE"),
        post_trade_review=rec.get("post_trade_review", ""),
        tags=rec.get("tags", []),
        metadata=rec.get("metadata", {}),
    )


class TradeThesisMemory:
    """Persistent memory for trade theses backed by a local JSON file.

    Provides CRUD-like operations, lookup by symbol/status, and
    similarity queries based on setup type and direction.
    """

    def __init__(self, file_path: Optional[str] = None) -> None:
        self._file_path = Path(file_path) if file_path else _THESIS_FILE
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        if not self._file_path.exists():
            return []
        try:
            with open(self._file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, records: List[Dict[str, Any]]) -> None:
        with open(self._file_path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)

    def _find_idx(self, records: List[Dict[str, Any]], thesis_id: str) -> Optional[int]:
        for i, r in enumerate(records):
            if r.get("thesis_id") == thesis_id:
                return i
        return None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def store(self, thesis: TradeThesis) -> TradeThesis:
        """Persist a thesis to the JSON file.

        If the thesis has no ``thesis_id`` a new one is generated.
        If a thesis with the same ``thesis_id`` already exists it is
        updated in-place.
        """
        if not thesis.thesis_id:
            thesis.thesis_id = f"TH-{uuid.uuid4().hex[:8]}"

        records = self._load()
        idx = self._find_idx(records, thesis.thesis_id)

        rec = thesis.to_dict()
        if idx is not None:
            records[idx] = rec
        else:
            records.append(rec)

        self._save(records)
        return thesis

    def get_by_symbol(self, symbol: str) -> List[TradeThesis]:
        """Return all theses for a given symbol (any status)."""
        symbol_upper = symbol.upper()
        records = self._load()
        return [
            _record_to_thesis(r)
            for r in records
            if r.get("symbol", "").upper() == symbol_upper
        ]

    def get_active(self) -> List[TradeThesis]:
        """Return all theses whose status is ACTIVE."""
        records = self._load()
        return [
            _record_to_thesis(r)
            for r in records
            if r.get("status", "") == "ACTIVE"
        ]

    def resolve(
        self,
        thesis_id: str,
        outcome: str,
        exit_price: float,
    ) -> Optional[TradeThesis]:
        """Resolve a thesis with an outcome and exit price.

        ``outcome`` should be one of: WIN, LOSS, INVALIDATED, EXPIRED,
        BREAKEVEN, MANUAL.

        Returns the updated thesis or ``None`` if the thesis was not found.
        """
        records = self._load()
        idx = self._find_idx(records, thesis_id)
        if idx is None:
            return None

        thesis = _record_to_thesis(records[idx])
        thesis.outcome = outcome.upper()
        thesis.exit_price = exit_price
        thesis.date_resolved = datetime.utcnow()
        thesis.status = "RESOLVED"

        if thesis.entry_price > 0:
            if thesis.direction.upper() == "LONG":
                thesis.pnl_percent = ((exit_price - thesis.entry_price) / thesis.entry_price) * 100
            else:
                thesis.pnl_percent = ((thesis.entry_price - exit_price) / thesis.entry_price) * 100

        records[idx] = thesis.to_dict()
        self._save(records)
        return thesis

    def get_history(self, limit: int = 50) -> List[TradeThesis]:
        """Return recent theses (resolved or active), most recent first.

        ``limit`` caps the number of returned records.
        """
        records = self._load()
        sorted_recs = sorted(
            records,
            key=lambda r: r.get("date_created", ""),
            reverse=True,
        )
        return [_record_to_thesis(r) for r in sorted_recs[:limit]]

    def get_similar_setup(
        self,
        setup_type: str,
        direction: str,
    ) -> List[TradeThesis]:
        """Find resolved theses that share the same setup type and direction.

        ``setup_type`` is matched case-insensitively against the thesis
        ``tags`` list (the first tag is treated as the setup type by
        convention). ``direction`` is LONG or SHORT.
        """
        setup_lower = setup_type.lower()
        direction_upper = direction.upper()
        records = self._load()
        matches: List[TradeThesis] = []
        for r in records:
            if r.get("status") != "RESOLVED":
                continue
            if r.get("direction", "").upper() != direction_upper:
                continue
            tags = [t.lower() for t in r.get("tags", [])]
            if setup_lower in tags:
                matches.append(_record_to_thesis(r))
        return matches
