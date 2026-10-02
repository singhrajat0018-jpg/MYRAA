# MYRAA MEMORY ARCHITECTURE

Date: 2026-09-19.

## Authority

Python `UnifiedMemoryManager` (`myraa_brain_memory.json`) is
brain-authoritative. Node `memories.json` is UI-facing and DIVERGED (no
sync, different schema) — unification is a designed-not-executed migration
(see below), not a second authority created here.

## Working memory (bounded, temporary)

`brain/working_memory` snapshot (live) + observer WORKING records. Ephemeral
by design; consolidation consumes sources into EPISODIC.

## Long-term memory (semantic usefulness, typed)

Types: WORKING/EPISODIC/SEMANTIC (+EXPERIENCE/PROCEDURAL/PREFERENCE
declared; only the first three are consolidation targets — code-verified).
Every record: provenance (8-value enum), timestamps, importance,
confidence, sensitivity, scope, fingerprint dedup, lifecycle transitions.

## Consolidation (controlled, RUNNING)

9-stage governed `remember()` → 60s RuntimeManager daemon
(`runtime_manager.py:124-204`) promotes WORKING→EPISODIC→SEMANTIC with
contradiction recording (-0.15) and reinforcement (+0.05, cap 1.0).
Idempotent via `consolidated_at`. External content enters only through the
same secret-filtered governance — and promotion policy for untrusted
content remains the open hardening item (flagged, not silently closed).

## Conflict handling

Contradictions are recorded with sources and confidence penalty, never
silently overwritten (`_record_contradiction:914`).

## Migration design (Node/Python unification — NOT executed)

1. Freeze Node schema → adapter translating to MemoryRecord.
2. One-way Node→Python import with provenance USER_IMPLICIT + dedup.
3. Cut reads to Python-backed endpoint; keep Node file as cache.
4. Verify counts/fingerprints; then remove Node authority.
Each step needs its own tests. No code for this exists yet by design.
