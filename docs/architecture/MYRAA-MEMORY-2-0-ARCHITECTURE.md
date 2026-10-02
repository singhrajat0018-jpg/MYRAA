# MYRAA Memory 2.0 Architecture

Authoritative, implementation-only description of the MYRAA Memory 2.0 system as
built. Every section reflects code that exists in the repository today
(verified 2026-08). Nothing here describes intended-but-unbuilt behavior.

---

## 1. Overview

Memory 2.0 unifies MYRAA's scattered memory stores (working / episodic /
semantic) into ONE canonical model (`MemoryRecord`) owned by ONE manager
(`UnifiedMemoryManager`). The legacy `MemoryManager`/`Brain` memory surface is
preserved as a compatibility layer over the unified store, so existing brain
code keeps working without a rewrite.

Files (all under `desktop_agent/brain/memory/`):

| File | Role |
|---|---|
| `unified_model.py` | `MemoryRecord`, enums, validators, fingerprints, equivalence/similarity |
| `unified_manager.py` | Single authority: write governance, retrieval, consolidation, lifecycle, decay, views |
| `persistence.py` | Atomic JSON persistence, corruption recovery, version-aware migration, F1 secret scrubbing |
| `memory_commands.py` | Natural-language memory commands (M10) wired into `BrainEngine.process` |
| `migrate_legacy.py` | DETECT→BACKUP→NORMALIZE→VALIDATE→MIGRATE→DEDUP→CONFLICT→VERIFY→ACTIVATE (M16) |
| `repair.py` | Safe/idempotent/non-destructive/reversible store repair + quarantine (M17) |
| `benchmark_memory.py` | Reproducible performance benchmark (M13) |
| `manager.py`, `working_memory.py`, `episodic_memory.py`, `semantic_memory.py` | Legacy store (kept for compat) |

## 2. Canonical data model (`unified_model.py`)

`MemoryRecord` is a dataclass with:

- **Identity**: `id` (UUID), `fingerprint` (SHA-256 of normalized
  `type:scope:content[:project][:task]`), `version`.
- **Type** (`MemoryType`): `WORKING`, `EPISODIC`, `SEMANTIC`, `PREFERENCE`,
  `PROCEDURAL`, `EXPERIENCE`, `CONVERSATION`.
- **Scope** (`MemoryScope`): `GLOBAL`, `USER`, `PROJECT`, `TASK`,
  `CONVERSATION`, `SESSION`.
- **Status** (`MemoryStatus`): `ACTIVE`, `ARCHIVED`, `RETRACTED`, `EXPIRED`,
  `CONFLICTED`, `SUPERSEDED`, `DELETED`.
- **Temporal**: `created_at`, `updated_at`, `last_accessed_at`, `event_time`.
- **Quality**: `importance`, `confidence`, `relevance`, `salience`, `recency`
  (all 0..1), `access_count`.
- **Organization**: `tags`, `entities`, `relations`.
- **Technical**: `embedding_reference`, `sensitivity` (`Sensitivity`),
  `retention_policy` (`RetentionPolicy`), `metadata`, `provenance`
  (`Provenance`), `supersedes`/`superseded_by` (version-chain links).

Helpers: `create_*_memory(...)` factories, `validate_memory_record()` (returns
error strings), `is_valid_memory()`, `memories_are_equivalent()` (exact),
`calculate_memory_similarity()` (0..1), `merge_memory_tags/entities/relations`.

## 3. Single source of truth

`UnifiedMemoryManager` is the composition root of every memory operation. It is
shared across the brain and the runtime container (M9):

- `BrainEngine.__init__` keeps `self.memory = memory_manager if memory_manager
  else UnifiedMemoryManager()` and `self.memory_2_0` defaults to `self.memory`
  — i.e. `brain.memory is brain.memory_2_0`.
- `ApplicationContainer` passes `memory_manager=self.memory_2_0`.
- `process_event()` writes one canonical `WORKING` record per event.

There is no second memory authority.

## 4. Write governance pipeline

`remember(record)` enforces, in order:

1. Fingerprint (updated before storage).
2. **Sensitivity gate** — `is_sensitive_text()` on content/summary/tags/
   entities/metadata (recursive, catches secret-like key names); secrets are
   rejected and never stored.
3. Deduplication — same ID refresh via `_update_existing_memory`; equivalent
   content via `memories_are_equivalent`.
4. Conflict resolution — contradictions degrade confidence and increment
   `metadata["contradictions"]`; repeated observation reinforces confidence.
5. Retention policy — `retention_decision` may `reject`, `modify`, or accept.
6. Persist (see M14 — deferred/coalesced).

`remember()` also scores importance (explicit value is a floor, never lowered).

## 5. Retrieval contract

- `recall(id)` returns a record only when it is `ACTIVE` or `SUPERSEDED`;
  `ARCHIVED`/`RETRACTED`/`EXPIRED`/`CONFLICTED`/`DELETED` return `None`.
- `recall_by_content()` / `get_all_active()` / `_advanced_retrieval()` return
  `ACTIVE` records only.
- `get_by_status()` / `get_all()` / `lifecycle_stats()` expose non-active
  records for inspection (tests and repair use these).

## 6. Memory commands (M10)

`memory_commands.py` exposes a command layer over the store:

- `MemoryCommand` (op + args), `MemoryCommandResult` (handled? message,
  affected ids, metadata).
- `MemoryCommandParser` parses English + Hinglish phrasing.
- `MemoryCommandEngine.handle(text, context)` → full pipeline:
  sensitivity rejection → parse → clarify on ambiguity → apply.

Operations: `REMEMBER`, `RECALL`, `UPDATE`, `FORGET`, `LIST`, `CLEAR_SCOPE`
plus M11 lifecycle ops `ARCHIVE`, `BURY`, `RETRACT`, `EXPIRE`, `RESTORE`.

Wired into `BrainEngine.process()`: after `_resolve_input`,
`self.memory_command_engine.handle(text, context)` is consulted; when it
returns a non-`None` result the brain returns early with
`metadata["route"] = "MEMORY_COMMAND"`. Command handlers use a strict lexical
match gate (`_score_query(...) > 0.0`) so destructive ops never act on weak
fuzzy matches.

## 7. Lifecycle management (M11)

`UnifiedMemoryManager` lifecycle section:

- `_LIFECYCLE_TRANSITIONS` — validity map (e.g. `ACTIVE→ARCHIVED` ok,
  `SUPERSEDED→DELETED` rejected).
- `transition_status(id, target, reason)` — idempotent, audit trail appended
  to `metadata["lifecycle"]["transitions"]`, immediate persist.
- `archive`, `bury` (ARCHIVE + `buried=True`), `retract`, `expire`,
  `mark_conflict`, `restore` (rejected from SUPERSEDED/DELETED).
- `get_by_status(status)`, `lifecycle_stats()`.
- `run_decay()` — `EPHEMERAL` or `importance < 0.3` → `EXPIRED`, else
  `ARCHIVED`; `USER_DEFINED`/`PERMANENT` never decay. `consolidate()`
  appends `stats["decay"] = self.run_decay()`.

## 8. Consolidation

`consolidate()` promotes working → episodic → semantic/procedural, marks
consumed source records `ARCHIVED` with `metadata["consolidated_at"]`, and now
runs decay. Exact detail preserved from M7.

## 9. Persistence (`persistence.py`)

- Atomic writes: temp file + `os.replace`; previous good copy kept at
  `<file>.bak`.
- Corruption recovery: corrupt store quarantined to
  `<file>.corrupt.<ts>` and last-good backup restored; else empty.
- Version-aware: `load_unified_memory_records` handles version 2 (unified),
  version 1 (legacy, via `_migrate_legacy_to_unified`), unknown.
- F1 scrubbing: `_SENSITIVE_PATTERNS` + `SENSITIVE_KEY_HINTS`; checked on
  load, on migration, and in `backup()` (which writes a SANITIZED copy).
- **Honest limitation**: the store is plaintext JSON — there is NO encryption
  at rest. The security model is F1 scrubbing (secrets never enter the store),
  not secrecy of the file.

## 10. Security model (M12)

- Secret-shaped values are rejected at write and scrubbed at load/backup.
- Patterns cover API keys (incl. spaced `api key` + `is` connector), passwords,
  secrets, access/auth/bearer tokens, private keys, provider-prefixed keys
  (`sk-`, `rk-`, `ghp_`, `github_pat_`, `tvly-`, `hf_`, `n8n_`, `rk_live_`),
  Google `AIza`, AWS `AKIA/ASIA`, Slack `xox...`, JWTs, Authorization headers,
  cookies, `password123`-shapes, `user:pass` shapes, card numbers (separated
  and compact with a `(?<![\d.])` lookbehind so float `0.9000000000000001`
  is not flagged), OTP/pin.
- `SENSITIVE_KEY_HINTS` includes `cookie`, `authorization`, `auth_header`,
  `bearer`, `credential`, `session_key`, `secret_key`.
- Both the manager and the dict-level loader use the same recursive
  `is_sensitive_text(metadata)` check, closing the key-name gap.
- API keys remain server-side only (Gemini key in `secrets.json`/env, per
  AGENTS.md §13).

## 11. Migration (M16)

`migrate_legacy.py` implements:

```
DETECT → BACKUP → NORMALIZE → VALIDATE → MIGRATE → DEDUP
       → CONFLICT CHECK → VERIFY → ACTIVATE
```

- Backs up the source (`<file>.pre-migration.<ts>.bak`) and any existing
  target before touching them — originals are never destroyed.
- Idempotent: an already-unified source reports `already_unified=True` and is
  only verified.
- Reuses `persistence._migrate_legacy_to_unified` (which M16 repaired: the
  missing enum imports and the invalid `timestamp=`/`category=` kwargs were
  fixed).
- DEDUP drops exact/equivalent duplicates; CONFLICT CHECK counts (never
  destroys) same-fingerprint/different-content records.
- VERIFY round-trips the store; ACTIVATE reports the active target.

Run: `python -m desktop_agent.brain.memory.migrate_legacy <legacy> [<target>]`

## 12. Repair (M17)

`repair.py` — `repair_store()`:

- Parses the raw file (not the scrubbing loader) so sensitive records are
  quarantined and REPORTED, not silently dropped.
- Quarantines invalid and sensitive records to
  `<path>.quarantine.<ts>.json` (never deletes).
- Rebuilds/reindexes fingerprints (only counted when they actually change).
- Dedups exact/equivalent duplicates.
- Rewrites the store only when something changed (idempotent).
- Reversible via `list_quarantine()` + `restore_quarantine()` (skips IDs
  already present).

Run: `python -m desktop_agent.brain.memory.repair [path] [--restore-quarantine QFILE]`

## 13. Performance (M13/M14)

`benchmark_memory.py` measures every hot path with reproducible numbers.
M14 added **deferred/coalesced persistence**: `_persist()` marks the store
dirty and schedules ONE background write per 50ms window; explicit operations
(forget, lifecycle transitions, decay, clear) and `flush()` remain immediate
durability points. `__del__` best-effort flushes.

Measured (repo root, 2026-08, `--iterations 5`):

| Operation | Before (M13) | After (M14) |
|---|---|---|
| remember (single) | ~3.05 ms | ~0.116 ms (~26x) |
| remember (bulk 300) | 435 ops/s | 7010 ops/s (~16x) |
| recall by id | ~4.1 µs | ~4.1 µs |
| recall_by_content (top-5) | ~80 µs | ~80 µs |
| get_all_active | ~12.6 µs | ~12.6 µs |
| consolidate pass (300 rec) | ~72 µs | ~124 µs |
| run_decay sweep | ~15 µs | ~15 µs |
| archive+restore round-trip | ~6.2 ms | ~6.2 ms |
| command REMEMBER | ~5.1 ms | ~1.1 ms |
| command RECALL | ~117 µs | ~117 µs |

Durability tradeoff: a crash within the 50 ms coalescing window can lose at
most that window of writes; `flush()` and lifecycle ops are synchronous.

Reproduce: `python -m desktop_agent.brain.memory.benchmark_memory`.

## 14. Compatibility layer (M9)

`UnifiedMemoryManager` still exposes the legacy surface used by the rest of
the brain: `working` / `episodic` / `semantic` views, `context()`, `clear()`,
`remember_event()`, `remember_fact()`, `remember_reflection()`, `learn()`,
`retrieve()`. The views (`_WorkingView`, `_EpisodicView`, `_SemanticView`)
project unified records into the old shapes and route writes back through the
authoritative path.

## 15. Tests

All under `desktop_agent/brain/memory/` (pytest, plus subtest counters):

| File | Scope |
|---|---|
| `test_unified_model.py` | model, enums, validators, fingerprints |
| `test_unified_manager.py` | write governance, persistence, reload |
| `test_consolidation.py` | consolidation |
| `test_m5_dedup_conflict_versioning.py` | dedup, conflicts, version chains |
| `test_m9_authoritative.py` | single authority + compat layer |
| `test_m10_commands.py` | command parser/engine + BrainEngine integration (52 tests) |
| `test_m11_lifecycle.py` | lifecycle transitions, decay, lifecycle commands (31 tests) |
| `test_m12_security.py` | F1 scrubbing, store rejection, sanitized backup (20 tests + 52 subtests) |
| `test_m16_migration.py` | migration pipeline, safety contract (6 tests) |
| `test_m17_repair.py` | repair + quarantine + restore (8 tests) |

Full regression (executed, repo root): `brain/memory` + `brain/super_brain`
198 passed; `brain` 239 passed; root `tests/` 293 passed. (`test_vision.py`
collection error and `test_mouse_bridge.py` async-plugin failure are
pre-existing and unrelated to memory.)

## 16. Known limitations

- Plaintext JSON store (no encryption at rest); security = scrubbing, not secrecy.
- Deferred persist has a ≤50 ms durability window on ordinary `remember()`.
- `recall()` intentionally hides non-active records; use `get_by_status()`.
- LLM/AI routing, research, and telemetry are outside the memory scope and
  remain as documented in AGENTS.md §7/§9/§10.