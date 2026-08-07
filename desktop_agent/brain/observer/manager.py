"""
Observer Manager

Responsible for:
- Starting observers
- Polling observers
- Collecting events
- Dispatching events to the Brain
- Graceful shutdown
"""

from __future__ import annotations

import logging
import threading
import time
from queue import Empty, Queue
from typing import Callable

from .event import ObserverEvent
from .registry import ObserverRegistry

logger = logging.getLogger(__name__)


class ObserverManager:

    def __init__(
        self,
        registry: ObserverRegistry,
        event_handler: Callable[[ObserverEvent], None] | None = None,
        poll_interval: float = 5.0,
    ) -> None:

        self.registry = registry
        self.poll_interval = poll_interval
        self.event_handler = event_handler

        self._queue: Queue[ObserverEvent] = Queue()

        self._thread: threading.Thread | None = None
        self._running = False

    # --------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    # --------------------------------------------------

    def start(self) -> None:

        if self._running:
            return

        logger.info("Starting Observer Manager...")

        self._running = True

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="ObserverManager",
        )

        self._thread.start()

    # --------------------------------------------------

    def stop(self) -> None:

        if not self._running:
            return

        logger.info("Stopping Observer Manager...")

        self._running = False

        if self._thread:
            self._thread.join(timeout=5)

    # --------------------------------------------------

    def emit(
        self,
        event: ObserverEvent,
    ) -> None:

        self._queue.put(event)

    # --------------------------------------------------

    def _loop(self) -> None:

        logger.info("Observer loop started.")

        while self._running:

            # -----------------------------
            # Poll all observers
            # -----------------------------

            for observer in self.registry.all():

                try:

                    events = observer.poll()

                    if not events:
                        continue

                    for event in events:
                        self.emit(event)

                except Exception:

                    logger.exception(
                        "Observer '%s' failed.",
                        getattr(observer, "name", observer),
                    )

            # -----------------------------
            # Process event queue
            # -----------------------------

            while True:

                try:

                    event = self._queue.get_nowait()

                except Empty:
                    break

                self._dispatch(event)

            time.sleep(self.poll_interval)

        logger.info("Observer loop stopped.")

    # --------------------------------------------------

    def _dispatch(
        self,
        event: ObserverEvent,
    ) -> None:

        logger.info(
            "[Observer] %s | %s",
            event.source,
            event.title,
        )

        if self.event_handler:

            try:

                self.event_handler(event)

            except Exception as exc:

                logger.exception(
                    "Brain failed to process event '%s': %s",
                    event.title,
                    exc,
                )