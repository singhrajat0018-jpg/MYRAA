"""Parallel execution framework for independent pipeline stages.

Allows the brain to run independent stages concurrently:
- Memory retrieval + screen analysis in parallel
- Context fusion + tool resolution in parallel
- Multiple tool executions in parallel (with safety gates)
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ExecutionPool(Enum):
    """Pre-configured thread pool sizes."""
    IO_BOUND = 4
    CPU_BOUND = 2
    TOOL_EXECUTION = 3
    MIXED = 4


@dataclass(frozen=True)
class ParallelTask:
    """A task to execute in parallel."""
    name: str
    fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    timeout_ms: float = 5000.0
    priority: int = 0


@dataclass
class ParallelResult:
    """Result of a parallel task execution."""
    name: str
    success: bool
    value: Any = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0


class ParallelExecutor:
    """Execute independent tasks concurrently with timeout and error handling.

    Usage:
        executor = ParallelExecutor()
        tasks = [
            ParallelTask("memory", retrieve_memory, ("query",)),
            ParallelTask("screen", analyze_screen, ("frame",)),
        ]
        results = executor.execute_all(tasks)

    Context manager:
        with ParallelExecutor() as executor:
            results = executor.execute_all(tasks)
        # executor.shutdown(wait=True) called automatically
    """

    _instance: Optional['ParallelExecutor'] = None
    _lock_class = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
                cls._instance._shutdown_called = False
            return cls._instance

    def __init__(self, pool_size: int = ExecutionPool.MIXED.value):
        if self._initialized:
            return
        self._initialized = True
        self._pool_size = pool_size
        self._executor = ThreadPoolExecutor(
            max_workers=pool_size,
            thread_name_prefix="myraa-parallel",
        )
        self._active_futures: dict[str, Future] = {}
        self._lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True, cancel_futures=True)
        return False

    def execute_all(self, tasks: list[ParallelTask],
                    fail_fast: bool = False) -> list[ParallelResult]:
        """Execute all tasks in parallel, wait for completion."""
        if not tasks:
            return []

        futures: dict[str, Future] = {}
        for task in tasks:
            future = self._executor.submit(
                self._run_task, task
            )
            futures[task.name] = future

        results = []
        for task in tasks:
            future = futures[task.name]
            try:
                timeout_s = task.timeout_ms / 1000.0
                result = future.result(timeout=timeout_s)
                results.append(result)
                if fail_fast and not result.success:
                    for remaining_name, remaining_future in futures.items():
                        if remaining_name != task.name:
                            remaining_future.cancel()
                    break
            except Exception as e:
                results.append(ParallelResult(
                    name=task.name,
                    success=False,
                    error=str(e),
                ))
                if fail_fast:
                    for remaining_name, remaining_future in futures.items():
                        if remaining_name != task.name:
                            remaining_future.cancel()
                    break

        return results

    def execute_any(self, tasks: list[ParallelTask]) -> ParallelResult:
        """Execute tasks in parallel, return first success."""
        if not tasks:
            return ParallelResult(name="empty", success=False, error="No tasks")

        futures = {}
        for task in tasks:
            future = self._executor.submit(self._run_task, task)
            futures[task.name] = future

        for task in tasks:
            try:
                timeout_s = task.timeout_ms / 1000.0
                result = futures[task.name].result(timeout=timeout_s)
                if result.success:
                    for name, f in futures.items():
                        if name != task.name:
                            f.cancel()
                    return result
            except Exception:
                continue

        return ParallelResult(name="any", success=False, error="All tasks failed")

    def _run_task(self, task: ParallelTask) -> ParallelResult:
        start = time.perf_counter()
        try:
            value = task.fn(*task.args, **task.kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            return ParallelResult(
                name=task.name, success=True,
                value=value, elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ParallelResult(
                name=task.name, success=False,
                error=str(e), elapsed_ms=elapsed,
            )

    def shutdown(self, wait: bool = True, cancel_futures: bool = False):
        """Idempotent shutdown. Safe to call multiple times."""
        with self._lock_class:
            if self._shutdown_called:
                return
            self._shutdown_called = True
        try:
            self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        except TypeError:
            # Python < 3.9 doesn't support cancel_futures
            self._executor.shutdown(wait=wait)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for f in self._active_futures.values() if not f.done())

    def worker_count(self) -> int:
        return len(self._executor._threads)

    @classmethod
    def singleton(cls) -> 'ParallelExecutor':
        return cls()

    @classmethod
    def reset_singleton(cls):
        with cls._lock_class:
            if cls._instance:
                cls._instance._shutdown_called = True
                try:
                    cls._instance._executor.shutdown(wait=True, cancel_futures=True)
                except TypeError:
                    cls._instance._executor.shutdown(wait=True)
                except Exception:
                    pass
            cls._instance = None
