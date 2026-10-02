"""
MYRAA Memory 2.0 — M17: store repair tooling.

Safe, idempotent, observable, non-destructive and reversible repair for the
unified memory store.

What it does
------------
- Scans every record; validates it (``validate_memory_record``).
- QUARANTINES (never deletes) invalid records and any record still containing
  sensitive data — they are moved to a ``<path>.quarantine.<ts>.json`` sidecar.
- REBUILDS/REINDEXES: recomputes content fingerprints for every kept record.
- DEDUPS exact/equivalent duplicates, keeping the oldest copy.
- Rewrites the store only when something changed (idempotent on a clean store).

Reversibility
-------------
``list_quarantine()`` shows quarantined records; ``restore_quarantine()``
re-injects them into a manager/store.

Run:
    python -m desktop_agent.brain.memory.repair [path] [--restore-quarantine]
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

from desktop_agent.brain.memory import persistence
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryStatus,
    validate_memory_record,
    memories_are_equivalent,
)

log = logging.getLogger(__name__)


@dataclass
class RepairReport:
    path: str
    scanned: int = 0
    invalid: int = 0
    sensitive: int = 0
    quarantine_file: str = ""
    quarantined_ids: List[str] = field(default_factory=list)
    rebuilt_fingerprints: int = 0
    duplicates_removed: int = 0
    active_before: int = 0
    active_after: int = 0
    repaired: bool = False
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "scanned": self.scanned,
            "invalid": self.invalid,
            "sensitive": self.sensitive,
            "quarantine_file": self.quarantine_file,
            "quarantined_ids": self.quarantined_ids,
            "rebuilt_fingerprints": self.rebuilt_fingerprints,
            "duplicates_removed": self.duplicates_removed,
            "active_before": self.active_before,
            "active_after": self.active_after,
            "repaired": self.repaired,
            "errors": self.errors,
        }


def repair_store(path: Optional[str] = None) -> RepairReport:
    """
    Repair the unified memory store in place. Idempotent + non-destructive.

    Parses the raw store (not the scrubbing loader) so sensitive records are
    quarantined and REPORTED rather than silently dropped.

    Args:
        path: Store path. Defaults to ``persistence.default_memory_file()``.

    Returns:
        RepairReport describing everything scanned and fixed.
    """
    store_path = path or persistence.default_memory_file()
    report = RepairReport(path=store_path)

    if not os.path.exists(store_path):
        report.errors.append(f"store not found: {store_path}")
        return report

    try:
        raw = persistence.load_json_safe(store_path, {})
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"load failed: {exc}")
        return report
    if not isinstance(raw, dict):
        report.errors.append("store is not a valid JSON object")
        return report
    items = raw.get("records", [])
    if not isinstance(items, list):
        report.errors.append("store has no records list")
        return report
    report.scanned = len(items)
    report.active_before = len(items)

    # 1) Parse + quarantine invalid/sensitive records (never destroy)
    quarantined: List[MemoryRecord] = []
    malformed: List[dict] = []
    kept: List[MemoryRecord] = []
    for item in items:
        if not isinstance(item, dict):
            report.invalid += 1
            malformed.append(item)
            continue
        try:
            record = MemoryRecord.from_dict(item)
        except Exception as exc:  # noqa: BLE001
            report.invalid += 1
            malformed.append(item)
            continue
        issues = validate_memory_record(record)
        if issues:
            report.invalid += 1
            quarantined.append(record)
        elif persistence._contains_sensitive_data(item):
            report.sensitive += 1
            quarantined.append(record)
        else:
            kept.append(record)
    report.quarantined_ids = [r.id for r in quarantined]

    # 2) Rebuild/reindex: recompute fingerprints, track actual changes
    for record in kept:
        before = record.fingerprint
        record.update_fingerprint()
        if record.fingerprint != before:
            report.rebuilt_fingerprints += 1

    # 3) Dedup exact/equivalent duplicates (keep oldest copy)
    unique: List[MemoryRecord] = []
    for record in kept:
        if any(memories_are_equivalent(one, record) for one in unique):
            report.duplicates_removed += 1
            quarantined.append(record)
        else:
            unique.append(record)

    # 4) Quarantine sidecar (never destroy; includes malformed raw items)
    if quarantined or malformed:
        ts = int(time.time())
        report.quarantine_file = f"{store_path}.quarantine.{ts}.json"
        payload = {"version": 2, "saved_at": time.time(),
                   "records": [r.to_dict() for r in quarantined] + malformed}
        persistence.atomic_write_json(report.quarantine_file, payload)

    report.active_after = len(unique)
    report.repaired = (report.invalid > 0 or report.sensitive > 0
                       or report.duplicates_removed > 0
                       or report.rebuilt_fingerprints > 0)

    # 5) Rewrite only when something changed (idempotent)
    if report.repaired:
        persistence.save_unified_memory_records(unique, store_path)

    return report


def list_quarantine(path: str) -> List[MemoryRecord]:
    """Load and return the records stored in a quarantine sidecar."""
    if not os.path.exists(path):
        return []
    return persistence.load_unified_memory_records(path)


def restore_quarantine(quarantine_path: str,
                       target_path: Optional[str] = None) -> RepairReport:
    """
    Re-inject quarantined records back into a store (reversible repair).

    Args:
        quarantine_path: Quarantine sidecar file created by ``repair_store``.
        target_path: Store to restore into. Defaults to the active store.

    Returns:
        RepairReport of the restore operation.
    """
    store_path = target_path or persistence.default_memory_file()
    report = RepairReport(path=store_path)

    quarantined = list_quarantine(quarantine_path)
    report.scanned = len(quarantined)
    if not quarantined:
        return report

    existing = persistence.load_unified_memory_records(store_path)
    existing_ids = {r.id for r in existing}
    restored = [r for r in quarantined if r.id not in existing_ids]
    skipped = [r for r in quarantined if r.id in existing_ids]

    for record in restored:
        record.status = MemoryStatus.ACTIVE
        record.update_fingerprint()
    merged = existing + restored
    persistence.save_unified_memory_records(merged, store_path)

    report.invalid = len(skipped)  # reused field: already-present (not re-added)
    report.quarantined_ids = [r.id for r in restored]
    report.rebuilt_fingerprints = len(restored)
    report.active_before = len(existing)
    report.active_after = len(merged)
    report.repaired = len(restored) > 0
    return report


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="MYRAA Memory 2.0 store repair")
    parser.add_argument("path", nargs="?", default=None, help="store path")
    parser.add_argument("--restore-quarantine", metavar="QFILE",
                        help="restore a quarantine sidecar into the store")
    args = parser.parse_args(argv)

    if args.restore_quarantine:
        report = restore_quarantine(args.restore_quarantine, args.path)
    else:
        report = repair_store(args.path)

    print("\nMYRAA Memory 2.0 Repair Report")
    print("=" * 60)
    for key, value in report.as_dict().items():
        print(f"{key:<20} {value}")
    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(_main())