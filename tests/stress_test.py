"""
Stress testing framework for MYRAA.

Implements extended duration tests to validate long-term stability,
detect memory leaks, and verify system robustness under sustained load.
"""

import time
import threading
import json
import logging
import os
import sys
import psutil
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict
import traceback

# Add the project root to the Python path so we can import desktop_agent modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Add the tests directory to the Python path so we can import test_utils
sys.path.insert(0, os.path.dirname(__file__))

# Import test utilities
from test_utils import isolate_external_apis, label_safe_live_test, label_mocked_test

logger = logging.getLogger(__name__)


class StressTestStatus(Enum):
    """Status of stress test execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class StressTestConfig:
    """Configuration for a stress test."""
    test_name: str
    duration_minutes: int = 5
    check_interval_seconds: int = 30
    max_memory_mb: float = 500.0
    max_cpu_percent: float = 80.0
    monitor_system_resources: bool = True
    collect_metrics: bool = True
    save_results: bool = True


@dataclass
class StressTestResult:
    """Result of a stress test execution."""
    test_name: str
    status: StressTestStatus
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: float = 0.0

    # Resource metrics
    max_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0
    max_cpu_percent: float = 0.0
    avg_cpu_percent: float = 0.0

    # Test-specific metrics
    iterations_completed: int = 0
    errors_encountered: int = 0
    warnings_encountered: int = 0

    # Detailed metrics collected during test
    metrics: Dict[str, List[Any]] = field(default_factory=lambda: defaultdict(list))

    # Errors and issues encountered
    error_details: List[Dict[str, Any]] = field(default_factory=list)
    warning_details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "test_name": self.test_name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "max_memory_mb": self.max_memory_mb,
            "avg_memory_mb": self.avg_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "avg_cpu_percent": self.avg_cpu_percent,
            "iterations_completed": self.iterations_completed,
            "errors_encountered": self.errors_encountered,
            "warnings_encountered": self.warnings_encountered,
            "metrics": dict(self.metrics),
            "error_details": self.error_details,
            "warning_details": self.warning_details
        }


class StressTestRunner:
    """
    Runs extended duration stress tests to validate system stability
    and detect resource leaks or performance degradations over time.
    """

    def __init__(self, config: StressTestConfig):
        """
        Initialize the stress test runner.

        Args:
            config: Configuration for the stress test
        """
        self.config = config
        self.status = StressTestStatus.PENDING
        self._stop_requested = False
        self._test_thread: Optional[threading.Thread] = None
        self._process = psutil.Process()
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

        # Resource monitoring
        self._memory_samples: List[float] = []
        self._cpu_samples: List[float] = []

        # Results
        self.result = StressTestResult(
            test_name=config.test_name,
            status=StressTestStatus.PENDING,
            start_time=0.0
        )

    def start(self, test_function: Callable[[], Any]):
        """
        Start the stress test.

        Args:
            test_function: Function to execute repeatedly during the test
                         Should return True for success, False for failure
                         Can raise exceptions for unexpected errors
        """
        if self.status == StressTestStatus.RUNNING:
            logger.warning("Stress test is already running")
            return False

        self._stop_requested = False
        self._test_thread = threading.Thread(
            target=self._run_test_loop,
            args=(test_function,),
            daemon=True
        )
        self._test_thread.start()
        return True

    def stop(self):
        """Request the stress test to stop."""
        self._stop_requested = True
        if self._test_thread and self._test_thread.is_alive():
            self._test_thread.join(timeout=5.0)

    def _run_test_loop(self, test_function: Callable[[], Any]):
        """Main test execution loop."""
        try:
            self.status = StressTestStatus.RUNNING
            self._start_time = time.time()
            self.result.start_time = self._start_time
            self.result.status = StressTestStatus.RUNNING

            logger.info(f"{label_safe_live_test()} Starting stress test: {self.config.test_name}")
            logger.info(f"{label_safe_live_test()} Duration: {self.config.duration_minutes} minutes")
            logger.info(f"{label_safe_live_test()} Check interval: {self.config.check_interval_seconds} seconds")

            # Isolate external APIs for safety
            isolate_external_apis()

            end_time = self._start_time + (self.config.duration_minutes * 60)
            next_check_time = self._start_time + self.config.check_interval_seconds

            iteration = 0

            while time.time() < end_time and not self._stop_requested:
                iteration_start = time.time()

                try:
                    # Execute the test function
                    success = test_function()
                    iteration += 1

                    if success:
                        self.result.iterations_completed += 1
                    else:
                        self.result.warnings_encountered += 1
                        self.result.warning_details.append({
                            "iteration": iteration,
                            "timestamp": time.time(),
                            "message": "Test function returned False"
                        })

                except Exception as e:
                    self.result.errors_encountered += 1
                    error_detail = {
                        "iteration": iteration,
                        "timestamp": time.time(),
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    }
                    self.result.error_details.append(error_detail)
                    logger.error(f"Error in stress test iteration {iteration}: {e}")

                # Collect resource metrics
                if self.config.monitor_system_resources:
                    self._collect_resource_metrics()

                # Periodic status check and logging
                if time.time() >= next_check_time:
                    self._log_periodic_status(iteration)
                    next_check_time += self.config.check_interval_seconds

                # Sleep until next iteration (aim for 1 second intervals)
                iteration_duration = time.time() - iteration_start
                sleep_time = max(0, 1.0 - iteration_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # Test completed normally
            self._end_test(success=True)

        except Exception as e:
            logger.error(f"Stress test failed with exception: {e}")
            logger.error(traceback.format_exc())
            self._end_test(success=False)

    def _collect_resource_metrics(self):
        """Collect current system resource metrics."""
        try:
            # Memory usage
            memory_info = self._process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            self._memory_samples.append(memory_mb)

            # CPU usage
            cpu_percent = self._process.cpu_percent()
            self._cpu_samples.append(cpu_percent)

        except Exception as e:
            logger.debug(f"Failed to collect resource metrics: {e}")

    def _log_periodic_status(self, iteration: int):
        """Log periodic status during stress test."""
        elapsed = time.time() - self._start_time
        elapsed_minutes = elapsed / 60
        total_minutes = self.config.duration_minutes
        progress = (elapsed_minutes / total_minutes) * 100

        # Calculate current resource usage
        current_memory = self._memory_samples[-1] if self._memory_samples else 0
        current_cpu = self._cpu_samples[-1] if self._cpu_samples else 0

        # Calculate averages
        avg_memory = sum(self._memory_samples) / len(self._memory_samples) if self._memory_samples else 0
        avg_cpu = sum(self._cpu_samples) / len(self._cpu_samples) if self._cpu_samples else 0

        logger.info(f"{label_safe_live_test()} Stress Test Progress: {progress:.1f}% "
                   f"({elapsed_minutes:.1f}/{total_minutes} min) "
                   f"Iterations: {iteration} "
                   f"Memory: {current_memory:.1f}/{avg_memory:.1f} MB "
                   f"CPU: {current_cpu:.1f}/{avg_cpu:.1f}%")

    def _end_test(self, success: bool):
        """End the stress test and finalize results."""
        self._end_time = time.time()
        self.result.end_time = self._end_time
        self.result.duration_seconds = self._end_time - self._start_time

        if self._stop_requested:
            self.result.status = StressTestStatus.STOPPED
            self.status = StressTestStatus.STOPPED
            logger.info(f"{label_safe_live_test()} Stress test stopped: {self.config.test_name}")
        elif success:
            self.result.status = StressTestStatus.COMPLETED
            self.status = StressTestStatus.COMPLETED
            logger.info(f"{label_safe_live_test()} Stress test completed: {self.config.test_name}")
        else:
            self.result.status = StressTestStatus.FAILED
            self.status = StressTestStatus.FAILED
            logger.error(f"{label_safe_live_test()} Stress test failed: {self.config.test_name}")

        # Finalize resource metrics
        if self._memory_samples:
            self.result.max_memory_mb = max(self._memory_samples)
            self.result.avg_memory_mb = sum(self._memory_samples) / len(self._memory_samples)

        if self._cpu_samples:
            self.result.max_cpu_percent = max(self._cpu_samples)
            self.result.avg_cpu_percent = sum(self._cpu_samples) / len(self._cpu_samples)

        # Check for resource violations
        if self.result.max_memory_mb > self.config.max_memory_mb:
            self.result.warnings_encountered += 1
            self.result.warning_details.append({
                "type": "memory_exceeded",
                "timestamp": time.time(),
                "max_memory_mb": self.result.max_memory_mb,
                "limit_mb": self.config.max_memory_mb
            })
            logger.warning(f"Memory usage exceeded limit: {self.result.max_memory_mb:.1f} MB > {self.config.max_memory_mb} MB")

        if self.result.max_cpu_percent > self.config.max_cpu_percent:
            self.result.warnings_encountered += 1
            self.result.warning_details.append({
                "type": "cpu_exceeded",
                "timestamp": time.time(),
                "max_cpu_percent": self.result.max_cpu_percent,
                "limit_percent": self.config.max_cpu_percent
            })
            logger.warning(f"CPU usage exceeded limit: {self.result.max_cpu_percent:.1f}% > {self.config.max_cpu_percent}%")

        # Save results if requested
        if self.config.save_results:
            self._save_results()

    def _save_results(self):
        """Save stress test results to file."""
        try:
            results_dir = Path(__file__).parent / "stress_test_results"
            results_dir.mkdir(exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{self.config.test_name}_{timestamp}.json"
            filepath = results_dir / filename

            with open(filepath, 'w') as f:
                json.dump(self.result.to_dict(), f, indent=2, default=str)

            logger.info(f"Stress test results saved to: {filepath}")

        except Exception as e:
            logger.error(f"Failed to save stress test results: {e}")

    def get_result(self) -> StressTestResult:
        """Get the current stress test result."""
        return self.result

    def is_running(self) -> bool:
        """Check if the stress test is currently running."""
        return self.status == StressTestStatus.RUNNING


# Predefined stress test scenarios
def create_static_desktop_stress_test(duration_minutes: int = 10) -> StressTestConfig:
    """Create a stress test for static desktop operations."""
    return StressTestConfig(
        test_name="static_desktop_stress",
        duration_minutes=duration_minutes,
        check_interval_seconds=30,
        max_memory_mb=200.0,
        max_cpu_percent=50.0
    )

def create_browser_interaction_stress_test(duration_minutes: int = 15) -> StressTestConfig:
    """Create a stress test for browser interactions."""
    return StressTestConfig(
        test_name="browser_interaction_stress",
        duration_minutes=duration_minutes,
        check_interval_seconds=30,
        max_memory_mb=500.0,
        max_cpu_percent=70.0
    )

def create_memory_leak_test(duration_minutes: int = 20) -> StressTestConfig:
    """Create a stress test specifically designed to detect memory leaks."""
    return StressTestConfig(
        test_name="memory_leak_detection",
        duration_minutes=duration_minutes,
        check_interval_seconds=15,
        max_memory_mb=100.0,  # Very strict limit to catch leaks early
        max_cpu_percent=30.0
    )


def run_stress_test(config: StressTestConfig, test_function: Callable[[], Any]) -> StressTestResult:
    """
    Convenience function to run a stress test.

    Args:
        config: Configuration for the stress test
        test_function: Function to execute repeatedly during the test

    Returns:
        StressTestResult containing the test outcome
    """
    runner = StressTestRunner(config)
    runner.start(test_function)

    # Wait for test to complete
    while runner.is_running():
        time.sleep(1)

    return runner.get_result()


# Example test functions for different scenarios
def example_static_desktop_test() -> bool:
    """Example test function for static desktop operations."""
    try:
        # Import and test basic MYRAA functionality
        from desktop_agent.brain.perception import Perception
        from desktop_agent.brain.blackboard.blackboard import Blackboard

        perception = Perception()
        blackboard = Blackboard()

        # Perform some basic operations
        snapshot = perception.snapshot
        if snapshot is None:
            return False

        # Read from blackboard
        _ = blackboard.read("system", "status", "unknown")

        # Write to blackboard
        blackboard.write("test", "timestamp", time.time())

        return True
    except Exception:
        return False


def example_browser_test() -> bool:
    """Example test function for browser operations."""
    try:
        # Test browser-related functionality
        from desktop_agent.tools_browser import PlaywrightBrowser

        browser = PlaywrightBrowser()
        if browser is None:
            return False

        # Basic browser operations
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("MYRAA Stress Testing Framework")
    print("=" * 40)

    # Run a short static desktop stress test
    config = create_static_desktop_stress_test(duration_minutes=2)
    result = run_stress_test(config, example_static_desktop_test)

    print(f"\nStress Test Results:")
    print(f"Test Name: {result.test_name}")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration_seconds:.1f} seconds")
    print(f"Iterations: {result.iterations_completed}")
    print(f"Errors: {result.errors_encountered}")
    print(f"Warnings: {result.warnings_encountered}")
    if result.max_memory_mb > 0:
        print(f"Max Memory: {result.max_memory_mb:.1f} MB")
        print(f"Avg Memory: {result.avg_memory_mb:.1f} MB")
    if result.max_cpu_percent > 0:
        print(f"Max CPU: {result.max_cpu_percent:.1f}%")
        print(f"Avg CPU: {result.avg_cpu_percent:.1f}%")

    print("\nStress test completed!")