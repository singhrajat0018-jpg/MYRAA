"""
MYRAA Event Bus

Thread-safe Publish / Subscribe event bus.

No module should directly communicate
with another module.

Everything passes through EventBus.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .subscriptions import Subscriptions

logger = logging.getLogger(__name__)


# ============================================================
# Event
# ============================================================

@dataclass(slots=True)
class BlackboardEvent:

    name: str

    timestamp: datetime = field(
        default_factory=datetime.utcnow,
    )

    payload: dict[str, Any] = field(
        default_factory=dict,
    )


# ============================================================
# Event Bus
# ============================================================

class EventBus:

    """
    Thread-safe publish/subscribe system.
    """

    def __init__(self):

        self._lock = threading.RLock()

        self._subscriptions = Subscriptions()

    # ------------------------------------------------------

    def subscribe(

        self,

        event: str,

        callback,

    ):

        with self._lock:

            self._subscriptions.subscribe(

                event,

                callback,

            )

    # ------------------------------------------------------

    def unsubscribe(

        self,

        event: str,

        callback,

    ):

        with self._lock:

            self._subscriptions.unsubscribe(

                event,

                callback,

            )

    # ------------------------------------------------------

    def publish(

        self,

        event: str,

        **payload,

    ) -> BlackboardEvent:

        evt = BlackboardEvent(

            name=event,

            payload=payload,

        )

        listeners = self._subscriptions.listeners(

            event,

        )

        for callback in listeners:

            try:

                callback(evt)

            except Exception:

                logger.exception(

                    "EventBus callback failed (%s)",

                    event,

                )

        return evt

    # ------------------------------------------------------

    def emit(

        self,

        event: BlackboardEvent,

    ) -> BlackboardEvent:

        listeners = self._subscriptions.listeners(

            event.name,

        )

        for callback in listeners:

            try:

                callback(event)

            except Exception:

                logger.exception(

                    "EventBus callback failed (%s)",

                    event.name,

                )

        return event

    # ------------------------------------------------------

    def listener_count(

        self,

        event: str | None = None,

    ) -> int:

        if event is None:

            return self._subscriptions.count()

        return len(

            self._subscriptions.listeners(

                event,

            )

        )

    # ------------------------------------------------------

    def clear(self):

        with self._lock:

            self._subscriptions.clear()