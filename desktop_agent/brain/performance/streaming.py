"""Streaming infrastructure for incremental response delivery.

Allows the brain to stream partial results as they become available
rather than waiting for the complete pipeline to finish.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import deque


class StreamPhase(Enum):
    PERCEPTION = "perception"
    CONTEXT = "context"
    DECISION = "decision"
    PLANNING = "planning"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StreamChunk:
    phase: StreamPhase
    data: Any
    timestamp: float
    seq: int
    is_final: bool = False
    error: Optional[str] = None


class StreamProcessor:
    """Process and emit streaming chunks through the pipeline."""

    def __init__(self, max_buffer: int = 500):
        self._buffer: deque[StreamChunk] = deque(maxlen=max_buffer)
        self._listeners: list[Callable[[StreamChunk], None]] = []
        self._seq = 0
        self._lock = threading.Lock()
        self._started_at: float = 0.0

    def start(self):
        with self._lock:
            self._buffer.clear()
            self._seq = 0
            self._started_at = time.perf_counter()

    def emit(self, phase: StreamPhase, data: Any, is_final: bool = False,
             error: Optional[str] = None) -> StreamChunk:
        with self._lock:
            self._seq += 1
            chunk = StreamChunk(
                phase=phase, data=data,
                timestamp=time.perf_counter() - self._started_at,
                seq=self._seq, is_final=is_final, error=error,
            )
            self._buffer.append(chunk)
        for listener in self._listeners:
            try:
                listener(chunk)
            except Exception:
                pass
        return chunk

    def on_chunk(self, callback: Callable[[StreamChunk], None]):
        self._listeners.append(callback)

    def chunks(self) -> list[StreamChunk]:
        with self._lock:
            return list(self._buffer)

    def latest(self) -> Optional[StreamChunk]:
        with self._lock:
            return self._buffer[-1] if self._buffer else None

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._started_at) * 1000 if self._started_at else 0.0

    def clear(self):
        with self._lock:
            self._buffer.clear()
            self._listeners.clear()
