"""
MYRAA Unified Memory Model
Canonical memory record that serves as the single source of truth for both
Python and Node.js memory systems.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from pathlib import Path


class MemoryType(Enum):
    """Types of memories in the MYRAA system."""
    WORKING = "working"           # Short-term cognitive context
    EPISODIC = "episodic"         # Timeline of events
    SEMANTIC = "semantic"         # Facts and knowledge
    PROCEDURAL = "procedural"     # Skills, workflows, procedures
    EXPERIENCE = "experience"     # Learning from outcomes
    PREFERENCE = "preference"     # User preferences and settings
    PROJECT = "project"           # Project-specific knowledge
    TASK = "task"                 # Task-specific context
    CONVERSATION = "conversation" # Conversation history
    SYSTEM = "system"             # System-level metadata
    IDENTITY = "identity"         # Core identity information


class MemoryScope(Enum):
    """Scope isolation levels for memories."""
    GLOBAL = "global"             # Available everywhere
    USER = "user"                 # User-specific
    PROJECT = "project"           # Project-specific
    TASK = "task"                 # Task-specific
    CONVERSATION = "conversation" # Conversation-specific
    SESSION = "session"           # Session-specific


class MemoryStatus(Enum):
    """Status of a memory record."""
    ACTIVE = "active"             # Currently valid and usable
    SUPERSEDED = "superseded"    # Replaced by newer version
    ARCHIVED = "archived"         # Moved to long-term storage
    DELETED = "deleted"           # Marked for deletion
    RETRACTED = "retracted"       # Explicitly withdrawn
    EXPIRED = "expired"           # Past its relevance period
    CONFLICTED = "conflicted"     # In conflict with other memories


class Sensitivity(Enum):
    """Sensitivity levels for memory content."""
    PUBLIC = "public"             # Safe to share anywhere
    INTERNAL = "internal"         # OK within trusted environment
    CONFIDENTIAL = "confidential" # Contains sensitive info
    RESTRICTED = "restricted"     # Highly sensitive (API keys, etc.)


class RetentionPolicy(Enum):
    """How long memories should be retained."""
    EPHEMERAL = "ephemeral"       # Seconds to minutes
    SHORT_TERM = "short_term"     # Hours to days
    MEDIUM_TERM = "medium_term"   # Weeks to months
    LONG_TERM = "long_term"       # Months to years
    PERMANENT = "permanent"       # Indefinite retention
    USER_DEFINED = "user_defined" # Custom retention period


class Provenance(Enum):
    """Source of how the memory was acquired."""
    USER_EXPLICIT = "user_explicit"    # Directly stated by user
    USER_IMPLICIT = "user_implicit"    # Inferred from user behavior
    TOOL_OBSERVED = "tool_observed"    # Observed via tool usage
    SYSTEM_OBSERVED = "system_observed" # Observed by system
    DOCUMENT_DERIVED = "document_derived" # Extracted from documents
    MODEL_INFERRED = "model_inferred"   # Inferred by AI/ML
    PEER_VALIDATED = "peer_validated"   # Validated by other agents
    CONSENSUS = "consensus"             # Agreed upon by multiple sources


@dataclass
class MemoryRecord:
    """
    Canonical memory record representing a single unit of memory in MYRAA.

    This is the unified model that both Python and Node.js systems will use.
    """

    # Core Identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MemoryType = MemoryType.SEMANTIC
    content: str = ""                           # Main memory content
    summary: str = ""                           # Brief summary for quick reference

    # Metadata
    source: str = "unknown"                     # Where this came from
    source_reference: Optional[str] = None      # Reference to source material
    scope: MemoryScope = MemoryScope.GLOBAL     # Isolation scope
    project_id: Optional[str] = None            # Associated project
    task_id: Optional[str] = None               # Associated task
    conversation_id: Optional[str] = None       # Associated conversation

    # Temporal Information
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    event_time: Optional[float] = None          # When the event actually occurred

    # Quality Metrics
    importance: float = 0.5                     # 0.0 to 1.0, how important this is
    confidence: float = 0.5                     # 0.0 to 1.0, confidence in accuracy
    relevance: float = 0.5                      # 0.0 to 1.0, relevance to current context
    salience: float = 0.5                       # 0.0 to 1.0, how noticeable/remarkable
    recency: float = 0.5                        # 0.0 to 1.0, how recent this is
    access_count: int = 0                       # How many times this has been accessed

    # Versioning & Status
    version: int = 1                            # Version number for this memory
    status: MemoryStatus = MemoryStatus.ACTIVE  # Current status

    # Organizational
    tags: Set[str] = field(default_factory=set) # Tags for categorization
    entities: Set[str] = field(default_factory=set) # Named entities mentioned
    relations: Dict[str, List[str]] = field(default_factory=dict) # Relationships

    # Technical
    embedding_reference: Optional[str] = None   # Reference to vector embedding
    sensitivity: Sensitivity = Sensitivity.PUBLIC # Sensitivity level
    retention_policy: RetentionPolicy = RetentionPolicy.MEDIUM_TERM # How long to keep
    metadata: Dict[str, Any] = field(default_factory=dict) # Additional metadata

    # Conflict Resolution
    supersedes: Optional[str] = None           # ID of memory this replaces
    superseded_by: Optional[str] = None        # ID of memory that replaced this

    # Provenance & Hash
    provenance: Provenance = Provenance.SYSTEM_OBSERVED # How we acquired this
    fingerprint: str = field(default="")       # Content hash for deduplication

    def __post_init__(self):
        """Initialize computed fields after creation."""
        if not self.fingerprint:
            self.fingerprint = self._compute_fingerprint()

    def _compute_fingerprint(self) -> str:
        """
        Compute a fingerprint hash of the memory content for deduplication.

        Returns:
            SHA256 hash of normalized content
        """
        # Normalize content for consistent fingerprinting
        normalized = self.content.lower().strip()
        # Also include key identifying fields
        to_hash = f"{self.type.value}:{self.scope.value}:{normalized}"
        if self.project_id:
            to_hash += f":project:{self.project_id}"
        if self.task_id:
            to_hash += f":task:{self.task_id}"

        return hashlib.sha256(to_hash.encode('utf-8')).hexdigest()

    def update_fingerprint(self):
        """Update the fingerprint after content changes."""
        self.fingerprint = self._compute_fingerprint()

    def access(self):
        """Record an access to this memory."""
        self.access_count += 1
        self.last_accessed_at = time.time()
        self._update_recency()

    def _update_recency(self):
        """Update the recency score based on time since creation."""
        # Simple exponential decay - can be made more sophisticated
        age_seconds = time.time() - self.created_at
        # Normalize to 0-1 range with half-life of 30 days
        half_life = 30 * 24 * 3600  # 30 days in seconds
        self.recency = max(0.0, min(1.0, 1.0 - (age_seconds / half_life)))

    def update_importance(self, new_importance: float):
        """
        Update the importance score with bounds checking.

        Args:
            new_importance: New importance value (0.0 to 1.0)
        """
        self.importance = max(0.0, min(1.0, new_importance))
        self.updated_at = time.time()

    def update_confidence(self, new_confidence: float):
        """
        Update the confidence score with bounds checking.

        Args:
            new_confidence: New confidence value (0.0 to 1.0)
        """
        self.confidence = max(0.0, min(1.0, new_confidence))
        self.updated_at = time.time()

    def supersede_by(self, new_memory_id: str):
        """
        Mark this memory as superseded by a newer memory.

        Args:
            new_memory_id: ID of the memory that supersedes this one
        """
        self.status = MemoryStatus.SUPERSEDED
        self.superseded_by = new_memory_id
        self.updated_at = time.time()

    def is_expired(self, max_age_seconds: Optional[float] = None) -> bool:
        """
        Check if this memory has exceeded its retention period.

        Args:
            max_age_seconds: Optional override for max age

        Returns:
            True if memory should be considered expired
        """
        if self.status in [MemoryStatus.DELETED, MemoryStatus.ARCHIVED]:
            return True

        age = time.time() - self.created_at

        # Use explicit max_age if provided
        if max_age_seconds is not None:
            return age > max_age_seconds

        # Otherwise use retention policy
        policy_limits = {
            RetentionPolicy.EPHEMERAL: 5 * 60,          # 5 minutes
            RetentionPolicy.SHORT_TERM: 24 * 3600,      # 1 day
            RetentionPolicy.MEDIUM_TERM: 30 * 24 * 3600, # 30 days
            RetentionPolicy.LONG_TERM: 365 * 24 * 3600, # 1 year
            RetentionPolicy.PERMANENT: float('inf'),    # Never expires
        }

        limit = policy_limits.get(self.retention_policy, 30 * 24 * 3600)  # Default 30 days
        return age > limit

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the memory record to a dictionary for serialization.

        Returns:
            Dictionary representation of the memory
        """
        # Convert enums to their values
        data = asdict(self)
        data['type'] = self.type.value
        data['scope'] = self.scope.value
        data['status'] = self.status.value
        data['sensitivity'] = self.sensitivity.value
        data['retention_policy'] = self.retention_policy.value
        data['provenance'] = self.provenance.value

        # Convert sets to lists for JSON serialization
        data['tags'] = list(self.tags)
        data['entities'] = list(self.entities)

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryRecord':
        """
        Create a MemoryRecord from a dictionary.

        Args:
            data: Dictionary representation of the memory

        Returns:
            MemoryRecord instance
        """
        # Make a copy to avoid modifying the original
        data = data.copy()

        # Convert string values back to enums
        if 'type' in data:
            data['type'] = MemoryType(data['type'])
        if 'scope' in data:
            data['scope'] = MemoryScope(data['scope'])
        if 'status' in data:
            data['status'] = MemoryStatus(data['status'])
        if 'sensitivity' in data:
            data['sensitivity'] = Sensitivity(data['sensitivity'])
        if 'retention_policy' in data:
            data['retention_policy'] = RetentionPolicy(data['retention_policy'])
        if 'provenance' in data:
            data['provenance'] = Provenance(data['provenance'])

        # Convert lists back to sets
        if 'tags' in data:
            data['tags'] = set(data['tags'])
        if 'entities' in data:
            data['entities'] = set(data['entities'])

        return cls(**data)

    def to_json(self) -> str:
        """
        Serialize the memory record to JSON.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> 'MemoryRecord':
        """
        Deserialize a memory record from JSON.

        Args:
            json_str: JSON string representation

        Returns:
            MemoryRecord instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __str__(self) -> str:
        """String representation of the memory."""
        return f"Memory({self.type.value}:{self.id[:8]}:{self.content[:50]}...)"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"MemoryRecord(id='{self.id}', "
                f"type='{self.type.value}', "
                f"content='{self.content[:50]}...', "
                f"scope='{self.scope.value}', "
                f"importance={self.importance:.2f}, "
                f"confidence={self.confidence:.2f})")


# ==========================================================
# Memory Factory Functions
# ==========================================================

def create_working_memory(content: str,
                         source: str = "working",
                         importance: float = 0.3,
                         ttl_seconds: int = 300) -> MemoryRecord:
    """
    Create a working memory record.

    Args:
        content: The memory content
        source: Source of the memory
        importance: Importance score (0.0-1.0)
        ttl_seconds: Time to live in seconds

    Returns:
        MemoryRecord configured as working memory
    """
    policy = RetentionPolicy.EPHEMERAL if ttl_seconds < 600 else RetentionPolicy.SHORT_TERM
    return MemoryRecord(
        type=MemoryType.WORKING,
        content=content,
        source=source,
        importance=importance,
        retention_policy=policy,
        scope=MemoryScope.SESSION,
        status=MemoryStatus.ACTIVE
    )


def create_episodic_memory(title: str,
                          description: str = "",
                          category: str = "event",
                          importance: float = 0.5,
                          metadata: Optional[Dict[str, Any]] = None) -> MemoryRecord:
    """
    Create an episodic memory record.

    Args:
        title: Title of the event
        description: Detailed description
        category: Event category
        importance: Importance score
        metadata: Additional metadata

    Returns:
        MemoryRecord configured as episodic memory
    """
    content = f"{title}: {description}" if description else title
    return MemoryRecord(
        type=MemoryType.EPISODIC,
        content=content,
        summary=title,
        source="episodic",
        importance=importance,
        retention_policy=RetentionPolicy.MEDIUM_TERM,
        scope=MemoryScope.USER,
        status=MemoryStatus.ACTIVE,
        metadata=metadata or {},
        tags={category} if category else set()
    )


def create_semantic_memory(key: str,
                          value: Any,
                          confidence: float = 1.0,
                          source: str = "semantic",
                          metadata: Optional[Dict[str, Any]] = None) -> MemoryRecord:
    """
    Create a semantic memory record.

    Args:
        key: The fact key
        value: The fact value
        confidence: Confidence in accuracy (0.0-1.0)
        source: Source of the fact
        metadata: Additional metadata

    Returns:
        MemoryRecord configured as semantic memory
    """
    content = f"{key}: {str(value)}"
    summary = f"{key} = {str(value)[:100]}"
    return MemoryRecord(
        type=MemoryType.SEMANTIC,
        content=content,
        summary=summary,
        source=source,
        confidence=confidence,
        retention_policy=RetentionPolicy.LONG_TERM,
        scope=MemoryScope.GLOBAL,
        status=MemoryStatus.ACTIVE,
        metadata=metadata or {},
        tags={key}
    )


def create_preference_memory(preference: str,
                            value: Any,
                            source: str = "user_explicit",
                            importance: float = 0.8) -> MemoryRecord:
    """
    Create a preference memory record.

    Args:
        preference: Name of the preference
        value: Value of the preference
        source: How this preference was established
        importance: Importance score (preferences are usually important)

    Returns:
        MemoryRecord configured as preference memory
    """
    content = f"{preference}: {str(value)}"
    summary = f"Preference {preference} = {str(value)[:50]}"
    return MemoryRecord(
        type=MemoryType.PREFERENCE,
        content=content,
        summary=summary,
        source=source,
        importance=importance,
        retention_policy=RetentionPolicy.PERMANENT,
        scope=MemoryScope.USER,
        status=MemoryStatus.ACTIVE,
        tags={preference, "preference"}
    )


def create_procedural_memory(name: str,
                            description: str,
                            steps: List[str],
                            success_rate: float = 1.0,
                            source: str = "observed") -> MemoryRecord:
    """
    Create a procedural memory record (skill/workflow).

    Args:
        name: Name of the procedure
        description: What the procedure does
        steps: List of steps in the procedure
        success_rate: Historical success rate (0.0-1.0)
        source: How this procedure was learned

    Returns:
        MemoryRecord configured as procedural memory
    """
    content = f"Procedure '{name}': {description}\nSteps: {' -> '.join(steps)}"
    summary = f"{name}: {description}"
    importance = 0.7 + (success_rate * 0.3)  # 0.7 to 1.0 based on success

    return MemoryRecord(
        type=MemoryType.PROCEDURAL,
        content=content,
        summary=summary,
        source=source,
        importance=importance,
        retention_policy=RetentionPolicy.LONG_TERM,
        scope=MemoryScope.PROJECT,
        status=MemoryStatus.ACTIVE,
        tags={name, "procedure"},
        entities=set(steps),
        relations={"steps": steps}
    )


def create_experience_memory(goal: str,
                            plan: str,
                            outcome: str,
                            success: bool,
                            user_feedback: str = "",
                            source: str = "experience_engine") -> MemoryRecord:
    """
    Create an experience memory record.

    Args:
        goal: What was attempted
        plan: What was planned
        outcome: What actually happened
        success: Whether it was successful
        user_feedback: Feedback from user
        source: Source of this experience

    Returns:
        MemoryRecord configured as experience memory
    """
    content = f"Goal: {goal}\nPlan: {plan}\nOutcome: {outcome}\nSuccess: {success}\nFeedback: {user_feedback}"
    summary = f"Experience: {goal} -> {'Success' if success else 'Failure'}"
    importance = 0.8 if success else 0.6  # Successful experiences are more important

    return MemoryRecord(
        type=MemoryType.EXPERIENCE,
        content=content,
        summary=summary,
        source=source,
        importance=importance,
        retention_policy=RetentionPolicy.LONG_TERM,
        scope=MemoryScope.USER,
        status=MemoryStatus.ACTIVE,
        tags={"experience", "success" if success else "failure"},
        relations={
            "goal": [goal],
            "plan": [plan],
            "outcome": [outcome],
            "feedback": [user_feedback] if user_feedback else []
        }
    )


# ==========================================================
# Validation Functions
# ==========================================================

def validate_memory_record(record: MemoryRecord) -> List[str]:
    """
    Validate a memory record and return any validation errors.

    Args:
        record: MemoryRecord to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Required fields
    if not record.id:
        errors.append("Memory ID is required")

    if not record.content or not record.content.strip():
        errors.append("Memory content is required")

    # Value ranges
    if not 0.0 <= record.importance <= 1.0:
        errors.append("Importance must be between 0.0 and 1.0")

    if not 0.0 <= record.confidence <= 1.0:
        errors.append("Confidence must be between 0.0 and 1.0")

    if not 0.0 <= record.relevance <= 1.0:
        errors.append("Relevance must be between 0.0 and 1.0")

    if not 0.0 <= record.salience <= 1.0:
        errors.append("Salience must be between 0.0 and 1.0")

    if not 0.0 <= record.recency <= 1.0:
        errors.append("Recency must be between 0.0 and 1.0")

    if record.access_count < 0:
        errors.append("Access count cannot be negative")

    if record.version < 1:
        errors.append("Version must be at least 1")

    # Scope-specific validations
    if record.scope == MemoryScope.PROJECT and not record.project_id:
        errors.append("Project-scoped memory must have a project_id")

    if record.scope == MemoryScope.TASK and not record.task_id:
        errors.append("Task-scoped memory must have a task_id")

    if record.scope == MemoryScope.CONVERSATION and not record.conversation_id:
        errors.append("Conversation-scoped memory must have a conversation_id")

    # Temporal validations
    if record.updated_at < record.created_at:
        errors.append("Updated time cannot be before creation time")

    if record.last_accessed_at < record.created_at:
        errors.append("Last accessed time cannot be before creation time")

    if record.event_time and record.event_time < 0:
        errors.append("Event time cannot be negative")

    return errors


def is_valid_memory(record: MemoryRecord) -> bool:
    """
    Check if a memory record is valid.

    Args:
        record: MemoryRecord to validate

    Returns:
        True if valid, False otherwise
    """
    return len(validate_memory_record(record)) == 0


# ==========================================================
# Memory Utilities
# ==========================================================

def merge_memory_tags(existing: Set[str], new: Set[str]) -> Set[str]:
    """
    Merge two sets of tags, preserving existing ones.

    Args:
        existing: Existing tags
        new: New tags to add

    Returns:
        Merged set of tags
    """
    return existing.union(new)


def merge_memory_entities(existing: Set[str], new: Set[str]) -> Set[str]:
    """
    Merge two sets of entities, preserving existing ones.

    Args:
        existing: Existing entities
        new: New entities to add

    Returns:
        Merged set of entities
    """
    return existing.union(new)


def merge_memory_relations(existing: Dict[str, List[str]],
                          new: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Merge two relations dictionaries, combining lists for same keys.

    Args:
        existing: Existing relations
        new: New relations to merge

    Returns:
        Merged relations dictionary
    """
    result = existing.copy()

    for key, values in new.items():
        if key in result:
            # Combine lists, removing duplicates
            combined = list(set(result[key]).union(set(values)))
            result[key] = combined
        else:
            result[key] = values.copy()

    return result


# ==========================================================
# Memory Comparison Functions
# ==========================================================

def memories_are_equivalent(mem1: MemoryRecord, mem2: MemoryRecord) -> bool:
    """
    Check if two memories are equivalent (same semantic content).

    Args:
        mem1: First memory
        mem2: Second memory

    Returns:
        True if memories are equivalent, False otherwise
    """
    # Check fingerprint first (fastest)
    if mem1.fingerprint == mem2.fingerprint:
        return True

    # Check core content fields
    if (mem1.type == mem2.type and
        mem1.content.lower().strip() == mem2.content.lower().strip() and
        mem1.scope == mem2.scope):

        # Check project/task/context alignment
        if (mem1.project_id == mem2.project_id and
            mem1.task_id == mem2.task_id and
            mem1.conversation_id == mem2.conversation_id):
            return True

    return False


def calculate_memory_similarity(mem1: MemoryRecord, mem2: MemoryRecord) -> float:
    """
    Calculate similarity between two memories (0.0 to 1.0).

    Args:
        mem1: First memory
        mem2: Second memory

    Returns:
        Similarity score (0.0 = completely different, 1.0 = identical)
    """
    # If fingerprints match, they're identical
    if mem1.fingerprint == mem2.fingerprint:
        return 1.0

    score = 0.0
    factors = 0

    # Type similarity
    if mem1.type == mem2.type:
        score += 0.2
    factors += 0.2

    # Scope similarity
    if mem1.scope == mem2.scope:
        score += 0.15
    factors += 0.15

    # Content similarity (simple approach - can be enhanced with NLP)
    content1 = mem1.content.lower().strip()
    content2 = mem2.content.lower().strip()

    if content1 == content2:
        score += 0.3
    elif content1 in content2 or content2 in content1:
        # Partial overlap
        overlap = min(len(content1), len(content2))
        total = max(len(content1), len(content2))
        score += 0.3 * (overlap / total if total > 0 else 0)
    factors += 0.3

    # Project/task/context alignment
    if mem1.project_id == mem2.project_id:
        score += 0.1
    factors += 0.1

    if mem1.task_id == mem2.task_id:
        score += 0.1
    factors += 0.1

    if mem1.conversation_id == mem2.conversation_id:
        score += 0.1
    factors += 0.1

    # Tags overlap
    if mem1.tags and mem2.tags:
        tag_overlap = len(mem1.tags.intersection(mem2.tags))
        tag_total = len(mem1.tags.union(mem2.tags))
        if tag_total > 0:
            score += 0.1 * (tag_overlap / tag_total)
    factors += 0.1

    # Normalize by factors
    return score / factors if factors > 0 else 0.0


if __name__ == "__main__":
    # Simple test when run directly
    print("Testing MYRAA Unified Memory Model...")

    # Test basic creation
    mem = MemoryRecord(
        content="User prefers Hinglish explanations",
        source="user_explicit",
        importance=0.9,
        confidence=0.95,
        scope=MemoryScope.USER,
        type=MemoryType.PREFERENCE,
        provenance=Provenance.USER_EXPLICIT
    )

    print(f"Created memory: {mem}")
    print(f"Fingerprint: {mem.fingerprint}")
    print(f"Is valid: {is_valid_memory(mem)}")
    print(f"Validation errors: {validate_memory_record(mem)}")

    # Test serialization
    json_str = mem.to_json()
    print(f"JSON length: {len(json_str)} characters")

    # Test deserialization
    mem2 = MemoryRecord.from_json(json_str)
    print(f"Deserialized: {mem2}")
    print(f"Equal fingerprints: {mem.fingerprint == mem2.fingerprint}")

    # Test factory functions
    pref_mem = create_preference_memory("language", "Hinglish", "user_explicit")
    print(f"Preference memory: {pref_mem}")

    exp_mem = create_experience_memory(
        goal="Build presentation",
        plan="Research -> Create slides -> Review",
        outcome="Successfully created presentation",
        success=True,
        user_feedback="Great work!"
    )
    print(f"Experience memory: {exp_mem}")

    print("All tests passed!")