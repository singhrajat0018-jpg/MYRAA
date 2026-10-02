"""
MYRAA Unified Memory Manager
Single entry point for every memory operation using the unified memory model.
"""

from __future__ import annotations

import logging
import time
import math
import re
import threading
from typing import List, Optional, Set, Dict, Any, Tuple
from threading import RLock

from desktop_agent.brain.memory.unified_model import (
    MemoryRecord, MemoryType, MemoryScope, MemoryStatus, Sensitivity,
    RetentionPolicy, Provenance, validate_memory_record, is_valid_memory,
    memories_are_equivalent, calculate_memory_similarity
)
from . import persistence

log = logging.getLogger(__name__)


class UnifiedMemoryManager:
    """
    Unified memory manager that provides a single interface for all memory operations.

    This manager works with the unified memory model and provides methods for:
    - Storing and retrieving memories with write governance
    - Memory consolidation (working -> episodic -> semantic/procedural)
    - Memory importance scoring and confidence management
    - Memory deduplication and conflict resolution
    - Memory scoping and isolation
    - Persistence with atomic writes and corruption recovery
    """

    def __init__(self, store_path: Optional[str] = None):
        """
        Initialize the unified memory manager.

        Args:
            store_path: Path to the memory store file. If None, uses default location.
        """
        self._records: Dict[str, MemoryRecord] = {}  # ID -> MemoryRecord
        self._lock = RLock()
        self._store_path = store_path or persistence.default_memory_file()

        # M14: deferred-persist bookkeeping. Writes are coalesced: rapid remember()
        # calls share one disk write per flush window instead of one write each.
        self._dirty = False
        self._flush_lock = threading.Lock()
        self._flush_thread_alive = False
        self._flush_delay = 0.05  # seconds

        # Load existing memories
        self._load_memories()

    # ------------------------------------------
    # Core Memory Operations with Write Governance
    # ------------------------------------------

    def remember(self, record: MemoryRecord) -> bool:
        """
        Store a memory record after applying the full write governance pipeline.

        Write Governance Pipeline:
        Candidate
        â†’ classify (validation)
        â†’ importance (scoring)
        â†’ confidence (scoring)
        â†’ sensitivity (checking)
        â†’ usefulness (assessment)
        â†’ deduplication (checking)
        â†’ conflict (detection/resolution)
        â†’ retention (decision)
        â†’ persist

        Args:
            record: MemoryRecord to store

        Returns:
            True if stored successfully, False if rejected
        """
        # START: Write Governance Pipeline

        # 1. CLASSIFY: Validate the memory record
        if not is_valid_memory(record):
            log.warning("[Memory] Invalid memory record rejected during classification")
            return False

        # 2. IMPORTANCE: Score importance based on multiple factors.
        #    Explicit caller-provided importance is authoritative â€” the scoring
        #    heuristic may raise it but must never clobber it lower (M5).
        explicit_importance = record.importance
        record.importance = self._score_importance(record)
        if record.importance < explicit_importance:
            record.importance = explicit_importance

        # 3. CONFIDENCE: Score confidence based on source and evidence.
        #    Explicit caller-provided confidence is authoritative (M5).
        explicit_confidence = record.confidence
        record.confidence = self._score_confidence(record)
        if record.confidence < explicit_confidence:
            record.confidence = explicit_confidence

        # 4. SENSITIVITY: Check for sensitive data (F1 - never store secrets)
        if self._contains_sensitive_data(record):
            log.warning("[Memory] Rejected sensitive memory during sensitivity check (never stored)")
            return False

        # 5. USEFULNESS: Assess usefulness/predicted future utility
        if not self._assess_usefulness(record):
            log.info("[Memory] Memory rejected during usefulness assessment")
            return False

        # 5b. SAME-ID UPDATE: an explicit update to an existing ACTIVE record
        #     always refreshes it in place (content wins, version increments).
        with self._lock:
            existing_by_id = self._records.get(record.id)
            if existing_by_id is not None and existing_by_id.status == MemoryStatus.ACTIVE:
                return self._update_existing_memory(existing_by_id, record, same_id=True)

        # 6. DEDUPLICATION: Check for existing similar memories
        existing_id = self._find_existing_similar_memory(record)
        if existing_id:
            existing_record = self._records[existing_id]
            log.debug(f"[Memory] Found similar existing memory: {existing_id[:8]}")
            # GLOBAL wins over a narrower scope: the incoming GLOBAL memory
            # replaces the narrower one entirely (scope authority, M5).
            if record.scope == MemoryScope.GLOBAL and existing_record.scope != MemoryScope.GLOBAL:
                with self._lock:
                    del self._records[existing_id]
                # fall through to persist the GLOBAL record
            elif existing_id == record.id:
                return self._update_existing_memory(existing_record, record, same_id=True)
            elif self._content_essentially_identical(existing_record, record):
                # Pure duplicate (same fact, higher quality) -> refresh in place.
                return self._update_existing_memory(existing_record, record, same_id=False)
            else:
                # Changed value of the same fact -> version-chain the old one.
                return self._supersede_and_store(existing_record, record)

        # 7. CONFLICT: Check for conflicting memories and resolve
        conflict_action, conflicting_memories = self._check_and_resolve_conflicts(record)
        if conflict_action == "reject":
            log.info("[Memory] Memory rejected due to unresolved conflicts")
            return False
        elif conflict_action == "supersede":
            # The incoming memory is a versioned update: mark every conflicting
            # existing memory SUPERSEDED and store the new one (version chain).
            for existing_id, existing_record in conflicting_memories:
                existing_record.supersede_by(record.id)
                existing_record.status = MemoryStatus.SUPERSEDED
            if len(conflicting_memories) == 1:
                record.supersedes = conflicting_memories[0][0]
                record.version = max(
                    record.version, conflicting_memories[0][1].version + 1
                )
            # Continue to store the memory
        elif conflict_action == "replace":
            # The incoming memory clearly wins: remove the conflicting ones.
            for existing_id, existing_record in conflicting_memories:
                with self._lock:
                    del self._records[existing_id]
            # Continue to store the new memory (normal persist will handle it)
        elif conflict_action == "update" or conflict_action == "merge":
            # Refresh/merge into the existing memory instead of duplicating.
            if conflicting_memories:
                existing_id, existing_record = conflicting_memories[0]
                return self._update_existing_memory(existing_record, record, same_id=False)
        elif conflict_action in ("keep_existing", "mark_conflict", "require_confirmation"):
            # Keep the existing memory intact; store the incoming one with a
            # visible conflict flag so the record trail is preserved (M5).
            record.metadata["conflict_resolution"] = conflict_action
            record.metadata["conflicts_with"] = [
                eid for eid, _ in conflicting_memories
            ]
            # Continue to store the memory

        # 8. RETENTION: Apply retention policy decision
        retention_decision = self._apply_retention_policy(record)
        if retention_decision == "reject":
            log.info("[Memory] Memory rejected by retention policy")
            return False
        elif retention_decision == "modify":
            # Apply any modifications suggested by retention policy
            record = self._apply_retention_modifications(record)

        # 9. PERSIST: Store the memory
        with self._lock:
            # Ensure fingerprint is up to date
            record.update_fingerprint()
            self._records[record.id] = record
            log.debug(f"[Memory] Stored new memory after write governance: {record.id[:8]}")
            self._persist()

        return True
        # END: Write Governance Pipeline

    def recall(self, memory_id: str) -> Optional[MemoryRecord]:
        """
        Retrieve a memory record by ID.

        Args:
            memory_id: ID of the memory to retrieve

        Returns:
            MemoryRecord if found and active, None otherwise
        """
        with self._lock:
            record = self._records.get(memory_id)
            if record is None:
                return None
            if record.status == MemoryStatus.ACTIVE:
                record.access()  # Update access statistics
                return record
            # Explicit recall by ID also exposes version history (SUPERSEDED)
            # so the full record trail stays accessible (M5 version chaining).
            if record.status == MemoryStatus.SUPERSEDED:
                return record
            return None

    def forget(self, memory_id: str) -> bool:
        """
        Forget (delete) a memory record by ID.

        Args:
            memory_id: ID of the memory to forget

        Returns:
            True if forgotten, False if not found
        """
        with self._lock:
            if memory_id in self._records:
                record = self._records[memory_id]
                record.status = MemoryStatus.DELETED
                record.updated_at = time.time()
                log.debug(f"[Memory] Forgot memory: {memory_id[:8]}")
                self._persist_immediate()
                return True
            return False

    def recall_by_content(self, content_query: str, limit: int = 10,
                          metadata_filter: Optional[Dict[str, Any]] = None,
                          entity_filter: Optional[Set[str]] = None) -> List[MemoryRecord]:
        """
        Recall memories by content similarity.

        Args:
            content_query: Text to search for
            limit: Maximum number of memories to return
            metadata_filter: Optional metadata filters to apply
            entity_filter: Optional entity filters to apply

        Returns:
            List of matching MemoryRecord objects, ranked by relevance
        """
        # Normalize the query
        normalized_query = self._normalize_query(content_query)

        # Perform advanced retrieval with content-based search
        results = self._advanced_retrieval(
            query=normalized_query,
            search_type="content",
            limit=limit,
            metadata_filter=metadata_filter,
            entity_filter=entity_filter
        )

        # Extract just the records from scored results
        return [record for record, score in results]

    def get_relevant_memories(self, query: str, limit: int = 5,
                              metadata_filter: Optional[Dict[str, Any]] = None,
                              entity_filter: Optional[Set[str]] = None,
                              min_relevance: float = 0.2) -> List[Dict[str, Any]]:
        """
        Full Integration: implicit context-retrieval contract used by
        ContextManager and the cognitive pipeline.

        Searches the unified store (ACTIVE records only) and returns a
        context-friendly list of dicts ranked by relevance. This makes Memory
        2.0 the authority for IMPLICIT retrieval, not just explicit commands.

        A relevance floor (default 0.2) filters out the fuzzy base score so
        unrelated memories never leak into context (bounded, targeted context).

        Args:
            query: Free-text query built from the current request/context.
            limit: Maximum number of memories to return.
            metadata_filter: Optional metadata filters to apply.
            entity_filter: Optional entity filters to apply.
            min_relevance: Minimum relevance score to include (0..1).

        Returns:
            List of {"memory", "relevance", "id", "type", "scope", "created_at"}
            dicts, ranked best-first (empty when nothing relevant).
        """
        normalized = self._normalize_query(query)
        print(f"[DEBUG] get_relevant_memories: query='{query}', normalized='{normalized}'")
        scored = self._advanced_retrieval(
            query=normalized,
            search_type="content",
            limit=limit,
            metadata_filter=metadata_filter,
            entity_filter=entity_filter,
        )
        print(f"[DEBUG] get_relevant_memories: scored={scored}")
        result = [
            {
                "memory": record.content,
                "relevance": round(float(score), 4),
                "id": record.id,
                "type": getattr(record.type, "value", str(record.type)),
                "scope": getattr(record.scope, "value", str(record.scope)),
                "created_at": record.created_at,
            }
            for record, score in scored
            if score >= min_relevance
        ]
        print(f"[DEBUG] get_relevant_memories: result={result}")
        return result

    def recall_by_scope(self, scope: MemoryScope, project_id: Optional[str] = None,
                      task_id: Optional[str] = None, conversation_id: Optional[str] = None,
                      limit: int = 10, metadata_filter: Optional[Dict[str, Any]] = None,
                      entity_filter: Optional[Set[str]] = None) -> List[MemoryRecord]:
        """
        Recall memories by scope and optional identifiers.

        Args:
            scope: Memory scope to filter by
            project_id: Optional project ID for PROJECT scope
            task_id: Optional task ID for TASK scope
            conversation_id: Optional conversation ID for CONVERSATION scope
            limit: Maximum number of memories to return
            metadata_filter: Optional metadata filters to apply
            entity_filter: Optional entity filters to apply

        Returns:
            List of matching MemoryRecord objects, ranked by relevance
        """
        # Normalize empty identifiers
        norm_project_id = project_id if project_id and project_id.strip() else None
        norm_task_id = task_id if task_id and task_id.strip() else None
        norm_conversation_id = conversation_id if conversation_id and conversation_id.strip() else None

        # Perform advanced retrieval with scope-based search
        results = self._advanced_retrieval(
            query="",  # Empty query for scope-only search
            search_type="scope",
            scope=scope,
            project_id=norm_project_id,
            task_id=norm_task_id,
            conversation_id=norm_conversation_id,
            limit=limit,
            metadata_filter=metadata_filter,
            entity_filter=entity_filter
        )

        # Extract just the records from scored results
        return [record for record, score in results]

    def recall_by_type(self, memory_type: MemoryType, limit: int = 10,
                         metadata_filter: Optional[Dict[str, Any]] = None,
                         entity_filter: Optional[Set[str]] = None) -> List[MemoryRecord]:
        """
        Recall memories by type.

        Args:
            memory_type: Type of memory to recall
            limit: Maximum number of memories to return
            metadata_filter: Optional metadata filters to apply
            entity_filter: Optional entity filters to apply

        Returns:
            List of matching MemoryRecord objects, ranked by relevance
        """
        # Perform advanced retrieval with type-based search
        results = self._advanced_retrieval(
            query="",  # Empty query for type-only search
            search_type="type",
            memory_type=memory_type,
            limit=limit,
            metadata_filter=metadata_filter,
            entity_filter=entity_filter
        )

        # Extract just the records from scored results
        return [record for record, score in results]

    def get_all_active(self) -> List[MemoryRecord]:
        """
        Get all active memory records.

        Returns:
            List of all active MemoryRecord objects
        """
        with self._lock:
            return [record for record in self._records.values()
                   if record.status == MemoryStatus.ACTIVE]

    def get_count(self) -> int:
        """
        Get the total number of memory records.

        Returns:
            Total number of memory records (including deleted/archived/etc.)
        """
        with self._lock:
            return len(self._records)

    def get_active_count(self) -> int:
        """
        Get the number of active memory records.

        Returns:
            Number of active memory records
        """
        with self._lock:
            return sum(1 for record in self._records.values()
                      if record.status == MemoryStatus.ACTIVE)

    # ------------------------------------------
    # Memory Lifecycle (M11)
    #
    # Authoritative status-transition engine. Every status change flows through
    # transition_status() which enforces the validity map below, so a memory can
    # never jump to an illegal state:
    #
    #   ACTIVE      -> SUPERSEDED, CONFLICTED, ARCHIVED, RETRACTED,
    #                  EXPIRED, DELETED
    #   SUPERSEDED  -> ARCHIVED, DELETED                    (history is permanent;
    #                  cannot revive a superseded version)
    #   CONFLICTED  -> ACTIVE (restore), DELETED
    #   ARCHIVED    -> ACTIVE (restore), DELETED, EXPIRED
    #   RETRACTED   -> ACTIVE (restore), DELETED
    #   EXPIRED     -> ACTIVE (restore/revive), ARCHIVED, DELETED
    #   DELETED     -> (terminal)
    #
    # All lifecycle commands are idempotent: re-applying the same transition is
    # a safe no-op. Explicit user commands (RETRACT/ARCHIVE/EXPIRE/RESTORE/BURY)
    # go through these methods via the M10 command engine.
    # ------------------------------------------

    _LIFECYCLE_TRANSITIONS = {
        MemoryStatus.ACTIVE: {
            MemoryStatus.SUPERSEDED, MemoryStatus.CONFLICTED, MemoryStatus.ARCHIVED,
            MemoryStatus.RETRACTED, MemoryStatus.EXPIRED, MemoryStatus.DELETED,
        },
        MemoryStatus.SUPERSEDED: {MemoryStatus.ARCHIVED, MemoryStatus.DELETED},
        MemoryStatus.CONFLICTED: {MemoryStatus.ACTIVE, MemoryStatus.DELETED},
        MemoryStatus.ARCHIVED: {MemoryStatus.ACTIVE, MemoryStatus.DELETED, MemoryStatus.EXPIRED},
        MemoryStatus.RETRACTED: {MemoryStatus.ACTIVE, MemoryStatus.DELETED},
        MemoryStatus.EXPIRED: {MemoryStatus.ACTIVE, MemoryStatus.ARCHIVED, MemoryStatus.DELETED},
        MemoryStatus.DELETED: set(),
    }

    def transition_status(self, memory_id: str, target: MemoryStatus,
                          reason: str = "", **metadata: Any) -> bool:
        """
        Transition a memory record to a new lifecycle status.

        Enforces the M11 validity map, records reason/timestamp metadata, and is
        idempotent (transitioning to the current status is a safe no-op).

        Args:
            memory_id: ID of the memory to transition
            target: Target MemoryStatus
            reason: Why the transition happened (audit trail)
            metadata: Extra metadata to merge into record.metadata

        Returns:
            True if the transition applied (or was an idempotent no-op),
            False if the record does not exist or the transition is invalid
        """
        with self._lock:
            record = self._records.get(memory_id)
            if record is None:
                return False

            current = record.status
            if current == target:
                # Idempotent no-op: safe and observable.
                record.metadata.setdefault("lifecycle", {})
                record.metadata["lifecycle"].setdefault("noop_transitions", []).append({
                    "status": target.value,
                    "at": time.time(),
                    "reason": reason,
                })
                return True

            allowed = self._LIFECYCLE_TRANSITIONS.get(current, set())
            if target not in allowed:
                log.warning(
                    f"[Memory][Lifecycle] Invalid transition "
                    f"{current.value} -> {target.value} for {memory_id[:8]}")
                return False

            record.status = target
            record.updated_at = time.time()
            lifecycle_meta = record.metadata.setdefault("lifecycle", {})
            transitions = lifecycle_meta.setdefault("transitions", [])
            transitions.append({
                "from": current.value,
                "to": target.value,
                "at": time.time(),
                "reason": reason,
            })
            record.metadata.update(metadata)
            if reason:
                record.metadata["last_lifecycle_reason"] = reason
            log.debug(f"[Memory][Lifecycle] {memory_id[:8]} {current.value} -> {target.value}")
        self._persist_immediate()
        return True

    def archive(self, memory_id: str, reason: str = "archived") -> bool:
        """Move an ACTIVE memory into long-term ARCHIVED storage. Idempotent."""
        return self.transition_status(
            memory_id, MemoryStatus.ARCHIVED, reason=reason, archived_at=time.time())

    def bury(self, memory_id: str, reason: str = "buried") -> bool:
        """Deep-archive a memory (alias of ARCHIVE with BURY provenance)."""
        return self.transition_status(
            memory_id, MemoryStatus.ARCHIVED, reason=reason,
            buried_at=time.time(), buried=True)

    def retract(self, memory_id: str, reason: str = "retracted") -> bool:
        """Explicitly withdraw an ACTIVE memory. Idempotent."""
        return self.transition_status(
            memory_id, MemoryStatus.RETRACTED, reason=reason, retracted_at=time.time())

    def expire(self, memory_id: str, reason: str = "expired") -> bool:
        """Mark a memory EXPIRED (past relevance period). Idempotent."""
        return self.transition_status(
            memory_id, MemoryStatus.EXPIRED, reason=reason, expired_at=time.time())

    def mark_conflict(self, memory_id: str, conflicts_with=None,
                      reason: str = "conflict") -> bool:
        """Mark an ACTIVE memory CONFLICTED (kept for the record trail)."""
        conflicts_with = conflicts_with or []
        return self.transition_status(
            memory_id, MemoryStatus.CONFLICTED, reason=reason,
            conflicts_with=list(conflicts_with), conflicted_at=time.time())

    def restore(self, memory_id: str, reason: str = "restored") -> bool:
        """
        Revive a memory back to ACTIVE.

        Allowed from CONFLICTED / ARCHIVED / RETRACTED / EXPIRED. Rejected for
        SUPERSEDED (version-chain permanence) and DELETED (terminal).
        """
        with self._lock:
            record = self._records.get(memory_id)
            if record is None:
                return False
            if record.status not in (MemoryStatus.CONFLICTED, MemoryStatus.ARCHIVED,
                                     MemoryStatus.RETRACTED, MemoryStatus.EXPIRED):
                if record.status == MemoryStatus.ACTIVE:
                    return True  # idempotent no-op
                return False
        ok = self.transition_status(memory_id, MemoryStatus.ACTIVE,
                                    reason=reason, restored_at=time.time())
        if ok:
            with self._lock:
                self._records[memory_id].metadata.pop("restored", None)
        return ok

    def get_by_status(self, status: MemoryStatus) -> List[MemoryRecord]:
        """Return all records currently in the given lifecycle status."""
        with self._lock:
            return [r for r in self._records.values() if r.status == status]

    def lifecycle_stats(self) -> Dict[str, Any]:
        """Snapshot of current lifecycle distribution (observability)."""
        with self._lock:
            counts: Dict[str, int] = {}
            for record in self._records.values():
                key = record.status.value
                counts[key] = counts.get(key, 0) + 1
            return {
                "total": len(self._records),
                "active": counts.get(MemoryStatus.ACTIVE.value, 0),
                "by_status": counts,
            }

    def run_decay(self, now: Optional[float] = None) -> Dict[str, Any]:
        """
        Temporal decay sweep (M11).

        Applies retention policy to ACTIVE memories:
          - EPHEMERAL past retention         -> EXPIRED
          - expired + low importance (<0.3)  -> EXPIRED
          - expired + normal importance      -> ARCHIVED (history preserved)
          - USER_DEFINED / PERMANENT         -> never decayed

        Every decay transition is recorded in lifecycle metadata. Idempotent and
        safe to run repeatedly (already-decayed records are skipped).

        Returns:
            Stats dict: {"checked", "expired", "archived", "transitioned"}
        """
        now = now if now is not None else time.time()
        stats = {"checked": 0, "expired": 0, "archived": 0, "transitioned": 0}

        with self._lock:
            records = list(self._records.values())

        for record in records:
            if record.status != MemoryStatus.ACTIVE:
                continue
            if record.retention_policy in (RetentionPolicy.USER_DEFINED,
                                           RetentionPolicy.PERMANENT):
                continue
            if record.is_expired():
                stats["checked"] += 1
                if record.retention_policy == RetentionPolicy.EPHEMERAL or record.importance < 0.3:
                    if self.transition_status(record.id, MemoryStatus.EXPIRED,
                                              reason="temporal_decay"):
                        stats["expired"] += 1
                        stats["transitioned"] += 1
                else:
                    if self.transition_status(record.id, MemoryStatus.ARCHIVED,
                                              reason="temporal_decay"):
                        stats["archived"] += 1
                        stats["transitioned"] += 1

        if stats["transitioned"]:
            self._persist_immediate()
        return stats

    def get_all(self, status: Optional[MemoryStatus] = None) -> List[MemoryRecord]:
        """Return all records, optionally filtered by lifecycle status."""
        with self._lock:
            if status is None:
                return list(self._records.values())
            return [r for r in self._records.values() if r.status == status]

    # ------------------------------------------
    # Memory Consolidation
    # ------------------------------------------

    # ------------------------------------------
    # Consolidation (M7)
    #
    # Authoritative pipeline:
    #   WORKING  â†’ EPISODIC
    #   CONVERSATION-scoped working â†’ EPISODIC
    #   EPISODIC â†’ SEMANTIC
    #
    # Every output goes through remember() so the M5 write-governance pipeline
    # (dedup / merge / conflict / versioning) applies uniformly. Source records
    # are marked ARCHIVED + metadata["consolidated_at"] so they are never
    # consolidated twice. This is the single consolidation authority â€” new
    # consolidation behavior must be added here, never in a parallel engine.
    # ------------------------------------------

    def consolidate(self) -> Dict[str, Any]:
        """
        Run the full authoritative consolidation pass over the store.

        Promotes WORKING â†’ EPISODIC and EPISODIC â†’ SEMANTIC records that have
        not yet been consolidated. Safe to call repeatedly (idempotent).

        Returns:
            Dict with counts: working_to_episodic, episodic_to_semantic,
            working_skipped, episodic_skipped, timestamp.
        """
        stats: Dict[str, Any] = {
            "working_to_episodic": 0,
            "episodic_to_semantic": 0,
            "working_skipped": 0,
            "episodic_skipped": 0,
            "timestamp": time.time(),
        }

        episodic_memories = self.consolidate_working_to_episodic()
        stats["working_to_episodic"] = len(episodic_memories)

        semantic_memories = self.consolidate_episodic_to_semantic()
        stats["episodic_to_semantic"] = len(semantic_memories)

        # Count skipped (already-consolidated or non-promotable) sources.
        for record in list(self._records.values()):
            if record.type == MemoryType.WORKING and self._is_consolidated(record):
                stats["working_skipped"] += 1
            if record.type == MemoryType.EPISODIC and self._is_consolidated(record):
                stats["episodic_skipped"] += 1

        # M11: run the temporal-decay sweep at the end of each consolidation
        # pass so stale memories naturally expire/archive.
        stats["decay"] = self.run_decay()

        log.info(
            "[Memory] Consolidation pass complete: %s",
            stats,
        )
        return stats

    def consolidate_working_to_episodic(self,
                                        working_memories: Optional[List[MemoryRecord]] = None) -> List[MemoryRecord]:
        """
        Consolidate WORKING (and CONVERSATION-scoped) memories into EPISODIC.

        - Pulls ACTIVE, not-yet-consolidated WORKING records when none are given.
        - Promotes each into an EPISODIC record (MEDIUM_TERM retention) through
          remember() so duplicates/conflicts are resolved by M5 governance.
        - Marks the source WORKING record ARCHIVED + consolidated so it is not
          promoted again.

        Args:
            working_memories: Optional explicit list of WORKING records.

        Returns:
            List of newly stored EPISODIC memory records.
        """
        if working_memories is None:
            working_memories = self._consolidation_candidates(MemoryType.WORKING)

        episodic_memories = []

        for wm in working_memories:
            if wm.type not in (MemoryType.WORKING, MemoryType.CONVERSATION) or \
               wm.status != MemoryStatus.ACTIVE:
                continue
            if self._is_consolidated(wm):
                continue

            episodic_record = MemoryRecord(
                type=MemoryType.EPISODIC,
                content=wm.content,
                summary=wm.summary or f"Consolidated event: {wm.content[:50]}",
                source=wm.source or "consolidation",
                importance=wm.importance,
                confidence=wm.confidence,
                retention_policy=RetentionPolicy.MEDIUM_TERM,
                scope=wm.scope,
                project_id=wm.project_id,
                task_id=wm.task_id,
                conversation_id=wm.conversation_id,
                status=MemoryStatus.ACTIVE,
                tags=wm.tags.copy(),
                entities=wm.entities.copy(),
                relations=wm.relations.copy(),
                provenance=Provenance.SYSTEM_OBSERVED,  # Consolidated by system
            )

            if self.remember(episodic_record):
                # The WORKING source is consumed regardless of whether the new
                # record was merged into an existing EPISODIC record.
                self._mark_consolidated(wm)
                if self.recall(episodic_record.id) is not None:
                    episodic_memories.append(episodic_record)

        return episodic_memories

    def consolidate_episodic_to_semantic(self,
                                         episodic_memories: Optional[List[MemoryRecord]] = None) -> List[MemoryRecord]:
        """
        Consolidate EPISODIC memories into SEMANTIC facts.

        - Pulls ACTIVE, not-yet-consolidated EPISODIC records when none are given.
        - Extracts a stable "subject: value" fact from each episode.
        - Detects contradictions against existing SEMANTIC facts (lowers the
          contradicted fact's confidence) and reinforces repeated observations
          (raises confidence, bounded at 1.0).
        - Stores each fact through remember() so M5 conflict/versioning applies.
        - Marks the source EPISODIC record ARCHIVED + consolidated.

        Args:
            episodic_memories: Optional explicit list of EPISODIC records.

        Returns:
            List of newly stored SEMANTIC memory records.
        """
        if episodic_memories is None:
            episodic_memories = self._consolidation_candidates(MemoryType.EPISODIC)

        semantic_memories = []

        for em in episodic_memories:
            if em.type != MemoryType.EPISODIC or em.status != MemoryStatus.ACTIVE:
                continue
            if self._is_consolidated(em):
                continue

            fact = self._extract_stable_fact(em)
            if fact is None:
                # Not a fact-bearing episode; still consume it so it is not
                # reconsidered every pass.
                self._mark_consolidated(em)
                continue

            subject, value = fact
            existing = self._find_existing_fact(subject, em)

            confidence = em.confidence
            if existing is not None and existing.content != f"{subject}: {value}":
                # Contradiction: penalize the existing fact and let M5 resolution
                # decide the outcome when the new fact is stored.
                self._record_contradiction(existing, em)
            elif existing is not None and existing.content == f"{subject}: {value}":
                # Reinforcement: repeated observation of the same fact.
                confidence = self._reinforce_confidence(existing, em)
            elif existing is None:
                # First observation; modest baseline boost for consistency.
                confidence = min(1.0, max(confidence, 0.6))

            semantic_record = MemoryRecord(
                type=MemoryType.SEMANTIC,
                content=f"{subject}: {value}",
                summary=value[:200],
                source=em.source or "consolidation",
                importance=max(0.6, em.importance),
                confidence=confidence,
                retention_policy=RetentionPolicy.LONG_TERM,
                scope=em.scope,
                project_id=em.project_id,
                task_id=em.task_id,
                conversation_id=em.conversation_id,
                status=MemoryStatus.ACTIVE,
                tags={subject} if subject else set(),
                entities=em.entities.copy(),
                relations=em.relations.copy(),
                provenance=Provenance.SYSTEM_OBSERVED,  # Consolidated by system
            )

            if self.remember(semantic_record):
                self._mark_consolidated(em)
                if self.recall(semantic_record.id) is not None:
                    semantic_memories.append(semantic_record)

        return semantic_memories

    # ------------------------------------------
    # Consolidation helpers
    # ------------------------------------------

    def _consolidation_candidates(self, mem_type: MemoryType) -> List[MemoryRecord]:
        """ACTIVE records of a type that have not yet been consolidated."""
        with self._lock:
            return [
                record for record in self._records.values()
                if record.type == mem_type and record.status == MemoryStatus.ACTIVE
                and not self._is_consolidated(record)
            ]

    def _is_consolidated(self, record: MemoryRecord) -> bool:
        return bool(record.metadata.get("consolidated_at"))

    def _mark_consolidated(self, record: MemoryRecord) -> None:
        """Mark a source record as consumed by consolidation (ARCHIVED + stamp)."""
        with self._lock:
            record.metadata["consolidated_at"] = time.time()
            if record.type in (MemoryType.WORKING, MemoryType.EPISODIC,
                               MemoryType.CONVERSATION):
                record.status = MemoryStatus.ARCHIVED
                record.updated_at = time.time()
        self._persist()

    def _extract_stable_fact(self, em: MemoryRecord) -> Optional[Tuple[str, str]]:
        """
        Extract a stable 'subject: value' fact from episodic content.

        Prefers an explicit 'subject: value' or 'subject=value' pattern. Falls
        back to tags/entities when content has no separator. Returns None when
        no stable fact can be derived (the episode is purely narrative).
        """
        content = em.content.strip()
        if not content:
            return None

        for sep in (":", "=", " - "):
            if sep in content:
                parts = content.split(sep, 1)
                subject = parts[0].strip().strip(".:= ")
                value = parts[1].strip().strip(".:= ")
                if len(subject) >= 3 and len(value) >= 1:
                    return subject, value

        # Fallback: use a tag as the subject with the full content as value.
        if em.tags:
            subject = sorted(em.tags)[0]
            return subject, content[:200]

        return None

    def _find_existing_fact(self, subject: str, context: MemoryRecord) -> Optional[MemoryRecord]:
        """
        Find an ACTIVE SEMANTIC fact with the same subject in the same scope and
        context (project/task/conversation). Scope isolation is preserved.
        """
        with self._lock:
            for record in self._records.values():
                if record.status != MemoryStatus.ACTIVE:
                    continue
                if record.type != MemoryType.SEMANTIC:
                    continue
                if record.scope != context.scope:
                    continue
                if record.project_id != context.project_id:
                    continue
                if record.task_id != context.task_id:
                    continue
                if record.conversation_id != context.conversation_id:
                    continue
                if subject in record.tags or subject.lower() in \
                        (t.lower() for t in record.tags):
                    return record
        return None

    def _record_contradiction(self, existing: MemoryRecord, source: MemoryRecord) -> None:
        """A newer observation contradicts an existing SEMANTIC fact."""
        with self._lock:
            existing.metadata["contradictions"] = existing.metadata.get("contradictions", 0) + 1
            existing.metadata["contradicted_at"] = time.time()
            existing.metadata.setdefault("conflict_sources", []).append(source.source)
            existing.confidence = max(0.1, existing.confidence - 0.15)
            existing.updated_at = time.time()
        self._persist()

    def _reinforce_confidence(self, existing: MemoryRecord, source: MemoryRecord) -> float:
        """Repeated observation of the same fact raises its confidence."""
        with self._lock:
            existing.metadata["observation_count"] = existing.metadata.get("observation_count", 1) + 1
            existing.metadata["last_observed_at"] = time.time()
            existing.confidence = min(1.0, existing.confidence + 0.05)
            existing.updated_at = time.time()
        self._persist()
        return existing.confidence

    def remember_working_event(self, event: Any, scope: MemoryScope = MemoryScope.SESSION,
                               conversation_id: Optional[str] = None) -> bool:
        """
        Record an observed event as a WORKING memory (the input side of the
        consolidation pipeline). Best-effort; never raises.

        Args:
            event: Object with title/message/source/severity/payload attributes
                   (observer event, desktop state, etc.).
            scope: Memory scope for the working record.
            conversation_id: Optional conversation id.

        Returns:
            True if the working memory was stored.
        """
        try:
            if isinstance(event, str):
                title = ""
                message = event
                source = "observer"
                severity = ""
                payload = {}
                extra: Dict[str, Any] = {}
            else:
                title = getattr(event, "title", "") or ""
                message = getattr(event, "message", "") or ""
                source = getattr(event, "source", "observer") or "observer"
                severity = str(getattr(event, "severity", "") or "")
                payload = getattr(event, "payload", {}) or {}
                if isinstance(payload, dict):
                    extra = payload
                else:
                    extra = {"payload": str(payload)}

            record = MemoryRecord(
                type=MemoryType.WORKING,
                content=message or title,
                summary=title or message[:80],
                source=str(source),
                importance=0.5,
                confidence=0.6,
                retention_policy=RetentionPolicy.SHORT_TERM,
                scope=scope,
                conversation_id=conversation_id,
                status=MemoryStatus.ACTIVE,
                provenance=Provenance.SYSTEM_OBSERVED,
                metadata={"severity": severity, **extra},
            )
            if not record.content.strip():
                return False
            return self.remember(record)
        except Exception:
            log.exception("[Memory] Failed to record working event")
            return False

    # ------------------------------------------
    # M9 compatibility layer â€” legacy-shaped views.
    #
    # The unified store is the AUTHORITATIVE memory. These views expose the
    # legacy MemoryManager sub-manager API (`.working` / `.episodic` /
    # `.semantic` plus `.context()`, `.clear()`, `remember_event`,
    # `remember_fact`, `remember_reflection`, `learn`) as thin adapters over
    # the unified records so the existing BrainEngine / SuperBrain /
    # ContextFusionEngine call sites keep working unchanged.
    # ------------------------------------------

    @property
    def working(self) -> "UnifiedMemoryManager._WorkingView":
        return self._get_working_view()

    @property
    def episodic(self) -> "UnifiedMemoryManager._EpisodicView":
        return self._get_episodic_view()

    @property
    def semantic(self) -> "UnifiedMemoryManager._SemanticView":
        return self._get_semantic_view()

    def _get_working_view(self) -> "_WorkingView":
        if getattr(self, "_working_view", None) is None:
            self._working_view = _WorkingView(self)
        return self._working_view

    def _get_episodic_view(self) -> "_EpisodicView":
        if getattr(self, "_episodic_view", None) is None:
            self._episodic_view = _EpisodicView(self)
        return self._episodic_view

    def _get_semantic_view(self) -> "_SemanticView":
        if getattr(self, "_semantic_view", None) is None:
            self._semantic_view = _SemanticView(self)
        return self._semantic_view

    def context(self) -> Dict[str, Any]:
        """Legacy MemoryManager.context() shape: working/episodic/semantic."""
        return {
            "working": self.working.snapshot(),
            "episodic": self.episodic.recent(limit=20),
            "semantic": self.semantic.snapshot(),
        }

    def clear(self) -> None:
        """Clear every record from the unified store (legacy compat)."""
        with self._lock:
            self._records.clear()
        self._persist_immediate()

    def remember_event(self, event: Any,
                       scope: MemoryScope = MemoryScope.SESSION) -> bool:
        """Legacy compat: record an observed event (WORKING input to M7)."""
        return self.remember_working_event(event, scope=scope)

    def remember_fact(self, key: str, value: Any = None,
                      confidence: float = 0.8,
                      source: str = "brain") -> bool:
        """Legacy compat: store a semantic fact via the authoritative path."""
        try:
            record = MemoryRecord(
                type=MemoryType.SEMANTIC,
                content=f"{key}: {value}",
                summary=str(value)[:200],
                source=source,
                importance=0.7,
                confidence=confidence,
                retention_policy=RetentionPolicy.LONG_TERM,
                scope=MemoryScope.USER,
                status=MemoryStatus.ACTIVE,
                provenance=Provenance.SYSTEM_OBSERVED,
                tags={key},
                metadata={"key": key},
            )
            return self.remember(record)
        except Exception:
            log.exception("[Memory] Failed to store semantic fact")
            return False

    def remember_reflection(self, reflection: Any) -> bool:
        """Legacy compat: store a reflection as an EPISODIC record."""
        try:
            text = str(reflection)
            if hasattr(reflection, "to_dict") and callable(reflection.to_dict):
                text = str(reflection.to_dict())
            return self.remember(MemoryRecord(
                type=MemoryType.EPISODIC,
                content=text[:1000],
                summary=f"Reflection: {text[:80]}",
                source="reflection",
                importance=0.8,
                confidence=0.7,
                retention_policy=RetentionPolicy.MEDIUM_TERM,
                scope=MemoryScope.SESSION,
                status=MemoryStatus.ACTIVE,
                provenance=Provenance.SYSTEM_OBSERVED,
                metadata={"category": "reflection"},
            ))
        except Exception:
            log.exception("[Memory] Failed to store reflection")
            return False

    def learn(self, observation: Any, events: Any = None,
              predictions: Any = None) -> bool:
        """Legacy compat: AutonomyLoop learning hook -> EPISODIC record."""
        try:
            content = f"Observation: {observation}\nEvents: {events}\nPredictions: {predictions}"
            return self.remember(MemoryRecord(
                type=MemoryType.EPISODIC,
                content=content[:1000],
                summary=f"Learned: {str(observation)[:80]}",
                source="autonomy",
                importance=0.7,
                confidence=0.6,
                retention_policy=RetentionPolicy.MEDIUM_TERM,
                scope=MemoryScope.SESSION,
                status=MemoryStatus.ACTIVE,
                provenance=Provenance.SYSTEM_OBSERVED,
                metadata={"category": "learning"},
            ))
        except Exception:
            log.exception("[Memory] Failed to record learning observation")
            return False

    def retrieve(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        """Legacy-compatible search entry point (alias of recall_by_content)."""
        return self.recall_by_content(query, limit=limit)

    # ------------------------------------------
    # Persistence
    # ------------------------------------------

    def _persist(self):
        """
        Persist memories to disk using the unified memory format.

        M14: deferred + coalesced. Marks the store dirty and schedules a single
        background write after `_flush_delay`. Rapid consecutive writes collapse
        into one disk write per flush window. Explicit durability points should
        call `flush()` or `_persist_immediate()`.
        """
        self._dirty = True
        with self._flush_lock:
            if self._flush_thread_alive:
                return
            self._flush_thread_alive = True
            try:
                threading.Thread(target=self._flush_target, daemon=True).start()
            except Exception as exc:
                self._flush_thread_alive = False
                log.error(f"[Memory] Failed to schedule deferred flush: {exc}")

    def _flush_target(self) -> None:
        try:
            time.sleep(self._flush_delay)
            self._write_snapshot()
        except Exception as exc:
            log.error(f"[Memory] Deferred flush failed: {exc}")
        finally:
            self._flush_thread_alive = False

    def _write_snapshot(self, *, respect_cooldown: bool = True) -> None:
        """Synchronous, guarded snapshot write.

        No-op when the store is clean. A *background* write respects the
        post-failure cooldown for this store (storm prevention); an *explicit*
        durability point (flush / _persist_immediate) forces an attempt.

        ``_dirty`` is cleared ONLY when the write actually landed. A skipped or
        abandoned write keeps the data pending, so the next flush persists it —
        previously a cooldown-skipped write was reported as success and the
        pending records could be lost on shutdown.
        """
        if not self._dirty:
            return
        if respect_cooldown and persistence.is_on_cooldown(self._store_path):
            log.debug("[Memory] Skipping snapshot write — persistence on cooldown (%.0fs remaining)",
                      persistence.cooldown_remaining_s(self._store_path))
            return
        try:
            with self._lock:
                active_records = [record for record in self._records.values()
                                  if record.status == MemoryStatus.ACTIVE]
                written = persistence.save_unified_memory_records(
                    active_records, self._store_path,
                    respect_cooldown=respect_cooldown)
                if written:
                    self._dirty = False
                    log.debug(f"[Memory] Persisted {len(active_records)} active memories to {self._store_path}")
                else:
                    log.debug("[Memory] Snapshot write skipped (store busy); state kept in memory")
        except Exception as exc:
            log.error(f"[Memory] Failed to persist memories: {exc}")

    def _persist_immediate(self):
        """Immediate synchronous persist for explicit, user-driven operations.

        Forces the write past the background cooldown: an explicit durability
        request must never be silently skipped.
        """
        self._write_snapshot(respect_cooldown=False)

    def flush(self) -> None:
        """Force an immediate synchronous write of any pending changes (M14)."""
        self._write_snapshot(respect_cooldown=False)

    def __del__(self):
        try:
            self.flush()
        except Exception:
            pass

    def _load_memories(self):
        """
        Load memories from disk using the unified memory format.
        """
        try:
            records = persistence.load_unified_memory_records(self._store_path)
            with self._lock:
                self._records = {record.id: record for record in records}
                log.info(f"[Memory] Loaded {len(self._records)} memories from {self._store_path}")
        except Exception as exc:
            log.warning(f"[Memory] Failed to load memories from {self._store_path}: {exc}")
            # Start with empty memory store
            with self._lock:
                self._records = {}

    # ------------------------------------------
    # Utility Methods
    # ------------------------------------------

    def _contains_sensitive_data(self, record: MemoryRecord) -> bool:
        """
        Check if a memory record contains sensitive data.

        Scans content, summary, tags, entities, and metadata recursively.
        The recursive dict scan in is_sensitive_text() also flags secret-like
        KEY NAMES (e.g. metadata={"api_key": ...}), closing the key-hint gap.

        Args:
            record: MemoryRecord to check

        Returns:
            True if sensitive data detected, False otherwise
        """
        if persistence.is_sensitive_text(record.content) or \
           persistence.is_sensitive_text(record.summary):
            return True
        if any(persistence.is_sensitive_text(str(tag)) for tag in record.tags):
            return True
        if any(persistence.is_sensitive_text(str(entity)) for entity in record.entities):
            return True
        if record.metadata and persistence.is_sensitive_text(record.metadata):
            return True
        return False

    def _find_existing_by_fingerprint(self, fingerprint: str) -> Optional[str]:
        """
        Find an existing memory record by its fingerprint.

        Args:
            fingerprint: Fingerprint to search for

        Returns:
            ID of existing memory if found, None otherwise
        """
        for memory_id, record in self._records.items():
            if record.fingerprint == fingerprint and record.status == MemoryStatus.ACTIVE:
                return memory_id
        return None

    def _update_existing_memory(self, existing: MemoryRecord, incoming: MemoryRecord,
                                same_id: bool = False) -> bool:
        """
        Update an existing memory record with new information.

        Args:
            existing: Existing memory record to update
            incoming: Incoming memory record with new information
            same_id: True when the incoming record carries the same ID (an
                     explicit update) vs. a deduplicated duplicate (M5).

        Returns:
            True if updated, False otherwise
        """
        # Update fields that should be refreshed
        existing.updated_at = time.time()
        existing.access_count = max(existing.access_count, incoming.access_count)

        # Update importance and confidence if the incoming values are higher
        if incoming.importance > existing.importance:
            existing.importance = incoming.importance
        if incoming.confidence > existing.confidence:
            existing.confidence = incoming.confidence

        # The incoming content is the authoritative value for an update.
        if existing.content != incoming.content:
            existing.content = incoming.content
            if incoming.summary:
                existing.summary = incoming.summary

        # Merge tags, entities, and relations
        existing.tags = existing.tags.union(incoming.tags)
        existing.entities = existing.entities.union(incoming.entities)
        existing.relations = persistence.merge_memory_relations(existing.relations, incoming.relations)

        # Update metadata
        existing.metadata.update(incoming.metadata)

        # Adopt the incoming provenance/type/scope/ids when they are more specific
        if incoming.provenance != Provenance.SYSTEM_OBSERVED:
            existing.provenance = incoming.provenance
        if incoming.scope != MemoryScope.GLOBAL or existing.scope == MemoryScope.GLOBAL:
            existing.scope = incoming.scope
        existing.type = incoming.type
        if incoming.project_id:
            existing.project_id = incoming.project_id
        if incoming.task_id:
            existing.task_id = incoming.task_id
        if incoming.conversation_id:
            existing.conversation_id = incoming.conversation_id

        # Handle versioning - increment version when updating
        existing.version += 1

        # A refreshed record is the current authoritative version.
        existing.status = MemoryStatus.ACTIVE
        existing.superseded_by = None

        # Update fingerprint
        existing.update_fingerprint()

        log.debug(f"[Memory] Updated existing memory: {existing.id[:8]} (version {existing.version})")
        self._persist()
        return True

    def _supersede_and_store(self, existing: MemoryRecord, incoming: MemoryRecord) -> bool:
        """
        Version-chain an update: the existing memory is marked SUPERSEDED and the
        incoming memory is stored as the new ACTIVE version with back/forward links.

        Args:
            existing: Existing ACTIVE memory being superseded
            incoming: Incoming memory carrying the updated value

        Returns:
            True on success
        """
        with self._lock:
            existing.supersede_by(incoming.id)
            existing.status = MemoryStatus.SUPERSEDED
            incoming.supersedes = existing.id
            incoming.version = max(incoming.version, existing.version + 1)
            incoming.update_fingerprint()
            self._records[incoming.id] = incoming
            log.debug(
                f"[Memory] Superseded {existing.id[:8]} v{existing.version} "
                f"with {incoming.id[:8]} v{incoming.version}"
            )
            self._persist()
        return True

    def _content_essentially_identical(self, a: MemoryRecord, b: MemoryRecord) -> bool:
        """True when two records carry the same fact (pure duplicate)."""
        if self._normalize_content_for_comparison(a.content) == \
           self._normalize_content_for_comparison(b.content):
            return True
        return a.fingerprint == b.fingerprint or \
            calculate_memory_similarity(a, b) > 0.9

    # ------------------------------------------
    # Write Governance Pipeline Methods
    # ------------------------------------------

    def _score_importance(self, record: MemoryRecord) -> float:
        """
        Score the importance of a memory based on multiple factors.

        Factors:
        - User explicit designation (high importance)
        - Relevance to current context/goals
        - Predicted future usefulness
        - Frequency/repetition indicators
        - Recency (more recent = slightly more important initially)
        - Task/project impact
        - Source credibility
        - Novelty/uniqueness

        Args:
            record: MemoryRecord to score

        Returns:
            Importance score between 0.0 and 1.0
        """
        # Start with the base importance from the record
        base_importance = record.importance

        # Initialize factor scores
        factors = []
        weights = []

        # 1. User explicit designation (high weight)
        if record.provenance == Provenance.USER_EXPLICIT:
            factors.append(0.9)  # Explicit user memories are important
            weights.append(0.25)
        else:
            factors.append(base_importance)  # Use base importance
            weights.append(0.15)

        # 2. Relevance to current context (would be enhanced with context awareness)
        # For now, use the relevance field if set, otherwise default
        relevance_score = record.relevance if hasattr(record, 'relevance') else 0.5
        factors.append(relevance_score)
        weights.append(0.20)

        # 3. Predicted future usefulness (simplified heuristic)
        usefulness_score = self._estimate_future_usefulness(record)
        factors.append(usefulness_score)
        weights.append(0.15)

        # 4. Frequency indicators (simplified - would track repetition in full system)
        frequency_score = 0.5  # Default moderate frequency assumption
        factors.append(frequency_score)
        weights.append(0.10)

        # 5. Recency boost (more recent gets slight boost)
        recency_score = record.recency if hasattr(record, 'recency') else 0.5
        factors.append(recency_score)
        weights.append(0.10)

        # 6. Task/project impact (higher impact = higher importance)
        impact_score = self._estimate_task_project_impact(record)
        factors.append(impact_score)
        weights.append(0.10)

        # 7. Source credibility
        source_score = self._score_source_credibility(record.source)
        factors.append(source_score)
        weights.append(0.05)

        # 8. Novelty/uniqueness (would be enhanced with similarity checking)
        novelty_score = 0.7  # Default to moderately novel
        factors.append(novelty_score)
        weights.append(0.05)

        # Calculate weighted average
        if sum(weights) > 0:
            weighted_sum = sum(f * w for f, w in zip(factors, weights))
            total_weight = sum(weights)
            final_importance = weighted_sum / total_weight
        else:
            final_importance = base_importance

        # Ensure bounds
        final_importance = max(0.0, min(1.0, final_importance))

        # M5: never let scoring lower an explicitly-set importance value.
        final_importance = max(final_importance, base_importance)

        log.debug(f"[Memory] Importance scoring: base={base_importance:.2f}, final={final_importance:.2f}")
        return final_importance

    def _score_confidence(self, record: MemoryRecord) -> float:
        """
        Score the confidence of a memory based on source and evidence.

        Args:
            record: MemoryRecord to score

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Start with the base confidence from the record
        base_confidence = record.confidence

        # Adjust based on provenance
        provenance_adjustments = {
            Provenance.USER_EXPLICIT: 0.9,      # User explicitly stated - high confidence
            Provenance.USER_IMPLICIT: 0.7,      # Inferred from behavior - medium confidence
            Provenance.TOOL_OBSERVED: 0.8,      # Directly observed via tools - high confidence
            Provenance.SYSTEM_OBSERVED: 0.85,   # System observed - high confidence
            Provenance.DOCUMENT_DERIVED: 0.75,  # Extracted from documents - good confidence
            Provenance.MODEL_INFERRED: 0.6,     # Inferred by AI/ML - medium confidence
            Provenance.PEER_VALIDATED: 0.95,    # Validated by peers - very high confidence
            Provenance.CONSENSUS: 0.9           # Agreed by multiple sources - high confidence
        }

        provenance_adjustment = provenance_adjustments.get(record.provenance, 0.5)

        # Combine base confidence with provenance adjustment
        # Weighted average: 60% base confidence, 40% provenance adjustment
        final_confidence = (base_confidence * 0.6) + (provenance_adjustment * 0.4)

        # Ensure bounds
        final_confidence = max(0.0, min(1.0, final_confidence))

        # M5: never let scoring lower an explicitly-set confidence value.
        final_confidence = max(final_confidence, base_confidence)

        log.debug(f"[Memory] Confidence scoring: base={base_confidence:.2f}, provenance_adj={provenance_adjustment:.2f}, final={final_confidence:.2f}")
        return final_confidence

    def _assess_usefulness(self, record: MemoryRecord) -> bool:
        """
        Assess the usefulness/predicted future utility of a memory.

        Args:
            record: MemoryRecord to assess

        Returns:
            True if useful enough to store, False otherwise
        """
        # Simple usefulness assessment based on several factors

        # 1. Very low importance memories might not be useful
        if record.importance < 0.1:
            return False

        # 2. Ephemeral memories with very short TTL might not be worth storing
        if (record.retention_policy == RetentionPolicy.EPHEMERAL and
            hasattr(record, 'created_at')):
            age = time.time() - record.created_at
            # If it's already old for ephemeral, maybe not useful
            if age > 300:  # 5 minutes
                return False

        # 3. Memories with extremely low confidence might not be useful
        if record.confidence < 0.2:
            return False

        # 4. Check if it's actionable or predictive
        # (This would be enhanced in a full implementation)

        # Default: useful enough to store
        return True

    def _find_existing_similar_memory(self, record: MemoryRecord) -> Optional[str]:
        """
        Find an existing memory that is similar to the given record.

        Enhanced for M5: Implements multi-level deduplication:
        LEVEL 1: Exact fingerprint match
        LEVEL 2: Normalized-content match
        LEVEL 3: Same semantic fact with different wording
        LEVEL 4: Semantic similarity where the existing architecture supports it

        Deduplication respects scope - memories in different scopes are not
        automatically treated as duplicates unless they are GLOBAL memories.

        Args:
            record: MemoryRecord to check for similarity

        Returns:
            ID of existing similar memory if found, None otherwise
        """
        with self._lock:
            # Deduplication is tier-aware (M7): WORKING / EPISODIC / SEMANTIC /
            # PREFERENCE / PROCEDURAL are distinct memory kinds, so a record only
            # deduplicates against another record of the SAME type. This keeps the
            # consolidation pipeline from merging a promoted record back into its
            # source record (e.g. the new EPISODIC merging into the WORKING input).

            # LEVEL 1: Exact fingerprint match (fast path)
            exact_match = self._find_existing_by_fingerprint(record.fingerprint)
            if exact_match:
                existing = self._records.get(exact_match)
                if existing is not None and existing.type == record.type:
                    return exact_match

            # LEVEL 2: Normalized-content match
            # Create a normalized version of the content for comparison
            normalized_content = self._normalize_content_for_comparison(record.content)

            for existing_id, existing_record in self._records.items():
                if existing_record.status != MemoryStatus.ACTIVE:
                    continue
                if existing_record.type != record.type:
                    continue

                # Check if normalized content matches (respecting scope)
                if self._normalized_content_match(record, existing_record, normalized_content):
                    return existing_id

            # LEVEL 3: Same semantic fact with different wording
            # and LEVEL 4: Semantic similarity
            for existing_id, existing_record in self._records.items():
                if existing_record.status != MemoryStatus.ACTIVE:
                    continue
                if existing_record.type != record.type:
                    continue

                # Only consider memories in compatible scopes for semantic deduplication
                if not self._scopes_compatible_for_deduplication(record.scope, existing_record.scope):
                    continue

                # Calculate semantic similarity
                similarity = calculate_memory_similarity(record, existing_record)

                # If highly similar (>0.85), treat as duplicate for updating
                if similarity > 0.85:
                    log.debug(f"[Memory] Found semantically similar memory: {existing_id[:8]} (similarity={similarity:.2f})")
                    return existing_id

        return None

    def _normalize_content_for_comparison(self, content: str) -> str:
        """
        Normalize content for comparison purposes.

        Args:
            content: Raw content string

        Returns:
            Normalized content string
        """
        if not content:
            return ""

        # Convert to lowercase
        normalized = content.lower()
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        # Remove common punctuation that doesn't affect meaning
        normalized = re.sub(r'[.,!?;:]', '', normalized)
        # Remove extra spaces again
        normalized = ' '.join(normalized.split())

        return normalized

    def _normalized_content_match(self, record1: MemoryRecord, record2: MemoryRecord,
                                 normalized_content1: str) -> bool:
        """
        Check if two memories match based on normalized content, respecting scope.

        Args:
            record1: First memory record
            record2: Second memory record
            normalized_content1: Pre-normalized content of record1

        Returns:
            True if memories match based on normalized content and scope, False otherwise
        """
        # Normalize content of record2
        normalized_content2 = self._normalize_content_for_comparison(record2.content)

        # Check if normalized content matches
        if normalized_content1 != normalized_content2:
            return False

        # Check scope compatibility - memories must be in the same scope or
        # one must be GLOBAL and the other USER/PROJECT for GLOBAL to win
        if not self._scopes_compatible_for_deduplication(record1.scope, record2.scope):
            return False

        # For same scope, check project/task/conversation alignment
        if record1.scope == record2.scope:
            if record1.scope == MemoryScope.PROJECT:
                if record1.project_id != record2.project_id:
                    return False
            elif record1.scope == MemoryScope.TASK:
                if record1.task_id != record2.task_id:
                    return False
            elif record1.scope == MemoryScope.CONVERSATION:
                if record1.conversation_id != record2.conversation_id:
                    return False

        return True

    def _scopes_compatible_for_deduplication(self, scope1: MemoryScope, scope2: MemoryScope) -> bool:
        """
        Check if two scopes are compatible for deduplication purposes (M5).

        This is DIRECTIONAL: scope1 is the INCOMING (new) memory and scope2 is
        the EXISTING (stored) memory.

        - Same scope is always compatible.
        - An incoming GLOBAL memory may deduplicate with any narrower scope
          (GLOBAL wins over USER/PROJECT/TASK).
        - A narrower incoming scope NEVER deduplicates with a broader existing
          GLOBAL memory â€” that would break scope isolation.

        Args:
            scope1: Incoming (new) scope
            scope2: Existing (stored) scope

        Returns:
            True if scopes are compatible for deduplication, False otherwise
        """
        # Same scope is always compatible
        if scope1 == scope2:
            return True

        # Incoming GLOBAL may deduplicate with a narrower existing scope
        if scope1 == MemoryScope.GLOBAL:
            return True

        # A narrower incoming scope is isolated from broader existing scope
        return False

    def _check_and_resolve_conflicts(self, record: MemoryRecord) -> tuple[str, list]:
        """
        Check for conflicting memories and determine resolution action.

        Enhanced for M5: Implements comprehensive conflict detection and resolution
        with support for all resolution policies:
        KEEP_EXISTING, KEEP_NEW, MERGE, SUPERSEDE, MARK_CONFLICT, REQUIRE_CONFIRMATION

        Returns:
            tuple of (action, conflicting_memories) where:
            action: "keep", "update", "supersede", "merge", "replace",
                    "mark_conflict", "keep_existing", "require_confirmation",
                    or "reject"
            conflicting_memories: list of (existing_id, existing_record) tuples
                                for memories in conflict (empty list if no conflicts)
        """
        with self._lock:
            conflicts = []

            # Check for potential conflicts with existing memories
            for existing_id, existing_record in self._records.items():
                if existing_record.status != MemoryStatus.ACTIVE:
                    continue
                if existing_id == record.id:
                    continue

                if not self._is_potential_conflict(record, existing_record):
                    continue

                similarity = calculate_memory_similarity(record, existing_record)
                action = self._resolve_conflict(record, existing_record, similarity)
                conflicts.append((existing_id, existing_record, action))

            if not conflicts:
                return "keep", []

            conflicting_memories = [
                (existing_id, existing_record)
                for existing_id, existing_record, _ in conflicts
            ]

            # Determine final action by priority (most severe/authoritative first).
            for action in (
                "require_confirmation",
                "replace",
                "supersede",
                "update",
                "merge",
                "keep_existing",
            ):
                if any(a == action for _, _, a in conflicts):
                    return action, conflicting_memories

            return "mark_conflict", conflicting_memories

    def _is_potential_conflict(self, record1: MemoryRecord, record2: MemoryRecord) -> bool:
        """
        Check if two records represent a potential conflict (same subject, different values).

        Conflicts are strictly scope-isolated (M5): only memories in the SAME
        scope AND SAME project/task/conversation context can conflict. Different
        scopes/contexts are never treated as conflicts.

        Beyond context matching, the records must actually concern the SAME
        subject to be a conflict:
        - PROJECT/TASK/CONVERSATION scopes are anchored by their matching IDs.
        - USER/GLOBAL scopes require a shared explicit subject (tag/entity or
          content-extracted subject) OR an explicit user statement, so that
          loosely-related distinct facts (e.g. "Test memory 0" vs "Test memory 1")
          are never treated as conflicts.

        Args:
            record1: First memory record
            record2: Second memory record

        Returns:
            True if records represent a potential conflict, False otherwise
        """
        # Strict scope/context isolation â€” conflicts never cross boundaries.
        if record1.scope != record2.scope:
            return False
        if record1.project_id != record2.project_id:
            return False
        if record1.task_id != record2.task_id:
            return False
        if record1.conversation_id != record2.conversation_id:
            return False

        # Must be same type
        if record1.type != record2.type:
            return False

        # Similarity band: not a duplicate (>0.9) and not unrelated (<0.1).
        similarity = calculate_memory_similarity(record1, record2)
        if not (0.1 < similarity <= 0.9):
            return False

        # Contextual scopes anchor the subject via their matching IDs.
        if record1.scope in (MemoryScope.PROJECT, MemoryScope.TASK,
                             MemoryScope.CONVERSATION):
            return True

        # An explicit user statement always conflicts with whatever it changes.
        if record1.provenance == Provenance.USER_EXPLICIT or \
           record2.provenance == Provenance.USER_EXPLICIT:
            return True

        # USER/GLOBAL scopes require a genuinely shared subject.
        return self._share_subject(record1, record2)

    def _extract_memory_subjects(self, record: MemoryRecord) -> Set[str]:
        """
        Extract subject/key concepts from a memory record.

        Args:
            record: Memory record to extract subjects from

        Returns:
            Set of subject strings
        """
        subjects = set()

        # Add explicit tags as subjects
        subjects.update(record.tags)

        # Add entities as subjects
        subjects.update(record.entities)

        # Extract from content - look for key-value patterns
        content_lower = record.content.lower()

        # Simple extraction: look for patterns like "X is Y", "X: Y", "X equals Y"
        # This is a simplified implementation - would be enhanced with NLP

        # Split by common separators and look for key-value patterns
        separators = [':', 'is', 'equals', '=', '-', ' -- ', ' - ']
        for sep in separators:
            if sep in content_lower:
                parts = content_lower.split(sep, 1)
                if len(parts) == 2:
                    key_part = parts[0].strip()
                    value_part = parts[1].strip()
                    # If key part looks like a subject (reasonable length, not just common words)
                    if len(key_part) > 2 and not self._is_common_word(key_part):
                        subjects.add(key_part)

        # Also add metadata keys as potential subjects
        subjects.update(record.metadata.keys())

        return subjects

    def _subjects_overlap_significantly(self, subjects1: Set[str], subjects2: Set[str]) -> bool:
        """
        Check if two sets of subjects overlap significantly enough to indicate a conflict.

        Args:
            subjects1: First set of subjects
            subjects2: Second set of subjects

        Returns:
            True if subjects overlap significantly, False otherwise
        """
        if not subjects1 or not subjects2:
            return False

        # Calculate overlap
        intersection = subjects1.intersection(subjects2)
        union = subjects1.union(subjects2)

        if not union:
            return False

        overlap_ratio = len(intersection) / len(union)
        return overlap_ratio >= 0.3  # At least 30% overlap

    def _is_common_word(self, word: str) -> bool:
        """
        Check if a word is a common word that shouldn't be treated as a subject.

        Args:
            word: Word to check

        Returns:
            True if word is common, False otherwise
        """
        common_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
        return word.lower() in common_words

    def _calculate_memory_quality_score(self, record: MemoryRecord) -> float:
        """
        Calculate a quality score for a memory to help resolve conflicts.

        Factors: importance, confidence, provenance, recency, specificity

        Args:
            record: Memory record to score

        Returns:
            Quality score (higher is better)
        """
        # Base score from importance and confidence
        base_score = (record.importance + record.confidence) / 2

        # Provenance adjustment (more reliable sources get higher scores)
        provenance_scores = {
            Provenance.USER_EXPLICIT: 1.0,      # Highest reliability
            Provenance.PEER_VALIDATED: 0.95,    # Very high reliability
            Provenance.SYSTEM_OBSERVED: 0.9,    # High reliability
            Provenance.TOOL_OBSERVED: 0.85,     # Good reliability
            Provenance.DOCUMENT_DERIVED: 0.8,   # Good reliability
            Provenance.CONSENSUS: 0.85,         # Good reliability
            Provenance.USER_IMPLICIT: 0.7,      # Medium reliability
            Provenance.MODEL_INFERRED: 0.6      # Lower reliability (but still useful)
        }
        provenance_score = provenance_scores.get(record.provenance, 0.5)

        # Recency factor (more recent gets slight boost)
        recency_factor = record.recency if hasattr(record, 'recency') else 0.5

        # Specificity factor (more specific content gets slight boost)
        specificity_score = self._calculate_content_specificity(record.content)

        # Combine factors with weights
        quality_score = (
            base_score * 0.4 +           # Importance/confidence
            provenance_score * 0.3 +     # Source reliability
            recency_factor * 0.2 +       # Recency
            specificity_score * 0.1      # Content specificity
        )

        return quality_score

    def _calculate_content_specificity(self, content: str) -> float:
        """
        Calculate how specific/content-rich a memory is.

        Args:
            content: Memory content string

        Returns:
            Specificity score (0.0 to 1.0)
        """
        if not content:
            return 0.0

        score = 0.0

        # Length factor (longer content tends to be more specific)
        length_score = min(1.0, len(content) / 200)  # Normalize to 200 chars
        score += length_score * 0.3

        # Numbers and specific data increase specificity
        if re.search(r'\d+', content):
            score += 0.2

        # Proper nouns and specific terms
        words = content.split()
        proper_noun_count = sum(1 for word in words if word and word[0].isupper())
        if words:
            proper_noun_score = min(1.0, proper_noun_count / len(words))
            score += proper_noun_score * 0.3

        # Specialized terminology (heuristic: words not in common vocabulary)
        common_words = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                           'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                           'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                           'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'])
        specialized_count = sum(1 for word in words if word.lower() not in common_words and len(word) > 2)
        if words:
            specialized_score = min(1.0, specialized_count / len(words))
            score += specialized_score * 0.2

        return min(1.0, score)

    def _resolve_conflict(self, record1: MemoryRecord, record2: MemoryRecord,
                         similarity: float) -> str:
        """
        Resolve a conflict between two memory records (M5 decision table).

        record1 is the INCOMING (new) record; record2 is the EXISTING (stored)
        record. Resolution priority:

        1. Provenance authority: explicit user truth beats everything.
        2. Version chain: a higher-version record supersedes the lower one.
        3. Same source + shared explicit subject: versioned update.
        4. Same-fact refresh: identical fact, incoming not weaker -> in-place update.
        5. Confidence margin (>= 0.15) -> replace / keep_existing.
        6. Importance margin (>= 0.1) -> replace / keep_existing.
        7. Otherwise -> mark_conflict (keep both, flag).

        Args:
            record1: Incoming/new memory record
            record2: Existing/stored memory record
            similarity: Similarity score between the records

        Returns:
            Resolution action string
        """
        # 1. Provenance authority: explicit user facts win over everything.
        if record1.provenance == Provenance.USER_EXPLICIT and \
           record2.provenance != Provenance.USER_EXPLICIT:
            return "replace"
        if record2.provenance == Provenance.USER_EXPLICIT and \
           record1.provenance != Provenance.USER_EXPLICIT:
            return "keep_existing"

        # 2. Version chain: a higher version number means it is the newer edit.
        if record1.version > record2.version:
            return "supersede"

        # 3. Same source + shared subject: versioned update.
        if record1.source == record2.source and \
           self._share_subject(record1, record2):
            return "supersede"

        # 3b. Contradiction explicitly detected during consolidation (M7): the
        # existing fact was already contradicted by a newer observation, so the
        # old value must be preserved via the version chain (history + the
        # contradiction metadata stay visible). Only consolidation sets this flag.
        if record2.metadata.get("contradictions", 0) > 0 and \
           self._share_subject(record1, record2):
            return "supersede"

        # 4. Same-fact refresh: identical fact with non-weaker incoming values.
        if self._same_fact_refresh(record1, record2, similarity):
            return "update"

        # 5. Confidence margin decides the more reliable statement.
        if record1.confidence - record2.confidence >= 0.15:
            return "replace"
        if record2.confidence - record1.confidence >= 0.15:
            return "keep_existing"

        # 6. Importance margin breaks ties on significance.
        if record1.importance - record2.importance >= 0.1:
            return "replace"
        if record2.importance - record1.importance >= 0.1:
            return "keep_existing"

        # 7. Everything else: preserve both and flag the disagreement.
        return "mark_conflict"

    def _share_explicit_subject(self, a: MemoryRecord, b: MemoryRecord) -> bool:
        """True when both records name the same explicit subject (tag/entity)."""
        if not a.tags or not b.tags:
            return False
        return bool(a.tags.intersection(b.tags)) or \
            bool(a.entities.intersection(b.entities))

    def _share_subject(self, a: MemoryRecord, b: MemoryRecord) -> bool:
        """
        True when both records concern the same subject, via explicit
        tags/entities OR overlap of subjects extracted from their content.
        """
        if self._share_explicit_subject(a, b):
            return True
        return self._subjects_overlap_significantly(
            self._extract_memory_subjects(a),
            self._extract_memory_subjects(b)
        )

    def _same_fact_refresh(self, a: MemoryRecord, b: MemoryRecord,
                           similarity: float) -> bool:
        """
        True when the incoming record refreshes the same fact of the existing
        record in place (same context, non-weaker values, shared subject).
        """
        if a.type != b.type:
            return False
        if a.scope != b.scope:
            return False
        if a.project_id != b.project_id:
            return False
        if a.task_id != b.task_id:
            return False
        if a.conversation_id != b.conversation_id:
            return False
        if similarity < 0.5:
            return False
        if a.confidence < b.confidence - 0.1 or a.importance < b.importance - 0.1:
            return False
        if a.scope == MemoryScope.PROJECT and a.project_id:
            return True
        if a.scope == MemoryScope.TASK and a.task_id:
            return True
        if a.scope == MemoryScope.CONVERSATION and a.conversation_id:
            return True
        return self._share_subject(a, b)

    def _apply_retention_policy(self, record: MemoryRecord) -> str:
        """
        Apply retention policy to make a keep/modify/reject decision.

        Returns:
            "keep" - keep the memory as-is
            "modify" - modify the memory according to policy
            "reject" - reject the memory
        """
        # Check if the memory is already expired based on its retention policy
        if record.is_expired():
            return "reject"

        # For immediate rejection cases
        if record.importance < 0.05 and record.confidence < 0.3:
            return "reject"  # Very low value memories

        # Default: keep the memory
        return "keep"

    def _apply_retention_modifications(self, record: MemoryRecord) -> MemoryRecord:
        """
        Apply modifications to a memory based on retention policy.

        Args:
            record: MemoryRecord to modify

        Returns:
            Modified MemoryRecord
        """
        # For now, return the record as-is
        # In a full implementation, this might adjust retention policy,
        # add metadata, or make other policy-based modifications
        return record

    def _estimate_future_usefulness(self, record: MemoryRecord) -> float:
        """
        Estimate the future usefulness of a memory.

        Args:
            record: MemoryRecord to estimate

        Returns:
            Usefulness score between 0.0 and 1.0
        """
        # Simplified heuristic based on memory type and content
        type_usefulness = {
            MemoryType.SEMANTIC: 0.8,      # Facts are generally useful
            MemoryType.PROCEDURAL: 0.9,    # Skills/workflows are very useful
            MemoryType.EXPERIENCE: 0.85,   # Learning from experience is useful
            MemoryType.PREFERENCE: 0.95,   # User preferences are consistently useful
            MemoryType.EPISODIC: 0.6,      # Events moderately useful
            MemoryType.WORKING: 0.3,       # Working memory less useful long-term
            MemoryType.PROJECT: 0.7,       # Project knowledge useful
            MemoryType.TASK: 0.4,          # Task context temporarily useful
            MemoryType.CONVERSATION: 0.5,  # Conversation history moderately useful
            MemoryType.SYSTEM: 0.4,        # System metadata context-dependent
            MemoryType.IDENTITY: 0.9       # Core identity very useful
        }

        base_usefulness = type_usefulness.get(record.type, 0.5)

        # Adjust based on content characteristics
        content_length = len(record.content)
        if content_length > 100:  # Substantial content
            base_usefulness += 0.1
        elif content_length < 10:  # Trivial content
            base_usefulness -= 0.2

        # Adjust based on specificity (specific facts more useful than vague ones)
        if any(char.isdigit() for char in record.content):  # Contains specific data
            base_usefulness += 0.05

        # Ensure bounds
        return max(0.0, min(1.0, base_usefulness))

    def _estimate_task_project_impact(self, record: MemoryRecord) -> float:
        """
        Estimate the task/project impact of a memory.

        Args:
            record: MemoryRecord to estimate

        Returns:
            Impact score between 0.0 and 1.0
        """
        # Memories associated with specific tasks/projects get higher impact scores
        impact = 0.5  # Base impact

        if record.project_id:
            impact += 0.2  # Project-specific memories are more impactful
        if record.task_id:
            impact += 0.15  # Task-specific memories are impactful
        if record.conversation_id:
            impact += 0.1   # Conversation-specific memories have some impact

        # Certain types are inherently more impactful
        if record.type in [MemoryType.PROCEDURAL, MemoryType.PREFERENCE, MemoryType.SEMANTIC]:
            impact += 0.15

        return max(0.0, min(1.0, impact))

    def _score_source_credibility(self, source: str) -> float:
        """
        Score the credibility of a memory source.

        Args:
            source: Source string to score

        Returns:
            Credibility score between 0.0 and 1.0
        """
        # Guard against a missing/None source (e.g. records built from
        # metadata dicts without a "source" key) — treat as default.
        if not source:
            return 0.6

        source_lower = source.lower()

        # High credibility sources
        if any(trusted in source_lower for trusted in ['user_explicit', 'system_observed', 'tool_observed']):
            return 0.9
        # Medium credibility sources
        elif any(medium in source_lower for medium in ['user_implicit', 'document_derived', 'peer_validated']):
            return 0.7
        # Lower credibility sources
        elif any(low in source_lower for low in ['model_inferred', 'unknown']):
            return 0.5
        else:
            return 0.6  # Default moderate credibility

    def _calculate_content_match_score(self, query: str, record: MemoryRecord) -> float:
        """
        Calculate how well a memory's content matches a query.

        Args:
            query: Lowercase query string
            record: MemoryRecord to score

        Returns:
            Match score between 0.0 and 1.0
        """
        content_lower = record.content.lower()
        summary_lower = record.summary.lower()

        # Exact match gets highest score
        if query in content_lower or query in summary_lower:
            # Score based on how much of the content the query represents
            query_length = len(query)
            content_length = max(len(content_lower), len(summary_lower))
            if content_length > 0:
                return min(1.0, query_length / content_length * 3)  # Boost for exact matches
            return 1.0

        # Partial word matches
        query_words = set(query.split())
        content_words = set(content_lower.split())
        summary_words = set(summary_lower.split())

        # Calculate word overlap
        content_overlap = len(query_words.intersection(content_words))
        summary_overlap = len(query_words.intersection(summary_words))
        total_query_words = len(query_words)

        if total_query_words > 0:
            word_score = (content_overlap + summary_overlap) / (2 * total_query_words)
            return min(1.0, word_score * 2)  # Boost for word matches

        return 0.0

    # ------------------------------------------
    # Advanced Retrieval Pipeline
    # ------------------------------------------

    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query string for retrieval.

        Args:
            query: Raw query string

        Returns:
            Normalized query string
        """
        if not query:
            return ""

        # Basic normalization: lowercase, strip whitespace
        normalized = query.lower().strip()

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        # TODO: Add more sophisticated normalization:
        # - Stemming/lemmatization
        # - Synonym expansion
        # - Stop word removal (optional)
        # - Spell correction

        return normalized

    def _extract_intent_and_context(self, query: str) -> Dict[str, Any]:
        """
        Extract intent and context from a query.

        Args:
            query: Normalized query string

        Returns:
            Dictionary containing intent and context information
        """
        # Simplified intent and context extraction
        # In a full implementation, this would use NLP techniques

        intent_and_context = {
            'intent': 'unknown',
            'context_keywords': [],
            'entities': [],
            'temporal_references': []
        }

        if not query:
            return intent_and_context

        # Simple keyword-based intent detection (would be enhanced with ML)
        query_lower = query.lower()

        # Detect question types
        if any(word in query_lower for word in ['what', 'who', 'where', 'when', 'why', 'how']):
            intent_and_context['intent'] = 'question'
        elif any(word in query_lower for word in ['find', 'search', 'look', 'show']):
            intent_and_context['intent'] = 'search'
        elif any(word in query_lower for word in ['remember', 'recall', 'what did']):
            intent_and_context['intent'] = 'recall'
        elif any(word in query_lower for word in ['how to', 'steps', 'procedure']):
            intent_and_context['intent'] = 'procedural'

        # Extract potential entities (simplified)
        words = query.split()
        for word in words:
            # Simple heuristic: capitalized words might be entities
            if word[0].isupper() and len(word) > 1:
                intent_and_context['entities'].append(word)
            # Words that look like dates or times
            elif any(char.isdigit() for char in word) and len(word) < 10:
                intent_and_context['temporal_references'].append(word)

        # Context keywords are all significant words
        intent_and_context['context_keywords'] = [w for w in words if len(w) > 2]

        return intent_and_context

    def _lexical_retrieval(self, query: str, limit: int) -> List[Tuple[MemoryRecord, float]]:
        """
        Perform lexical retrieval (keyword-based matching).

        Args:
            query: Normalized query string
            limit: Maximum number of results to return

        Returns:
            List of (MemoryRecord, score) tuples
        """
        if not query:
            # Return all active memories sorted by importance if no query
            with self._lock:
                records = [r for r in self._records.values() if r.status == MemoryStatus.ACTIVE]
                records.sort(key=lambda r: (r.importance, r.confidence, r.access_count), reverse=True)
                return [(r, r.importance) for r in records[:limit]]

        # Perform lexical matching
        matches = []
        query_terms = set(query.split())

        with self._lock:
            for record in self._records.values():
                if record.status != MemoryStatus.ACTIVE:
                    continue

                # Calculate lexical match score
                content_terms = set(record.content.lower().split())
                summary_terms = set(record.summary.lower().split())
                print(f"[DEBUG _lexical_retrieval] record.id={record.id}, query_terms={query_terms}, content_terms={content_terms}, summary_terms={summary_terms}")

                # Jaccard similarity for content and summary
                content_overlap = len(query_terms.intersection(content_terms))
                summary_overlap = len(query_terms.intersection(summary_terms))
                total_query_terms = len(query_terms)
                print(f"[DEBUG _lexical_retrieval] record.id={record.id}, content_overlap={content_overlap}, summary_overlap={summary_overlap}, total_query_terms={total_query_terms}")

                if total_query_terms > 0:
                    content_score = content_overlap / total_query_terms if total_query_terms > 0 else 0
                    summary_score = summary_overlap / total_query_terms if total_query_terms > 0 else 0
                    lexical_score = max(content_score, summary_score)  # Take best match
                    print(f"[DEBUG _lexical_retrieval] record.id={record.id}, content_score={content_score}, summary_score={summary_score}, lexical_score={lexical_score}")
                else:
                    lexical_score = 0
                    print(f"[DEBUG _lexical_retrieval] record.id={record.id}, total_query_terms=0, lexical_score={lexical_score}")

                # Boost score for exact phrase matches
                if query in record.content.lower() or query in record.summary.lower():
                    lexical_score = min(1.0, lexical_score + 1.0)
                    print(f"[DEBUG _lexical_retrieval] record.id={record.id}, after boost lexical_score={lexical_score}")
                else:
                    print(f"[DEBUG _lexical_retrieval] record.id={record.id}, no exact phrase match")

                if lexical_score > 0.1:  # Minimum relevance threshold
                    matches.append((record, lexical_score))
                    print(f"[DEBUG _lexical_retrieval] record.id={record.id}, lexical_score>{0.1}, appending")
                else:
                    print(f"[DEBUG _lexical_retrieval] record.id={record.id}, lexical_score<={0.1}, skipping")

        # Sort by lexical score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]

    def _semantic_retrieval(self, query: str, limit: int) -> List[Tuple[MemoryRecord, float]]:
        """
        Perform semantic retrieval (meaning-based matching).

        Args:
            query: Normalized query string
            limit: Maximum number of results to return

        Returns:
            List of (MemoryRecord, score) tuples
        """
        # In a full implementation, this would use vector embeddings
        # For now, we'll fall back to an enhanced lexical approach

        # Use similarity-based matching as a proxy for semantic retrieval
        matches = []

        with self._lock:
            for record in self._records.values():
                if record.status != MemoryStatus.ACTIVE:
                    continue

                # Calculate semantic similarity using existing function
                # Create a temporary record for the query to compare against
                query_record = MemoryRecord(
                    content=query,
                    source="query",
                    importance=0.5,
                    confidence=0.5,
                    scope=MemoryScope.GLOBAL,
                    status=MemoryStatus.ACTIVE
                )

                similarity = calculate_memory_similarity(query_record, record)

                if similarity > 0.1:  # Minimum relevance threshold
                    matches.append((record, similarity))

        # Sort by semantic similarity descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]

    def _merge_and_deduplicate_candidates(self,
                                        lexical_results: List[Tuple[MemoryRecord, float]],
                                        semantic_results: List[Tuple[MemoryRecord, float]]) -> List[Tuple[MemoryRecord, float]]:
        """
        Merge lexical and semantic retrieval results and deduplicate.

        Args:
            lexical_results: Results from lexical retrieval
            semantic_results: Results from semantic retrieval

        Returns:
            Merged and deduplicated list of (MemoryRecord, score) tuples
        """
        # Dictionary to track best score for each memory
        merged_scores = {}

        # Process lexical results
        for record, score in lexical_results:
            if record.id not in merged_scores or score > merged_scores[record.id]:
                merged_scores[record.id] = score  # Store just the score

        # Process semantic results
        for record, score in semantic_results:
            if record.id not in merged_scores or score > merged_scores[record.id]:
                merged_scores[record.id] = score  # Store just the score
            elif record.id in merged_scores:
                # If we have both lexical and semantic scores, combine them
                existing_score = merged_scores[record.id]
                # Combined score: average of lexical and semantic, boosted if both agree
                combined_score = (existing_score + score) / 2
                if existing_score > 0 and score > 0:  # Both methods found something
                    combined_score = min(1.0, combined_score + 0.1)  # Boost for agreement
                merged_scores[record.id] = combined_score

        # Convert back to list of (record, score) tuples and sort by score
        merged_list = []
        all_results = lexical_results + semantic_results
        processed_ids = set()

        for record, score in all_results:
            if record.id in processed_ids:
                continue
            if record.id in merged_scores:
                merged_list.append((record, merged_scores[record.id]))
                processed_ids.add(record.id)

        # Sort by score descending
        merged_list.sort(key=lambda x: x[1], reverse=True)

        return merged_list

    def _merge_and_deduplicate_scored_candidates(self,
                                                 scored_lexical: List[Tuple[MemoryRecord, float]],
                                                 scored_semantic: List[Tuple[MemoryRecord, float]]) -> List[Tuple[MemoryRecord, float]]:
        """
        Merge two lists of scored memory records, taking the higher score for each memory.

        Args:
            scored_lexical: Scored results from lexical retrieval
            scored_semantic: Scored results from semantic retrieval

        Returns:
            Merged and deduplicated list of (MemoryRecord, score) tuples, sorted by score descending
        """
        # Dictionary to track best score for each memory
        best_scores = {}

        # Process lexical results
        for record, score in scored_lexical:
            if record.id not in best_scores or score > best_scores[record.id]:
                best_scores[record.id] = score

        # Process semantic results
        for record, score in scored_semantic:
            if record.id not in best_scores or score > best_scores[record.id]:
                best_scores[record.id] = score

        # Convert back to list of (record, score) tuples
        merged_list = []
        for record_id, score in best_scores.items():
            # We need to retrieve the actual record objects - they should be in one of the input lists
            record = None
            for r, s in scored_lexical + scored_semantic:
                if r.id == record_id:
                    record = r
                    break
            if record is not None:
                merged_list.append((record, score))

        # Sort by score descending
        merged_list.sort(key=lambda x: x[1], reverse=True)

        return merged_list

    def _apply_scoring_factors(self,
                             candidates: List[Tuple[MemoryRecord, float]],
                             query: str,
                             intent_and_context: Dict[str, Any],
                             scope: Optional[MemoryScope] = None,
                             project_id: Optional[str] = None,
                             task_id: Optional[str] = None,
                             conversation_id: Optional[str] = None,
                             memory_type: Optional[MemoryType] = None,
                             search_type: str = "general",
                             metadata_filter: Optional[Dict[str, Any]] = None,
                             entity_filter: Optional[Set[str]] = None) -> List[Tuple[MemoryRecord, float]]:
        """
        Apply additional scoring factors to rank candidates.

        Args:
            candidates: List of (MemoryRecord, score) tuples from retrieval
            query: Original query string
            intent_and_context: Extracted intent and context
            scope: Optional scope filter
            project_id: Optional project ID filter
            task_id: Optional task ID filter
            conversation_id: Optional conversation ID filter
            memory_type: Optional memory type filter
            search_type: Type of search being performed
            metadata_filter: Optional metadata filters to apply
            entity_filter: Optional entity filters to apply

        Returns:
            List of (MemoryRecord, score) tuples with applied scoring factors
        """
        scored_candidates = []

        with self._lock:
            for record, base_score in candidates:
                # Skip if not active
                if record.status != MemoryStatus.ACTIVE:
                    continue

                pass

                # Apply metadata filtering (hard filter)
                if metadata_filter:
                    metadata_match = True
                    for key, expected_value in metadata_filter.items():
                        if key not in record.metadata:
                            metadata_match = False
                            break
                        actual_value = record.metadata[key]
                        # Handle both single values and lists of acceptable values
                        if isinstance(expected_value, list):
                            if actual_value not in expected_value:
                                metadata_match = False
                                break
                        else:
                            if actual_value != expected_value:
                                metadata_match = False
                                break
                    if not metadata_match:
                        continue  # Skip this record if it doesn't match metadata filter

                # Apply entity filtering (hard filter)
                if entity_filter:
                    if not entity_filter.issubset(record.entities):
                        continue  # Skip this record if it doesn't contain all required entities

                # Start with base retrieval score
                final_score = base_score

                # Apply scope filtering and scoring
                scope_score = self._calculate_scope_score(record, scope, project_id, task_id, conversation_id, exact_match=True)
                if scope_score == 0 and (scope or project_id or task_id or conversation_id):
                    # If scope is specified and record doesn't match, skip
                    continue
                final_score *= (0.7 + 0.3 * scope_score)  # Weight scope as 30% of score

                # Apply memory type filtering and scoring
                type_score = self._calculate_type_score(record, memory_type, exact_match=True)
                if type_score == 0 and memory_type:
                    # If type is specified and record doesn't match, skip
                    continue
                final_score *= (0.8 + 0.2 * type_score)  # Weight type as 20% of score

                # Apply importance factor (0-1 range)
                importance_factor = 0.5 + 0.5 * record.importance  # Scale to 0.5-1.0
                final_score *= importance_factor

                # Apply confidence factor (0-1 range)
                confidence_factor = 0.5 + 0.5 * record.confidence  # Scale to 0.5-1.0
                final_score *= confidence_factor

                # Apply recency factor (0-1 range)
                recency_factor = 0.3 + 0.7 * record.recency  # Scale to 0.3-1.0
                final_score *= recency_factor

                # Apply access frequency factor (logarithmic scaling)
                access_factor = min(1.0, 0.5 + 0.5 * math.log(1 + record.access_count) / 10)
                final_score *= access_factor

                # Apply relevance to intent/context
                intent_score = self._calculate_intent_match_score(record, intent_and_context)
                final_score *= (0.7 + 0.3 * intent_score)  # Weight intent as 30% of score

                # Apply temporal boost for recent memories if query has temporal context
                temporal_boost = self._calculate_temporal_boost(record, intent_and_context)
                final_score *= temporal_boost

                # Apply search-type specific adjustments
                if search_type == "content":
                    # For content search, boost scores that likely came from good content matches
                    # and reduce scores that are likely from structural similarities only
                    # Heuristic: if base_score is low, it likely came from semantic similarity
                    # based on type/scope rather than content, so reduce it
                    if base_score < 0.3:
                        final_score *= 0.5  # Reduce low-base-score results for content search
                    elif base_score > 0.7:
                        final_score *= 1.2  # Boost high-base-score results for content search

                # Ensure score is in valid range
                final_score = max(0.0, min(1.0, final_score))

                pass

                scored_candidates.append((record, final_score))

        # Sort by final score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates

    def _calculate_scope_score(self,
                               record: MemoryRecord,
                               scope: Optional[MemoryScope] = None,
                               project_id: Optional[str] = None,
                               task_id: Optional[str] = None,
                               conversation_id: Optional[str] = None,
                               exact_match: bool = True) -> float:
        """
        Calculate how well a memory matches the specified scope criteria.

        Args:
            record: MemoryRecord to score
            scope: Target memory scope
            project_id: Target project ID
            task_id: Target task ID
            conversation_id: Optional conversation ID filter
            exact_match: If True, require exact match (returns 0.0 for non-exact matches).
                       If False, allow partial credit for related scopes.

        Returns:
            Scope match score between 0.0 and 1.0
        """
        # If no scope criteria specified, return neutral score
        if not any([scope, project_id, task_id, conversation_id]):
            return 1.0

        # For exact matching (used in filtering), only exact matches get score
        if exact_match:
            scope_match = (scope is None or record.scope == scope)
            project_id_match = (project_id is None or record.project_id == project_id)
            task_id_match = (task_id is None or record.task_id == task_id)
            conversation_id_match = (conversation_id is None or record.conversation_id == conversation_id)

            if scope_match and project_id_match and task_id_match and conversation_id_match:
                return 1.0
            else:
                return 0.0

        score = 0.0
        factors = 0

        # Check scope match
        if scope is not None:
            factors += 1
            if record.scope == scope:
                score += 1.0
            # Partial credit for compatible scopes
            elif scope == MemoryScope.GLOBAL and record.scope in [MemoryScope.USER, MemoryScope.PROJECT]:
                score += 0.5  # Global can access user/project
            elif record.scope == MemoryScope.GLOBAL and scope in [MemoryScope.USER, MemoryScope.PROJECT]:
                score += 0.8  # User/project can access global

        # Check project_id match
        if project_id is not None:
            factors += 1
            if record.project_id == project_id:
                score += 1.0
            elif record.project_id is not None:
                score += 0.2  # Some project relevance

        # Check task_id match
        if task_id is not None:
            factors += 1
            if record.task_id == task_id:
                score += 1.0
            elif record.task_id is not None:
                score += 0.2  # Some task relevance

        # Check conversation_id match
        if conversation_id is not None:
            factors += 1
            if record.conversation_id == conversation_id:
                score += 1.0
            elif record.conversation_id is not None:
                score += 0.2  # Some conversation relevance

        return score / factors if factors > 0 else 1.0

    def _calculate_type_score(self, record: MemoryRecord, memory_type: Optional[MemoryType] = None, exact_match: bool = False) -> float:
        """
        Calculate how well a memory matches the specified type.

        Args:
            record: MemoryRecord to score
            memory_type: Target memory type
            exact_match: If True, require exact match (returns 0.0 for non-exact matches).
                       If False, allow partial credit for related types.

        Returns:
            Type match score between 0.0 and 1.0
        """
        if memory_type is None:
            return 1.0

        # For exact matching (used in filtering), only exact matches get score
        if exact_match:
            return 1.0 if record.type == memory_type else 0.0

        if record.type == memory_type:
            return 1.0
        elif record.type == MemoryType.SEMANTIC and memory_type in [MemoryType.PROCEDURAL, MemoryType.EXPERIENCE]:
            return 0.3  # Some semantic relevance to procedural/experience
        elif record.type == MemoryType.EPISODIC and memory_type == MemoryType.EXPERIENCE:
            return 0.5  # Episodic to experience connection
        else:
            return 0.1  # Minimal cross-type relevance

    def _calculate_intent_match_score(self,
                                    record: MemoryRecord,
                                    intent_and_context: Dict[str, Any]) -> float:
        """
        Calculate how well a memory matches the extracted intent and context.

        Args:
            record: MemoryRecord to score
            intent_and_context: Extracted intent and context from query

        Returns:
            Intent/context match score between 0.0 and 1.0
        """
        if not intent_and_context['context_keywords'] and not intent_and_context['entities']:
            return 0.5  # Neutral score if no context extracted

        score = 0.0
        factors = 0

        # Check context keyword matches
        if intent_and_context['context_keywords']:
            factors += 1
            record_words = set(record.content.lower().split() + record.summary.lower().split())
            query_words = set(intent_and_context['context_keywords'])
            if query_words:
                overlap = len(record_words.intersection(query_words))
                score += overlap / len(query_words)

        # Check entity matches
        if intent_and_context['entities']:
            factors += 1
            record_entities = set(e.lower() for e in record.entities)
            query_entities = set(e.lower() for e in intent_and_context['entities'])
            if query_entities:
                overlap = len(record_entities.intersection(query_entities))
                score += overlap / len(query_entities)

        return score / factors if factors > 0 else 0.5

    def _calculate_temporal_boost(self,
                                record: MemoryRecord,
                                intent_and_context: Dict[str, Any]) -> float:
        """
        Calculate temporal boost for memories based on query temporal context.

        Args:
            record: MemoryRecord to score
            intent_and_context: Extracted intent and context from query

        Returns:
            Temporal boost factor (typically 0.8-1.2)
        """
        # No temporal references in query, return neutral boost
        if not intent_and_context['temporal_references']:
            return 1.0

        # For now, give a small boost to recent memories when query has temporal context
        # In a full implementation, this would do proper temporal reasoning
        if intent_and_context['temporal_references'] and record.recency > 0.7:
            return 1.1  # 10% boost for recent memories when query is temporal
        elif intent_and_context['temporal_references'] and record.recency < 0.3:
            return 0.9  # 10% penalty for old memories when query is temporal
        else:
            return 1.0

    def _advanced_retrieval(self,
                          query: str,
                          search_type: str = "general",
                          limit: int = 10,
                          scope: Optional[MemoryScope] = None,
                          project_id: Optional[str] = None,
                          task_id: Optional[str] = None,
                          conversation_id: Optional[str] = None,
                          memory_type: Optional[MemoryType] = None,
                          metadata_filter: Optional[Dict[str, Any]] = None,
                          entity_filter: Optional[Set[str]] = None) -> List[Tuple[MemoryRecord, float]]:
        """
        Advanced retrieval pipeline implementing the full retrieval workflow.

        Pipeline:
        1. Query normalization
        2. Intent and context extraction
        3. Lexical retrieval
        4. Semantic retrieval
        5. Apply scoring factors (with search-type awareness)
        6. Merge and deduplicate scored candidates
        7. Apply relevance threshold and return top-K

        Args:
            query: Query string to search for
            search_type: Type of search ("general", "content", "scope", "type")
            limit: Maximum number of results to return
            scope: Optional memory scope to filter by
            project_id: Optional project ID for PROJECT scope
            task_id: Optional task ID for TASK scope
            conversation_id: Optional conversation ID for CONVERSATION scope
            memory_type: Optional memory type to filter by

        Returns:
            List of (MemoryRecord, score) tuples ranked by relevance
        """
        # 1. Normalize query
        normalized_query = self._normalize_query(query)

        # 2. Extract intent and context
        intent_and_context = self._extract_intent_and_context(normalized_query)

        # 3. Perform lexical retrieval
        lexical_results = self._lexical_retrieval(normalized_query, limit * 2)

        # 4. Perform semantic retrieval
        semantic_results = self._semantic_retrieval(normalized_query, limit * 2)

        # 5. Apply scoring factors to each result set separately (search-type aware)
        scored_lexical = self._apply_scoring_factors(
            candidates=lexical_results,
            query=normalized_query,
            intent_and_context=intent_and_context,
            scope=scope,
            project_id=project_id,
            task_id=task_id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            search_type=search_type,
            metadata_filter=metadata_filter,
            entity_filter=entity_filter
        )

        scored_semantic = self._apply_scoring_factors(
            candidates=semantic_results,
            query=normalized_query,
            intent_and_context=intent_and_context,
            scope=scope,
            project_id=project_id,
            task_id=task_id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            search_type=search_type,
            metadata_filter=metadata_filter,
            entity_filter=entity_filter
        )

        # 6. Merge and deduplicate scored candidates
        merged_scored_candidates = self._merge_and_deduplicate_scored_candidates(scored_lexical, scored_semantic)

        # 7. Apply relevance threshold and return top-K
        # Filter out very low scoring results
        relevance_threshold = 0.05
        filtered_candidates = [(r, s) for r, s in merged_scored_candidates if s >= relevance_threshold]

        # Return top-K results
        return filtered_candidates[:limit]

    # ------------------------------------------
    # Backup and Maintenance
    # ------------------------------------------

    def backup(self, backup_path: str) -> bool:
        """
        Create a backup of the memory store.

        The backup is written as a sanitized copy: every record is re-checked
        with the F1 secret scan so a compromised or legacy store can never
        leak secrets into an export/backup artifact. Original store untouched.

        Args:
            backup_path: Path to save the backup

        Returns:
            True if backup successful, False otherwise
        """
        try:
            clean_records = []
            with self._lock:
                for record in self._records.values():
                    if self._contains_sensitive_data(record):
                        log.warning(
                            f"[Memory][Security] Excluded sensitive record "
                            f"{record.id[:8]} from backup (never exported)")
                        continue
                    clean_records.append(record)
            import os
            os.makedirs(os.path.dirname(os.path.abspath(backup_path)), exist_ok=True)
            persistence.save_unified_memory_records(clean_records, backup_path)
            log.info(f"[Memory] Sanitized backup created at {backup_path} "
                     f"({len(clean_records)} records)")
            return True
        except Exception as exc:
            log.error(f"[Memory] Failed to create backup: {exc}")
            return False

    def repair(self) -> bool:
        """
        Attempt to repair the memory store by reloading and validation.

        Returns:
            True if repair successful, False otherwise
        """
        try:
            log.info("[Memory] Starting memory store repair")
            old_count = len(self._records)

            # Reload from disk
            self._load_memories()

            new_count = len(self._records)
            log.info(f"[Memory] Memory store repaired: {old_count} -> {new_count} records")
            return True
        except Exception as exc:
            log.error(f"[Memory] Failed to repair memory store: {exc}")
            return False


# ==========================================================
# Convenience Functions
# ==========================================================

def create_unified_memory_manager(store_path: Optional[str] = None) -> UnifiedMemoryManager:
    """
    Create a unified memory manager instance.

    Args:
        store_path: Optional path to memory store file

    Returns:
        UnifiedMemoryManager instance
    """
    return UnifiedMemoryManager(store_path)


# ==========================================================
# Memory Factory Functions (Adapter to Unified Model)
# ==========================================================

def remember_fact(key: str, value: Any, confidence: float = 1.0,
                  source: str = "brain", importance: float = 0.8) -> bool:
    """
    Remember a fact (backward compatibility function).

    Args:
        key: Fact key
        value: Fact value
        confidence: Confidence in accuracy
        source: Source of the fact
        importance: Importance score

    Returns:
        True if remembered successfully, False otherwise
    """
    manager = create_unified_memory_manager()
    record = MemoryRecord(
        type=MemoryType.SEMANTIC,
        content=f"{key}: {str(value)}",
        summary=f"{key} = {str(value)[:100]}",
        source=source,
        confidence=confidence,
        importance=importance,
        retention_policy=RetentionPolicy.LONG_TERM,
        scope=MemoryScope.GLOBAL,
        status=MemoryStatus.ACTIVE,
        tags={key}
    )
    return manager.remember(record)


def remember_event(title: str, description: str = "", category: str = "general",
                   importance: float = 0.5, source: str = "brain") -> bool:
    """
    Remember an event (backward compatibility function).

    Args:
        title: Event title
        description: Event description
        category: Event category
        importance: Importance score
        source: Source of the event

    Returns:
        True if remembered successfully, False otherwise
    """
    manager = create_unified_memory_manager()
    record = MemoryRecord(
        type=MemoryType.EPISODIC,
        content=f"{title}: {description}" if description else title,
        summary=title,
        source=source,
        importance=importance,
        retention_policy=RetentionPolicy.MEDIUM_TERM,
        scope=MemoryScope.USER,
        status=MemoryStatus.ACTIVE,
        tags={category} if category else set()
    )
    return manager.remember(record)


# ==========================================================
# M9 compatibility view classes.
#
# These wrap the authoritative UnifiedMemoryManager and expose the legacy
# MemoryManager sub-manager API shapes so BrainEngine / SuperBrain /
# ContextFusionEngine keep working unchanged against the unified store.
# ==========================================================


class _WorkingView:
    """Legacy-shaped `.working` sub-manager over the unified store."""

    def __init__(self, manager: UnifiedMemoryManager,
                 capacity: int = 100, ttl_seconds: int = 600):
        self.manager = manager
        self.capacity = capacity
        self.ttl = ttl_seconds

    def _entry(self, record: MemoryRecord):
        from .working_memory import MemoryEntry
        return MemoryEntry(
            timestamp=record.created_at,
            category=record.metadata.get("category") or record.summary or "event",
            value=record.content,
            importance=record.importance,
            metadata=dict(record.metadata or {}),
        )

    def _records_sorted(self) -> List[MemoryRecord]:
        with self.manager._lock:
            recs = [r for r in self.manager._records.values()
                    if r.type == MemoryType.WORKING]
        recs.sort(key=lambda r: r.created_at)
        return recs

    def add(self, value: Any, category: str = "event",
            importance: float = 0.5,
            metadata: Optional[dict] = None) -> Any:
        record = MemoryRecord(
            type=MemoryType.WORKING,
            content=str(value),
            summary=category,
            source="brain",
            importance=importance,
            confidence=0.6,
            retention_policy=RetentionPolicy.SHORT_TERM,
            scope=MemoryScope.SESSION,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.SYSTEM_OBSERVED,
            metadata={"category": category, **(metadata or {})},
        )
        self.manager.remember(record)
        return self._entry(record)

    def snapshot(self) -> list:
        return [self._entry(r) for r in self._records_sorted()]

    def recent(self, limit: int = 10) -> list:
        return [self._entry(r) for r in self._records_sorted()[-limit:]]

    def latest(self, category: Optional[str] = None):
        for record in reversed(self._records_sorted()):
            if category is None:
                return self._entry(record)
            if (record.metadata.get("category") or record.summary) == category:
                return self._entry(record)
        return None

    def search(self, category: str) -> list:
        return [
            self._entry(r) for r in self._records_sorted()
            if (r.metadata.get("category") or r.summary) == category
        ]

    def remove(self, entry: Any) -> None:
        with self.manager._lock:
            for mid, record in self.manager._records.items():
                if record.type == MemoryType.WORKING and record.content == entry.value:
                    self.manager._records.pop(mid, None)
                    break
        self.manager._persist_immediate()

    def clear(self) -> None:
        with self.manager._lock:
            doomed = [mid for mid, r in self.manager._records.items()
                      if r.type == MemoryType.WORKING]
            for mid in doomed:
                self.manager._records.pop(mid, None)
        self.manager._persist_immediate()

    def summary(self) -> dict:
        recs = self._records_sorted()
        return {
            "entries": len(recs),
            "capacity": self.capacity,
            "ttl_seconds": self.ttl,
            "latest": self._entry(recs[-1]) if recs else None,
        }

    @property
    def size(self) -> int:
        return len(self._records_sorted())

    @property
    def empty(self) -> bool:
        return self.size == 0

    def __len__(self) -> int:
        return self.size

    def __bool__(self) -> bool:
        return not self.empty

    def __repr__(self) -> str:
        return f"UnifiedWorkingView(entries={self.size})"


class _EpisodicView:
    """Legacy-shaped `.episodic` sub-manager over the unified store."""

    def __init__(self, manager: UnifiedMemoryManager, max_events: int = 5000):
        self.manager = manager
        self.max_events = max_events
        self._next_id = 1

    def _episode(self, record: MemoryRecord) -> Any:
        from .episodic_memory import Episode
        return Episode(
            id=record.id,
            timestamp=record.created_at,
            category=record.metadata.get("category") or "general",
            title=record.summary or record.content[:80],
            description=record.content,
            importance=record.importance,
            metadata=dict(record.metadata or {}),
        )

    def _records_sorted(self) -> List[MemoryRecord]:
        with self.manager._lock:
            recs = [r for r in self.manager._records.values()
                    if r.type == MemoryType.EPISODIC]
        recs.sort(key=lambda r: r.created_at)
        return recs

    def record(self, title: str, category: str = "general",
               description: str = "", importance: float = 0.5,
               metadata: Optional[dict] = None) -> Any:
        record = MemoryRecord(
            type=MemoryType.EPISODIC,
            content=description or title,
            summary=title,
            source=metadata.get("source", "brain") if metadata else "brain",
            importance=importance,
            confidence=0.7,
            retention_policy=RetentionPolicy.MEDIUM_TERM,
            scope=MemoryScope.SESSION,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.SYSTEM_OBSERVED,
            metadata={"category": category, **(metadata or {})},
        )
        self.manager.remember(record)
        return self._episode(record)

    def recent(self, limit: int = 20) -> list:
        return [self._episode(r) for r in self._records_sorted()[-limit:]]

    def by_category(self, category: str) -> list:
        return [
            self._episode(r) for r in self._records_sorted()
            if (r.metadata.get("category") or "general") == category
        ]

    def important(self, threshold: float = 0.8) -> list:
        return [
            self._episode(r) for r in self._records_sorted()
            if r.importance >= threshold
        ]

    def search(self, keyword: str) -> list:
        keyword = keyword.lower()
        return [
            self._episode(r) for r in self._records_sorted()
            if keyword in (r.summary or "").lower()
            or keyword in r.content.lower()
        ]

    def latest(self):
        recs = self._records_sorted()
        return self._episode(recs[-1]) if recs else None

    def timeline(self) -> list:
        return [self._episode(r) for r in self._records_sorted()]

    def clear(self) -> None:
        with self.manager._lock:
            doomed = [mid for mid, r in self.manager._records.items()
                      if r.type == MemoryType.EPISODIC]
            for mid in doomed:
                self.manager._records.pop(mid, None)
        self.manager._persist_immediate()

    def summary(self) -> dict:
        recs = self._records_sorted()
        return {
            "episodes": len(recs),
            "latest": self._episode(recs[-1]) if recs else None,
            "capacity": self.max_events,
        }

    @property
    def size(self) -> int:
        return len(self._records_sorted())

    @property
    def empty(self) -> bool:
        return self.size == 0

    def __len__(self) -> int:
        return self.size

    def __bool__(self) -> bool:
        return not self.empty

    def __repr__(self) -> str:
        return f"UnifiedEpisodicView(episodes={self.size})"


class _SemanticView:
    """Legacy-shaped `.semantic` sub-manager over the unified store."""

    def __init__(self, manager: UnifiedMemoryManager, max_facts: int = 10000):
        self.manager = manager
        self._max_facts = max_facts

    def _key_of(self, record: MemoryRecord) -> str:
        key = record.metadata.get("key")
        if key:
            return str(key)
        tag = next((t for t in (record.tags or set()) if t.lower() != "semantic"), None)
        if tag:
            return tag
        if ": " in record.content:
            return record.content.split(": ", 1)[0].strip()
        return record.content[:40]

    def _knowledge(self, record: MemoryRecord) -> Any:
        from .semantic_memory import Knowledge
        key = self._key_of(record)
        value = record.content
        if key and record.content.startswith(f"{key}: "):
            value = record.content[len(key) + 2:]
        return Knowledge(
            key=key,
            value=value,
            confidence=record.confidence,
            source=record.source,
            created_at=record.created_at,
            updated_at=record.updated_at,
            metadata=dict(record.metadata or {}),
        )

    def _records(self) -> List[MemoryRecord]:
        with self.manager._lock:
            return [r for r in self.manager._records.values()
                    if r.type == MemoryType.SEMANTIC]

    def store(self, key: str, value: Any, confidence: float = 1.0,
              source: str = "brain",
              metadata: Optional[dict] = None) -> Any:
        record = MemoryRecord(
            type=MemoryType.SEMANTIC,
            content=f"{key}: {value}",
            summary=str(value)[:200],
            source=source,
            importance=0.7,
            confidence=confidence,
            retention_policy=RetentionPolicy.LONG_TERM,
            scope=MemoryScope.USER,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.SYSTEM_OBSERVED,
            tags={key},
            metadata={"key": key, **(metadata or {})},
        )
        self.manager.remember(record)
        return self._knowledge(record)

    def get(self, key: str, default=None):
        for record in self._records():
            if self._key_of(record) == key:
                value = record.content
                if record.content.startswith(f"{key}: "):
                    value = record.content[len(key) + 2:]
                return value
        return default

    def knowledge(self, key: str):
        for record in self._records():
            if self._key_of(record) == key:
                return self._knowledge(record)
        return None

    def exists(self, key: str) -> bool:
        return any(self._key_of(r) == key for r in self._records())

    def remove(self, key: str) -> None:
        with self.manager._lock:
            for mid, record in list(self.manager._records.items()):
                if record.type == MemoryType.SEMANTIC and self._key_of(record) == key:
                    self.manager._records.pop(mid, None)
        self.manager._persist_immediate()

    def search(self, text: str) -> list:
        text = text.lower()
        return [
            self._knowledge(r) for r in self._records()
            if text in self._key_of(r).lower() or text in r.content.lower()
        ]

    def summary(self) -> dict:
        recs = self._records()
        return {
            "facts": len(recs),
            "keys": [self._key_of(r) for r in recs],
        }

    def snapshot(self) -> dict:
        return {self._key_of(r): self._knowledge(r) for r in self._records()}

    def clear(self) -> None:
        with self.manager._lock:
            doomed = [mid for mid, r in self.manager._records.items()
                      if r.type == MemoryType.SEMANTIC]
            for mid in doomed:
                self.manager._records.pop(mid, None)
        self.manager._persist_immediate()

    def __len__(self) -> int:
        return len(self._records())

    def __contains__(self, key) -> bool:
        return self.exists(key)

    def __repr__(self) -> str:
        return f"UnifiedSemanticView(facts={len(self)})"