"""
MYRAA Memory 2.0 — M16: legacy migration + backward compatibility.

Migrates a legacy memory store (episodic+semantic, "version" < 2) into the
unified MemoryRecord store, reusing the existing per-record migration in
``persistence._migrate_legacy_to_unified``.

Pipeline (as designed):
    DETECT -> BACKUP -> NORMALIZE -> VALIDATE -> MIGRATE -> DEDUP
        -> CONFLICT CHECK -> VERIFY -> ACTIVATE

Safety contract
---------------
- Never destroys the original: a timestamped ``.pre-migration.bak`` is written
  before anything is touched, and an existing unified target is also backed up.
- Idempotent: a source that is already unified (version 2) is reported as
  ``already_unified`` and only verified; re-running is a safe no-op.
- Records that fail validation are dropped and counted (never written).
- DEDUP drops only exact/equivalent duplicates (``memories_are_equivalent``);
  CONFLICT CHECK counts (does not destroy) records that are similar but
  conflicting (same fingerprint, different content).

Run:
    python -m desktop_agent.brain.memory.migrate_legacy <legacy_path> [<unified_path>]
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import List, Optional

from desktop_agent.brain.memory import persistence
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryStatus,
    validate_memory_record,
    memories_are_equivalent,
    calculate_memory_similarity,
)

log = logging.getLogger(__name__)


@dataclass
class MigrationReport:
    source: str
    target: str
    detected: bool = False
    already_unified: bool = False
    backup_written: bool = False
    source_backup: str = ""
    target_backup: str = ""
    records_detected: int = 0
    records_invalid: int = 0
    records_duplicates: int = 0
    records_conflicts: int = 0
    records_migrated: int = 0
    verified: bool = False
    activated: bool = False
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "detected": self.detected,
            "already_unified": self.already_unified,
            "backup_written": self.backup_written,
            "source_backup": self.source_backup,
            "target_backup": self.target_backup,
            "records_detected": self.records_detected,
            "records_invalid": self.records_invalid,
            "records_duplicates": self.records_duplicates,
            "records_conflicts": self.records_conflicts,
            "records_migrated": self.records_migrated,
            "verified": self.verified,
            "activated": self.activated,
            "errors": self.errors,
        }


def _detect_format(raw: object) -> str:
    """Return 'unified', 'legacy', or 'unknown' for a parsed store dict."""
    if isinstance(raw, dict):
        version = raw.get("version")
        if version == 2 and isinstance(raw.get("records"), list):
            return "unified"
        if version == 1:
            return "legacy"
        if "episodic" in raw or "semantic" in raw:
            return "legacy"
    return "unknown"


def _backup(path: str) -> str:
    backup_path = f"{path}.pre-migration.{int(time.time())}.bak"
    shutil.copy2(path, backup_path)
    return backup_path


def _dedup(records: List[MemoryRecord]) -> List[MemoryRecord]:
    """Drop exact/equivalent duplicates, keeping the first (oldest) copy."""
    kept: List[MemoryRecord] = []
    for record in records:
        duplicate = any(memories_are_equivalent(kept_one, record)
                        for kept_one in kept)
        if not duplicate:
            kept.append(record)
    return kept


def _count_conflicts(records: List[MemoryRecord]) -> int:
    """Count similar-but-conflicting records (same fingerprint, diff content)."""
    by_fingerprint: dict = {}
    conflicts = 0
    for record in records:
        fp = record.fingerprint
        if fp in by_fingerprint:
            if by_fingerprint[fp].content != record.content:
                conflicts += 1
        else:
            by_fingerprint[fp] = record
    return conflicts


def migrate_legacy_to_unified(
    legacy_path: str,
    unified_path: Optional[str] = None,
) -> MigrationReport:
    """
    Migrate a legacy store into the unified store. Idempotent + non-destructive.

    Args:
        legacy_path: Path to the (possibly legacy) memory file.
        unified_path: Destination unified store. Defaults to the active
            ``persistence.default_memory_file()``.

    Returns:
        MigrationReport describing every pipeline stage.
    """
    report = MigrationReport(source=legacy_path,
                             target=unified_path or persistence.default_memory_file())

    # DETECT
    if not os.path.exists(legacy_path):
        report.errors.append(f"source not found: {legacy_path}")
        return report
    raw = persistence.load_json_safe(legacy_path, {})
    fmt = _detect_format(raw)
    if fmt == "unknown":
        report.errors.append("source format not recognized (not unified, not legacy)")
        return report
    report.detected = True

    if fmt == "unified":
        report.already_unified = True
        report.records_detected = len(raw.get("records", []))
        # Idempotent: verify the existing unified store loads, no rewrite.
        report.records_migrated = report.records_detected
        existing = persistence.load_unified_memory_records(report.target)
        report.verified = (len(existing) == report.records_migrated
                           if os.path.exists(report.target) else True)
        report.activated = True
        return report

    # BACKUP — never destroy the original, and back up an existing target too.
    try:
        report.source_backup = _backup(legacy_path)
        report.backup_written = True
    except OSError as exc:
        report.errors.append(f"backup failed: {exc}")
        return report
    if os.path.exists(report.target):
        try:
            report.target_backup = _backup(report.target)
        except OSError as exc:
            report.errors.append(f"target backup failed: {exc}")

    # NORMALIZE + VALIDATE
    migrated = persistence._migrate_legacy_to_unified(raw)  # reuse existing logic
    report.records_detected = len(migrated)
    valid: List[MemoryRecord] = []
    for record in migrated:
        issues = validate_memory_record(record)
        if issues:
            report.records_invalid += 1
            continue
        record.status = MemoryStatus.ACTIVE
        valid.append(record)

    # DEDUP
    deduped = _dedup(valid)
    report.records_duplicates = len(valid) - len(deduped)

    # CONFLICT CHECK (report-only; never destroys)
    report.records_conflicts = _count_conflicts(deduped)

    # MIGRATE (merge into any existing unified target)
    target_records: List[MemoryRecord] = []
    if os.path.exists(report.target):
        target_records = persistence.load_unified_memory_records(report.target)
    merged = _dedup(target_records + deduped)
    merged_incoming = len(merged) - len(target_records)
    try:
        persistence.save_unified_memory_records(merged, report.target)
    except OSError as exc:
        report.errors.append(f"write failed: {exc}")
        return report
    report.records_migrated = merged_incoming

    # VERIFY
    reloaded = persistence.load_unified_memory_records(report.target)
    report.verified = len(reloaded) == len(merged)

    # ACTIVATE
    report.activated = report.verified
    return report


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="MYRAA Memory 2.0 legacy migration")
    parser.add_argument("legacy_path", help="path to the legacy memory file")
    parser.add_argument("unified_path", nargs="?", default=None,
                        help="destination unified store (default: active store)")
    args = parser.parse_args(argv)

    report = migrate_legacy_to_unified(args.legacy_path, args.unified_path)
    print("\nMYRAA Memory 2.0 Migration Report")
    print("=" * 60)
    for key, value in report.as_dict().items():
        print(f"{key:<20} {value}")
    return 0 if report.activated else 1


if __name__ == "__main__":
    raise SystemExit(_main())