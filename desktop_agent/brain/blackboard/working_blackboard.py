"""
MYRAA Working Blackboard

Thread-safe shared runtime storage with EPIC-14E production hardening enhancements.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from .cognitive_context import CognitiveContext


@dataclass
class VersionedValue:
    """A value with version and timestamp for change tracking."""
    value: Any
    version: int
    timestamp: float
    ttl: Optional[float] = None  # Time to live in seconds

    def is_expired(self) -> bool:
        """Check if the value has expired based on TTL."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl


@dataclass
class StateChangeEvent:
    """Event representing a state change."""
    channel: str
    key: str
    old_value: Any
    new_value: Any
    timestamp: float


@dataclass
class IdempotencyRecord:
    """Record for tracking executed actions to prevent duplicates."""
    action_id: str
    task_id: str
    timestamp: float
    result: Any

    def is_expired(self, ttl: float) -> bool:
        """Check if the idempotency record has expired."""
        return time.time() - self.timestamp > ttl


class WorkingBlackboard:
    """
    Runtime shared memory with EPIC-14E production hardening.

    Enhancements for EPIC-14E:
    - Reader-writer lock pattern for better concurrency
    - State versioning and change tracking
    - Idempotency protection for actions
    - Bounded histories to prevent memory leaks
    - State freshness validation
    - Enhanced observability and metrics
    """

    def __init__(self):
        # Reader-writer lock for better concurrency
        # Using a simple implementation: multiple readers OR single writer
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._readers_count = 0

        # Main storage with versioning
        self._channels: dict[str, dict[str, VersionedValue]] = {}

        # Change notification system
        self._change_listeners: dict[str, List[callable]] = defaultdict(list)
        self._global_listeners: List[callable] = []

        # Idempotency tracking for action deduplication
        self._idempotency_records: Dict[str, IdempotencyRecord] = {}
        self._idempotency_ttl = 300.0  # 5 minutes default TTL
        self._max_idempotency_records = 1000  # Maximum number of idempotency records to keep

        # Bounded histories to prevent memory leaks
        self._max_history_size = 1000
        self._state_history: Dict[str, List[StateChangeEvent]] = defaultdict(list)

        # Metrics collection
        self._metrics = {
            'reads': 0,
            'writes': 0,
            'idempotency_hits': 0,
            'idempotency_misses': 0,
            'version_conflicts': 0,
            'expired_cleanups': 0
        }
        self._metrics_lock = threading.Lock()

        # Context and initialization
        self.context = CognitiveContext()
        self.created_at = datetime.utcnow()

        # Cleanup scheduler reference (would be set by external scheduler)
        self._cleanup_callback: Optional[callable] = None

    # =======================================================
    # Reader-Writer Lock Implementation
    # =======================================================

    def _acquire_read(self):
        """Acquire read lock allowing multiple concurrent readers."""
        with self._read_lock:
            self._readers_count += 1
            if self._readers_count == 1:
                # First reader blocks writers
                self._write_lock.acquire()

    def _release_read(self):
        """Release read lock."""
        with self._read_lock:
            self._readers_count -= 1
            if self._readers_count == 0:
                # Last reader unblocks writers
                self._write_lock.release()

    def _acquire_write(self):
        """Acquire write lock (exclusive access)."""
        self._write_lock.acquire()

    def _release_write(self):
        """Release write lock."""
        self._write_lock.release()

    # =======================================================
    # Memory API with EPIC-14E Enhancements
    # =======================================================

    def write(
        self,
        channel: str,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        version: Optional[int] = None
    ) -> bool:
        """
        Write a value to the blackboard with versioning and change detection.

        Args:
            channel: Storage channel (e.g., 'perception', 'execution')
            key: Storage key within channel
            value: Value to store
            ttl: Time to live in seconds (None for permanent)
            version: Expected version for optimistic locking (None to skip check)

        Returns:
            True if write succeeded, False if version conflict
        """
        self._acquire_write()
        try:
            # Initialize channel if needed
            if channel not in self._channels:
                self._channels[channel] = {}

            # Get current value for change detection
            old_versioned = self._channels[channel].get(key)
            old_value = old_versioned.value if old_versioned else None

            # Version checking for optimistic locking
            current_version = old_versioned.version if old_versioned else 0
            if version is not None and version != current_version:
                self._increment_metric('version_conflicts')
                return False  # Version conflict

            # Create new versioned value
            new_version = current_version + 1
            new_versioned = VersionedValue(
                value=value,
                version=new_version,
                timestamp=time.time(),
                ttl=ttl
            )

            # Store the new value
            self._channels[channel][key] = new_versioned

            # Create change event
            change_event = StateChangeEvent(
                channel=channel,
                key=key,
                old_value=old_value,
                new_value=value,
                timestamp=time.time()
            )

            # Add to history (with bounding)
            self._add_to_history(change_event)

            # Notify listeners
            self._notify_listeners(channel, key, change_event)

            # Update context timestamp
            self.context.touch()

            # Update metrics
            self._increment_metric('writes')

            return True
        finally:
            self._release_write()

    def read(
        self,
        channel: str,
        key: str,
        default=None,
        validate_freshness: bool = True,
        max_age: Optional[float] = None
    ) -> Any:
        """
        Read a value from the blackboard with optional freshness validation.

        Args:
            channel: Storage channel
            key: Storage key
            default: Default value if not found
            validate_freshness: Whether to validate against staleness
            max_age: Maximum age in seconds for freshness (None to use TTL)

        Returns:
            The stored value or default if not found/expired/stale
        """
        self._acquire_read()
        try:
            # Clean up expired entries lazily during read
            self._cleanup_expired_lazy()

            channel_dict = self._channels.get(channel, {})
            versioned = channel_dict.get(key)

            if versioned is None:
                self._increment_metric('reads')
                return default

            # Check expiration
            if versioned.is_expired():
                # Clean up expired entry
                del self._channels[channel][key]
                self._increment_metric('expired_cleanups')
                self._increment_metric('reads')
                return default

            # Check freshness if requested
            if validate_freshness:
                age = time.time() - versioned.timestamp
                max_allowed_age = max_age if max_age is not None else (versioned.ttl or float('inf'))
                if age > max_allowed_age:
                    self._increment_metric('reads')
                    return default  # Treat as not found if stale

            self._increment_metric('reads')
            return versioned.value
        finally:
            self._release_read()

    def read_with_version(
        self,
        channel: str,
        key: str
    ) -> Tuple[Any, int, float]:
        """
        Read a value along with its version and timestamp.

        Returns:
            Tuple of (value, version, timestamp) or (None, 0, 0) if not found
        """
        self._acquire_read()
        try:
            channel_dict = self._channels.get(channel, {})
            versioned = channel_dict.get(key)

            if versioned is None or versioned.is_expired():
                return (None, 0, 0)

            return (versioned.value, versioned.version, versioned.timestamp)
        finally:
            self._release_read()

    def channel(
        self,
        channel: str
    ) -> dict[str, Any]:
        """
        Get all key-value pairs in a channel (without versioning).

        Returns:
            Dictionary mapping keys to values
        """
        self._acquire_read()
        try:
            # Clean up expired entries
            self._cleanup_expired_lazy()

            channel_dict = self._channels.get(channel, {})
            result = {}

            for key, versioned in channel_dict.items():
                if not versioned.is_expired():
                    result[key] = versioned.value

            return dict(result)  # Return copy to prevent external modification
        finally:
            self._release_read()

    def update_context(
        self,
        **kwargs
    ):
        """Update the cognitive context with new values."""
        self._acquire_write()
        try:
            self.context.update(**kwargs)
            self.events.publish("context.updated", **kwargs)
        finally:
            self._release_write()

    def context_snapshot(self) -> dict:
        """Get a snapshot of the current context."""
        self._acquire_read()
        try:
            return {
                "timestamp": self.context.timestamp,
                "current_goal": self.context.current_goal,
                "current_activity": self.context.current_activity,
                "current_application": self.context.current_application,
                "current_user_query": self.context.current_user_query,
                "emotional_state": self.context.emotional_state,
                "attention_target": self.context.attention_target,
                "reasoning_state": self.context.reasoning_state,
                "planner_state": self.context.planner_state,
                "execution_state": self.context.execution_state,
                "vision_state": self.context.vision_state,
                "knowledge_state": self.context.knowledge_state,
                "memory_state": self.context.memory_state,
                "metadata": dict(self.context.metadata)
            }
        finally:
            self._release_read()

    def snapshot(self) -> dict:
        """
        Get a complete snapshot of the blackboard state.

        Returns:
            Dictionary representing the entire state
        """
        self._acquire_read()
        try:
            channels_snapshot = {}
            for channel_name, channel_dict in self._channels.items():
                channels_snapshot[channel_name] = {}
                for key, versioned in channel_dict.items():
                    if not versioned.is_expired():
                        channels_snapshot[channel_name][key] = {
                            'value': versioned.value,
                            'version': versioned.version,
                            'timestamp': versioned.timestamp,
                            'ttl': versioned.ttl
                        }

            return {
                "created_at": self.created_at.timestamp(),
                "context": self.context_snapshot(),
                "channels": channels_snapshot,
                "metrics": dict(self._metrics)
            }
        finally:
            self._release_read()

    # =======================================================
    # Idempotency Protection
    # =======================================================

    def record_idempotency(
        self,
        action_id: str,
        task_id: str,
        result: Any = None
    ) -> bool:
        """
        Record an action execution for idempotency protection.

        Args:
            action_id: Unique identifier for the action
            task_id: Identifier for the task/context
            result: Result of the action execution

        Returns:
            True if this is a new execution, False if it was a duplicate
        """
        self._acquire_write()
        try:
            # Clean up expired records
            self._cleanup_expired_idempotency()

            # Create composite key
            composite_key = f"{task_id}:{action_id}"

            # Check if we've seen this before
            if composite_key in self._idempotency_records:
                existing = self._idempotency_records[composite_key]
                if not existing.is_expired(self._idempotency_ttl):
                    self._increment_metric('idempotency_hits')
                    return False  # Duplicate execution

            # If we're at capacity, remove the oldest expired record first,
            # then if still at capacity, remove the oldest record overall
            if len(self._idempotency_records) >= self._max_idempotency_records:
                # First try to remove expired records
                expired_keys = [
                    key for key, record in self._idempotency_records.items()
                    if record.is_expired(self._idempotency_ttl)
                ]

                for key in expired_keys:
                    del self._idempotency_records[key]

                # If still at capacity, remove the oldest record
                if len(self._idempotency_records) >= self._max_idempotency_records:
                    oldest_key = min(self._idempotency_records.keys(),
                                   key=lambda k: self._idempotency_records[k].timestamp)
                    del self._idempotency_records[oldest_key]

            # Record new execution
            self._idempotency_records[composite_key] = IdempotencyRecord(
                action_id=action_id,
                task_id=task_id,
                timestamp=time.time(),
                result=result
            )

            self._increment_metric('idempotency_misses')
            return True  # New execution
        finally:
            self._release_write()

    def get_idempotency_result(
        self,
        action_id: str,
        task_id: str
    ) -> Tuple[bool, Any]:
        """
        Get the recorded result for an idempotent action.

        Returns:
            Tuple of (exists, result) where exists is True if found
        """
        self._acquire_read()
        try:
            self._cleanup_expired_idempotency()

            composite_key = f"{task_id}:{action_id}"
            record = self._idempotency_records.get(composite_key)

            if record is None or record.is_expired(self._idempotency_ttl):
                return (False, None)

            return (True, record.result)
        finally:
            self._release_read()

    # =======================================================
    # Change Notification System
    # =======================================================

    def subscribe_to_channel(
        self,
        channel: str,
        callback: callable
    ):
        """
        Subscribe to changes in a specific channel.

        Args:
            channel: Channel to monitor
            callback: Function to call on changes (channel, key, change_event)
        """
        self._change_listeners[channel].append(callback)

    def subscribe_to_key(
        self,
        channel: str,
        key: str,
        callback: callable
    ):
        """
        Subscribe to changes to a specific key.

        Args:
            channel: Channel containing the key
            key: Specific key to monitor
            callback: Function to call on changes (old_value, new_value, change_event)
        """
        def wrapper(change_event: StateChangeEvent):
            if change_event.channel == channel and change_event.key == key:
                callback(change_event.old_value, change_event.new_value, change_event)

        self._change_listeners[f"{channel}:{key}"].append(wrapper)

    def subscribe_global(
        self,
        callback: callable
    ):
        """
        Subscribe to all changes anywhere in the blackboard.

        Args:
            callback: Function to call on any change (change_event)
        """
        self._global_listeners.append(callback)

    def unsubscribe_from_channel(
        self,
        channel: str,
        callback: callable
    ):
        """Unsubscribe from channel changes."""
        if channel in self._change_listeners:
            try:
                self._change_listeners[channel].remove(callback)
            except ValueError:
                pass

    def unsubscribe_from_key(
        self,
        channel: str,
        key: str,
        callback: callable
    ):
        """Unsubscribe from key changes."""
        listener_key = f"{channel}:{key}"
        if listener_key in self._change_listeners:
            try:
                self._change_listeners[listener_key].remove(callback)
            except ValueError:
                pass

    def unsubscribe_global(
        self,
        callback: callable
    ):
        """Unsubscribe from global changes."""
        try:
            self._global_listeners.remove(callback)
        except ValueError:
            pass

    # =======================================================
    # History and Observability
    # =======================================================

    def get_state_history(
        self,
        channel: Optional[str] = None,
        key: Optional[str] = None,
        limit: int = 100
    ) -> List[StateChangeEvent]:
        """
        Get history of state changes.

        Args:
            channel: Filter by channel (None for all)
            key: Filter by key (None for all)
            limit: Maximum number of events to return

        Returns:
            List of state change events (most recent first)
        """
        self._acquire_read()
        try:
            history = self._state_history

            if channel is not None and key is not None:
                history = [e for e in history if e.channel == channel and e.key == key]
            elif channel is not None:
                history = [e for e in history if e.channel == channel]

            # Return most recent first, limited
            return list(reversed(history[-limit:]))
        finally:
            self._release_read()

    def get_metrics(self) -> dict:
        """Get current metrics collection."""
        self._acquire_read()
        try:
            return dict(self._metrics)
        finally:
            self._release_read()

    # =======================================================
    # Cleanup and Maintenance
    # =======================================================

    def _cleanup_expired_lazy(self):
        """Lazy cleanup of expired entries during read operations."""
        current_time = time.time()
        channels_to_clean = []

        for channel_name, channel_dict in self._channels.items():
            keys_to_delete = []
            for key, versioned in channel_dict.items():
                if versioned.is_expired():
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._channels[channel_name][key]
                self._increment_metric('expired_cleanups')

            # Mark empty channels for deletion
            if not self._channels[channel_name]:
                channels_to_clean.append(channel_name)

        for channel_name in channels_to_clean:
            del self._channels[channel_name]

    def _cleanup_expired_idempotency(self):
        """Clean up expired idempotency records."""
        current_time = time.time()
        keys_to_delete = []

        for key, record in self._idempotency_records.items():
            if record.is_expired(self._idempotency_ttl):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._idempotency_records[key]

    def _add_to_history(self, event: StateChangeEvent):
        """Add a state change event to the bounded history."""
        # Add to main history
        key = f"{event.channel}:{event.key}"
        self._state_history[key].append(event)

        # Bound the history
        if len(self._state_history[key]) > self._max_history_size:
            self._state_history[key] = self._state_history[key][-self._max_history_size:]

        # Also maintain global recent history for quick access
        if not hasattr(self, '_recent_history'):
            self._recent_history = []
        self._recent_history.append(event)
        if len(self._recent_history) > self._max_history_size:
            self._recent_history = self._recent_history[-self._max_history_size:]

    def _notify_listeners(self, channel: str, key: str, event: StateChangeEvent):
        """Notify all relevant listeners of a state change."""
        # Notify channel subscribers
        for callback in self._change_listeners.get(channel, []):
            try:
                callback(channel, key, event)
            except Exception:
                # Don't let listener exceptions break the system
                pass

        # Notify key-specific subscribers
        key_specific = f"{channel}:{key}"
        for callback in self._change_listeners.get(key_specific, []):
            try:
                callback(event)
            except Exception:
                pass

        # Notify global subscribers
        for callback in self._global_listeners:
            try:
                callback(event)
            except Exception:
                pass

    def _increment_metric(self, metric_name: str):
        """Thread-safe increment of a metric."""
        with self._metrics_lock:
            self._metrics[metric_name] = self._metrics.get(metric_name, 0) + 1

    def set_cleanup_callback(self, callback: callable):
        """Set a callback to be called for periodic cleanup."""
        self._cleanup_callback = callback

    # =======================================================
    # Utility Methods
    # =======================================================

    def clear_channel(self, channel: str):
        """Clear all data in a channel."""
        self._acquire_write()
        try:
            if channel in self._channels:
                # Create change events for deletion
                for key, versioned in self._channels[channel].items():
                    if not versioned.is_expired():
                        event = StateChangeEvent(
                            channel=channel,
                            key=key,
                            old_value=versioned.value,
                            new_value=None,
                            timestamp=time.time()
                        )
                        self._add_to_history(event)
                        self._notify_listeners(channel, key, event)

                # Clear the channel
                self._channels[channel].clear()
        finally:
            self._release_write()

    def clear(self):
        """Clear all data in the blackboard."""
        self._acquire_write()
        try:
            # Create change events for all deletions
            for channel_name, channel_dict in self._channels.items():
                for key, versioned in channel_dict.items():
                    if not versioned.is_expired():
                        event = StateChangeEvent(
                            channel=channel_name,
                            key=key,
                            old_value=versioned.value,
                            new_value=None,
                            timestamp=time.time()
                        )
                        self._add_to_history(event)
                        self._notify_listeners(channel_name, key, event)

            # Clear everything
            self._channels.clear()
            self._idempotency_records.clear()
            self._state_history.clear()
            if hasattr(self, '_recent_history'):
                self._recent_history.clear()

            # Reset metrics
            with self._metrics_lock:
                for key in self._metrics:
                    self._metrics[key] = 0

            # Reset context
            self.context = CognitiveContext()
            self.created_at = datetime.utcnow()
        finally:
            self._release_write()

    def channels(self) -> List[str]:
        """Get list of all channels."""
        self._acquire_read()
        try:
            return list(self._channels.keys())
        finally:
            self._release_read()

    def keys_in_channel(self, channel: str) -> List[str]:
        """Get list of all keys in a channel."""
        self._acquire_read()
        try:
            channel_dict = self._channels.get(channel, {})
            # Return only non-expired keys
            return [
                key for key, versioned in channel_dict.items()
                if not versioned.is_expired()
            ]
        finally:
            self._release_read()