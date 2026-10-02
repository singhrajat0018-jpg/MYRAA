"""
MYRAA Latency Tracing Utility

Provides decorators and context managers for tracing latency of functions and code blocks
for performance monitoring and optimization.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, Optional
from desktop_agent.brain.metrics import metrics_collector


def trace_latency(metric_name: str):
    """
    Decorator to trace latency of a function.

    Args:
        metric_name: Name of the metric to record latency under

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                metrics_collector.add_to_histogram(metric_name, latency_ms)
        return wrapper
    return decorator


class LatencyContext:
    """
    Context manager for tracing latency of code blocks.

    Usage:
        with LatencyContext("my_operation"):
            # code to trace
            pass
    """

    def __init__(self, metric_name: str):
        self.metric_name = metric_name
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            end_time = time.perf_counter()
            latency_ms = (end_time - self.start_time) * 1000
            metrics_collector.add_to_histogram(self.metric_name, latency_ms)
        return False  # Don't suppress exceptions


def trace_async_latency(metric_name: str):
    """
    Decorator to trace latency of async functions.

    Args:
        metric_name: Name of the metric to record latency under

    Returns:
        Decorated async function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                metrics_collector.add_to_histogram(metric_name, latency_ms)
        return wrapper
    return decorator