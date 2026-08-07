"""
MYRAA Working Blackboard

Thread-safe shared runtime storage.
"""

from __future__ import annotations

import threading
from datetime import datetime

from .cognitive_context import CognitiveContext


class WorkingBlackboard:

    """
    Runtime shared memory.
    """

    def __init__(self):

        self._lock = threading.RLock()

        self._channels: dict[str, dict] = {}

        self.context = CognitiveContext()

        self.created_at = datetime.utcnow()

    # ------------------------------------------------------

    def write(

        self,

        channel: str,

        key: str,

        value,

    ):

        with self._lock:

            if channel not in self._channels:

                self._channels[channel] = {}

            self._channels[channel][key] = value

    # ------------------------------------------------------

    def read(

        self,

        channel: str,

        key: str,

        default=None,

    ):

        with self._lock:

            return (

                self._channels

                .get(channel, {})

                .get(key, default)

            )

    # ------------------------------------------------------

    def channel(

        self,

        channel: str,

    ):

        with self._lock:

            return dict(

                self._channels.get(

                    channel,

                    {},

                )

            )

    # ------------------------------------------------------

    def update_context(

        self,

        **kwargs,

    ):

        with self._lock:

            self.context.update(

                **kwargs,

            )

    # ------------------------------------------------------

    def clear_channel(

        self,

        channel: str,

    ):

        with self._lock:

            self._channels.pop(

                channel,

                None,

            )

    # ------------------------------------------------------

    def clear(self):

        with self._lock:

            self._channels.clear()

    # ------------------------------------------------------

    def channels(self):

        with self._lock:

            return list(

                self._channels.keys()

            )

    # ------------------------------------------------------

    def snapshot(self):

        with self._lock:

            return {

                "created_at": self.created_at,

                "context": self.context.to_dict(),

                "channels": {

                    name: dict(data)

                    for name, data

                    in self._channels.items()

                },

            }