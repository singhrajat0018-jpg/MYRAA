"""
Long-running soak test procedures for MYRAA.

These tests are designed to run for extended periods to monitor
system stability, resource usage, and detect memory leaks or
performance degradation over time.
"""

import os
import sys
import time
import threading
import psutil
import gc
from typing import Dict, List, Any
import logging

# Add the project root to the Python path so we can import desktop_agent modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import test utilities
from test_utils import isolate_external_apis, label_safe_live_test, label_mocked_test

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitor system resources during soak tests."""

    def __init__(self, sample_interval: float = 5.0):
        self.sample_interval = sample_interval
        self.monitoring = False
        self.monitor_thread = None
        self.metrics = {
            'memory_mb': [],
            'cpu_percent': [],
            'thread_count': [],
            'open_files': [],
            'timestamp': []
        }
        self.process = psutil.Process()

    def start(self):
        """Start monitoring in a background thread."""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("System monitoring started")

    def stop(self):
        """Stop monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info("System monitoring stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                # Collect metrics
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024

                cpu_percent = self.process.cpu_percent()
                thread_count = self.process.num_threads()

                try:
                    open_files = len(self.process.open_files())
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    open_files = 0

                # Store metrics
                self.metrics['memory_mb'].append(memory_mb)
                self.metrics['cpu_percent'].append(cpu_percent)
                self.metrics['thread_count'].append(thread_count)
                self.metrics['open_files'].append(open_files)
                self.metrics['timestamp'].append(time.time())

                # Log periodically
                if len(self.metrics['timestamp']) % 12 == 0:  # Every minute if sampling every 5s
                    logger.info(
                        f"Soak test metrics - Memory: {memory_mb:.1f} MB, "
                        f"CPU: {cpu_percent:.1f}%, Threads: {thread_count}, "
                        f"Open files: {open_files}"
                    )

            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")

            time.sleep(self.sample_interval)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of collected metrics."""
        if not self.metrics['timestamp']:
            return {}

        return {
            'duration_seconds': self.metrics['timestamp'][-1] - self.metrics['timestamp'][0],
            'sample_count': len(self.metrics['timestamp']),
            'memory_mb': {
                'min': min(self.metrics['memory_mb']),
                'max': max(self.metrics['memory_mb']),
                'avg': sum(self.metrics['memory_mb']) / len(self.metrics['memory_mb']),
                'final': self.metrics['memory_mb'][-1],
                'growth_mb': self.metrics['memory_mb'][-1] - self.metrics['memory_mb'][0]
            },
            'cpu_percent': {
                'min': min(self.metrics['cpu_percent']),
                'max': max(self.metrics['cpu_percent']),
                'avg': sum(self.metrics['cpu_percent']) / len(self.metrics['cpu_percent'])
            },
            'thread_count': {
                'min': min(self.metrics['thread_count']),
                'max': max(self.metrics['thread_count']),
                'avg': sum(self.metrics['thread_count']) / len(self.metrics['thread_count']),
                'final': self.metrics['thread_count'][-1]
            },
            'open_files': {
                'min': min(self.metrics['open_files']),
                'max': max(self.metrics['open_files']),
                'avg': sum(self.metrics['open_files']) / len(self.metrics['open_files']),
                'final': self.metrics['open_files'][-1]
            }
        }


def run_perception_soak_test(duration_minutes: int = 10):
    """
    Run a perception pipeline soak test.

    Args:
        duration_minutes: How long to run the test (default 10 minutes)
    """
    print(f"{label_safe_live_test()} Starting perception soak test for {duration_minutes} minutes")

    # Isolate external APIs for safety
    isolate_external_apis()

    # Start system monitoring
    monitor = SystemMonitor(sample_interval=5.0)
    monitor.start()

    try:
        # Import perception components
        from desktop_agent.brain.perception import Perception

        # Initialize perception system
        perception = Perception()

        end_time = time.time() + (duration_minutes * 60)
        iteration = 0

        logger.info(f"Perception soak test will run until {time.ctime(end_time)}")

        while time.time() < end_time:
            iteration += 1
            iteration_start = time.time()

            try:
                # Perform perception cycle - get the current snapshot
                snapshot = perception.snapshot
                # Access some properties to exercise the perception system
                _ = perception.ready
                _ = perception.application
                _ = perception.window
                _ = perception.confidence

                # Force garbage collection periodically to check for leaks
                if iteration % 60 == 0:  # Every 5 minutes if sampling every 5s
                    gc.collect()
                    logger.info(f"Perception soak test iteration {iteration}")

            except Exception as e:
                logger.error(f"Error in perception soak test iteration {iteration}: {e}")

            # Calculate sleep time to maintain approximately 5-second intervals
            iteration_time = time.time() - iteration_start
            sleep_time = max(0, 5.0 - iteration_time)
            time.sleep(sleep_time)

    finally:
        monitor.stop()

    # Get and display summary
    summary = monitor.get_summary()
    print(f"\n{label_safe_live_test()} Perception soak test completed")
    print(f"Duration: {summary.get('duration_seconds', 0):.1f} seconds")
    print(f"Memory growth: {summary.get('memory_mb', {}).get('growth_mb', 0):.1f} MB")
    print(f"Average CPU: {summary.get('cpu_percent', {}).get('avg', 0):.1f}%")
    print(f"Final thread count: {summary.get('thread_count', {}).get('final', 0)}")

    # Check for concerning trends
    memory_growth = summary.get('memory_mb', {}).get('growth_mb', 0)
    if memory_growth > 50:  # More than 50MB growth is concerning
        print(f"⚠️  WARNING: Significant memory growth detected: {memory_growth:.1f} MB")
    else:
        print(f"✅ Memory growth within acceptable limits: {memory_growth:.1f} MB")

    return summary


def run_browser_soak_test(duration_minutes: int = 10):
    """
    Run a browser automation soak test.

    Args:
        duration_minutes: How long to run the test (default 10 minutes)
    """
    print(f"{label_safe_live_test()} Starting browser soak test for {duration_minutes} minutes")

    # Isolate external APIs for safety
    isolate_external_apis()

    # Start system monitoring
    monitor = SystemMonitor(sample_interval=5.0)
    monitor.start()

    try:
        # Import browser components
        from desktop_agent.tools_browser import PlaywrightBrowser

        browser = PlaywrightBrowser()

        end_time = time.time() + (duration_minutes * 60)
        iteration = 0

        logger.info(f"Browser soak test will run until {time.ctime(end_time)}")

        while time.time() < end_time:
            iteration += 1
            iteration_start = time.time()

            try:
                # Perform browser operations
                # In a real implementation, this would involve:
                # 1. Navigate to a test page
                # 2. Perform some actions
                # 3. Check state
                # 4. Clean up

                # For demonstration, we'll just check if browser is initialized
                if hasattr(browser, 'is_initialized') and browser.is_initialized:
                    pass  # Browser is ready

                # Force garbage collection periodically
                if iteration % 60 == 0:  # Every 5 minutes if sampling every 5s
                    gc.collect()
                    logger.info(f"Browser soak test iteration {iteration}")

            except Exception as e:
                logger.error(f"Error in browser soak test iteration {iteration}: {e}")

            # Calculate sleep time to maintain approximately 5-second intervals
            iteration_time = time.time() - iteration_start
            sleep_time = max(0, 5.0 - iteration_time)
            time.sleep(sleep_time)

    finally:
        monitor.stop()

    # Get and display summary
    summary = monitor.get_summary()
    print(f"\n{label_safe_live_test()} Browser soak test completed")
    print(f"Duration: {summary.get('duration_seconds', 0):.1f} seconds")
    print(f"Memory growth: {summary.get('memory_mb', {}).get('growth_mb', 0):.1f} MB")
    print(f"Average CPU: {summary.get('cpu_percent', {}).get('avg', 0):.1f}%")
    print(f"Final thread count: {summary.get('thread_count', {}).get('final', 0)}")

    # Check for concerning trends
    memory_growth = summary.get('memory_mb', {}).get('growth_mb', 0)
    if memory_growth > 100:  # Browser tests can use more memory
        print(f"⚠️  WARNING: Significant memory growth detected: {memory_growth:.1f} MB")
    else:
        print(f"✅ Memory growth within acceptable limits: {memory_growth:.1f} MB")

    return summary


def run_full_system_soak_test(duration_minutes: int = 5):
    """
    Run a full system soak test exercising multiple components.

    Args:
        duration_minutes: How long to run the test (default 5 minutes for full system)
    """
    print(f"{label_safe_live_test()} Starting full system soak test for {duration_minutes} minutes")

    # Isolate external APIs for safety
    isolate_external_apis()

    # Start system monitoring
    monitor = SystemMonitor(sample_interval=5.0)
    monitor.start()

    try:
        # Import various components to exercise
        from desktop_agent.perception import Perception
        from desktop_agent.brain.working_memory import WorkingMemory
        from desktop_agent.brain.blackboard.blackboard import Blackboard

        perception = Perception()
        working_memory = WorkingMemory()
        blackboard = Blackboard()

        end_time = time.time() + (duration_minutes * 60)
        iteration = 0

        logger.info(f"Full system soak test will run until {time.ctime(end_time)}")

        while time.time() < end_time:
            iteration += 1
            iteration_start = time.time()

            try:
                # Exercise perception
                if hasattr(perception, 'get_screen_state'):
                    perception.get_screen_state()

                # Exercise working memory
                working_memory.store(f"test_key_{iteration}", f"test_value_{iteration}")
                if iteration % 10 == 0:
                    working_memory.recent_items()

                # Exercise blackboard
                blackboard.set(f"test_key_{iteration}", f"test_value_{iteration}")
                if iteration % 10 == 0:
                    blackboard.get(f"test_key_{iteration-10}" if iteration >= 10 else "test_key_0")

                # Force garbage collection periodically
                if iteration % 30 == 0:  # Every 2.5 minutes if sampling every 5s
                    gc.collect()
                    logger.info(f"Full system soak test iteration {iteration}")

            except Exception as e:
                logger.error(f"Error in full system soak test iteration {iteration}: {e}")

            # Calculate sleep time to maintain approximately 5-second intervals
            iteration_time = time.time() - iteration_start
            sleep_time = max(0, 5.0 - iteration_time)
            time.sleep(sleep_time)

    finally:
        monitor.stop()

    # Get and display summary
    summary = monitor.get_summary()
    print(f"\n{label_safe_live_test()} Full system soak test completed")
    print(f"Duration: {summary.get('duration_seconds', 0):.1f} seconds")
    print(f"Memory growth: {summary.get('memory_mb', {}).get('growth_mb', 0):.1f} MB")
    print(f"Average CPU: {summary.get('cpu_percent', {}).get('avg', 0):.1f}%")
    print(f"Final thread count: {summary.get('thread_count', {}).get('final', 0)}")

    # Check for concerning trends
    memory_growth = summary.get('memory_mb', {}).get('growth_mb', 0)
    if memory_growth > 30:  # Full system test should be efficient
        print(f"⚠️  WARNING: Significant memory growth detected: {memory_growth:.1f} MB")
    else:
        print(f"✅ Memory growth within acceptable limits: {memory_growth:.1f} MB")

    return summary


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("MYRAA Long-Running Soak Test Procedures")
    print("=" * 50)

    # Run a short perception test as demonstration
    try:
        summary = run_perception_soak_test(duration_minutes=2)  # 2 minutes for demo
        print("\nSoak test finished successfully!")
    except KeyboardInterrupt:
        print("\nSoak test interrupted by user")
    except Exception as e:
        print(f"\nSoak test failed with error: {e}")
        import traceback
        traceback.print_exc()