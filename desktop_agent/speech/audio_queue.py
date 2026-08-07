"""
Thread-safe audio queue used by the speech pipeline.
"""

from __future__ import annotations

from queue import Queue
from typing import Optional

from .models import AudioChunk


class AudioQueue:

    def __init__(self) -> None:
        self._queue: Queue[AudioChunk] = Queue()

    def push(self, chunk: AudioChunk) -> None:
        self._queue.put(chunk)

    def pop(self, timeout: Optional[float] = None) -> AudioChunk:
        return self._queue.get(timeout=timeout)

    def clear(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()

    def size(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()