"""Notification and follow-up engine for proactive user engagement."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional
from collections import deque


class NotificationType(Enum):
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    FOLLOW_UP = "follow_up"
    ALERT = "alert"
    SUGGESTION = "suggestion"
    DEGRADED_WARNING = "degraded_warning"
    MONITORING = "monitoring"
    REMINDER = "reminder"
    SYSTEM = "system"


class NotificationPriority(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    URGENT = 3


@dataclass
class Notification:
    notification_id: str
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    timestamp: float
    source: str = ""
    action_label: str = ""
    action_data: dict = field(default_factory=dict)
    read: bool = False
    dismissed: bool = False
    auto_dismiss_ms: Optional[float] = None

    @property
    def age_ms(self) -> float:
        return (time.time() - self.timestamp) * 1000

    def to_dict(self) -> dict:
        return {
            "id": self.notification_id,
            "type": self.notification_type.value,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "source": self.source,
            "action_label": self.action_label,
            "read": self.read,
        }


class NotificationEngine:
    """Manage notifications with callbacks, history, and auto-dismiss."""

    _instance: Optional['NotificationEngine'] = None
    _lock_class = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, max_notifications: int = 500):
        if self._initialized:
            return
        self._initialized = True
        self._max = max_notifications
        self._notifications: deque[Notification] = deque(maxlen=max_notifications)
        self._callbacks: list[Callable[[Notification], None]] = []
        self._lock = threading.Lock()
        self._counter = 0

    def notify(self, ntype: NotificationType, title: str, message: str,
               priority: NotificationPriority = NotificationPriority.MEDIUM,
               source: str = "", action_label: str = "",
               action_data: Optional[dict] = None,
               auto_dismiss_ms: Optional[float] = None) -> Notification:
        with self._lock:
            self._counter += 1
            n = Notification(
                notification_id=f"n_{self._counter}",
                notification_type=ntype, title=title, message=message,
                priority=priority, timestamp=time.time(),
                source=source, action_label=action_label,
                action_data=action_data or {},
                auto_dismiss_ms=auto_dismiss_ms,
            )
            self._notifications.append(n)
        for cb in self._callbacks:
            try:
                cb(n)
            except Exception:
                pass
        return n

    def task_complete(self, task_name: str, result: str = "",
                      source: str = "") -> Notification:
        return self.notify(
            NotificationType.TASK_COMPLETE,
            title=f"Task Complete: {task_name}",
            message=result or f"{task_name} completed successfully.",
            priority=NotificationPriority.LOW, source=source,
        )

    def task_failed(self, task_name: str, error: str = "",
                    source: str = "") -> Notification:
        return self.notify(
            NotificationType.TASK_FAILED,
            title=f"Task Failed: {task_name}",
            message=error or f"{task_name} failed.",
            priority=NotificationPriority.HIGH, source=source,
        )

    def follow_up(self, question: str, context: str = "",
                  action_label: str = "Respond") -> Notification:
        return self.notify(
            NotificationType.FOLLOW_UP,
            title="Follow-up Question", message=question,
            priority=NotificationPriority.MEDIUM, action_label=action_label,
        )

    def suggestion(self, text: str, action_label: str = "") -> Notification:
        return self.notify(
            NotificationType.SUGGESTION,
            title="Suggestion", message=text,
            priority=NotificationPriority.LOW, action_label=action_label,
        )

    def degraded_warning(self, message: str) -> Notification:
        return self.notify(
            NotificationType.DEGRADED_WARNING,
            title="System Degraded", message=message,
            priority=NotificationPriority.HIGH,
        )

    def reminder(self, text: str, action_label: str = "") -> Notification:
        return self.notify(
            NotificationType.REMINDER,
            title="Reminder", message=text,
            priority=NotificationPriority.MEDIUM, action_label=action_label,
        )

    def on_notification(self, callback: Callable[[Notification], None]):
        self._callbacks.append(callback)

    def mark_read(self, notification_id: str) -> bool:
        with self._lock:
            for n in self._notifications:
                if n.notification_id == notification_id:
                    n.read = True
                    return True
            return False

    def dismiss(self, notification_id: str) -> bool:
        with self._lock:
            for n in self._notifications:
                if n.notification_id == notification_id:
                    n.dismissed = True
                    return True
            return False

    def unread(self) -> list[Notification]:
        with self._lock:
            return [n for n in self._notifications if not n.read and not n.dismissed]

    def recent(self, n: int = 10) -> list[Notification]:
        with self._lock:
            return list(self._notifications)[-n:]

    def by_type(self, ntype: NotificationType) -> list[Notification]:
        with self._lock:
            return [n for n in self._notifications if n.notification_type == ntype]

    def auto_dismiss_expired(self) -> list[str]:
        dismissed_ids = []
        with self._lock:
            for n in self._notifications:
                if (n.auto_dismiss_ms and not n.dismissed and
                        n.age_ms > n.auto_dismiss_ms):
                    n.dismissed = True
                    dismissed_ids.append(n.notification_id)
        return dismissed_ids

    def clear(self):
        with self._lock:
            self._notifications.clear()

    def stats(self) -> dict:
        with self._lock:
            total = len(self._notifications)
            unread = sum(1 for n in self._notifications if not n.read and not n.dismissed)
            by_type = {}
            for n in self._notifications:
                t = n.notification_type.value
                by_type[t] = by_type.get(t, 0) + 1
            return {"total": total, "unread": unread, "by_type": by_type}

    @classmethod
    def singleton(cls) -> 'NotificationEngine':
        return cls()

    @classmethod
    def reset_singleton(cls):
        with cls._lock_class:
            cls._instance = None
