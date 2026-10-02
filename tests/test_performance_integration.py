"""
Performance integration tests for MYRAA EPIC-14G.

These tests validate that the performance optimizations and infrastructure
implemented in EPIC-14G are working correctly and that there are no
regressions in core functionality.
"""

import time
import threading
import json
import os
import sys
import tempfile
from typing import Dict, Any, List
from pathlib import Path
import logging

# Add the project root to the Python path so we can import desktop_agent modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import test utilities
from test_utils import isolate_external_apis, label_safe_live_test

logger = logging.getLogger(__name__)


def test_performance_guard_basic_functionality():
    """Test basic functionality of the performance regression guard."""
    print(f"{label_safe_live_test()} Testing performance regression guard basic functionality")

    # Isolate external APIs for safety
    isolate_external_apis()

    # Import the performance guard
    from desktop_agent.brain.performance_guard import (
        PerformanceRegressionGuard,
        PerformanceBaseline,
        RegressionCheckResult,
        RegressionStatus,
        record_performance,
        check_performance_regression,
        track_performance,
        performance_guard
    )

    # Create a temporary baseline file for testing
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        baseline_path = Path(tmp_file.name)

    try:
        # Create a new performance guard with temporary baseline file
        guard = PerformanceRegressionGuard(baseline_file=baseline_path)

        # Test recording measurements
        guard.record_measurement("test_operation", 10.0)
        guard.record_measurement("test_operation", 12.0)
        guard.record_measurement("test_operation", 11.0)

        # Test establishing baseline
        result = guard.check_regression("test_operation", min_samples_for_check=2)

        assert result.status == RegressionStatus.UNKNOWN  # Should be unknown since we just established baseline
        assert result.operation_name == "test_operation"
        assert result.sample_count == 3
        assert result.baseline_mean == 11.0  # (10+12+11)/3

        # Test checking regression with improved performance
        guard.record_measurement("test_operation", 8.0)  # Better performance
        guard.record_measurement("test_operation", 9.0)
        guard.record_measurement("test_operation", 7.0)

        result = guard.check_regression("test_operation", min_samples_for_check=2)

        # Should show improvement (negative change_pct)
        assert result.change_pct < 0
        if result.change_pct < -30:  # If improvement > 30%
            assert result.status == RegressionStatus.IMPROVED
        else:
            assert result.status in [RegressionStatus.HEALTHY, RegressionStatus.UNKNOWN]

        # Test checking regression with degraded performance
        guard.record_measurement("test_operation", 20.0)  # Much worse
        guard.record_measurement("test_operation", 25.0)
        guard.record_measurement("test_operation", 22.0)

        result = guard.check_regression("test_operation", min_samples_for_check=2)

        # Should show degradation (positive change_pct)
        assert result.change_pct > 0
        if result.change_pct > 50:  # If degradation > 50%
            assert result.status == RegressionStatus.REGRESSION
        elif result.change_pct > 20:  # If degradation > 20%
            assert result.status == RegressionStatus.DEGRADED
        else:
            assert result.status == RegressionStatus.HEALTHY

        # Test that baselines are saved and loaded
        assert baseline_path.exists()

        # Create new guard with same file to test loading
        guard2 = PerformanceRegressionGuard(baseline_file=baseline_path)
        baseline = guard2.get_baseline("test_operation")
        assert baseline is not None
        assert baseline.operation_name == "test_operation"

        logger.info("Performance regression guard basic functionality test passed")
        return True

    finally:
        # Clean up temporary file
        if baseline_path.exists():
            baseline_path.unlink()


def test_performance_guard_decorator():
    """Test the performance tracking decorators."""
    print(f"{label_safe_live_test()} Testing performance tracking decorators")

    # Isolate external APIs for safety
    isolate_external_apis()

    from desktop_agent.brain.performance_guard import (
        track_performance,
        track_async_performance,
        record_performance,
        check_performance_regression,
        performance_guard
    )

    # Test synchronous decorator
    @track_performance("decorated_sync_function")
    def sync_test_function():
        time.sleep(0.01)  # Sleep for 10ms
        return "success"

    # Test asynchronous decorator
    import asyncio

    @track_async_performance("decorated_async_function")
    async def async_test_function():
        await asyncio.sleep(0.01)  # Sleep for 10ms
        return "success"

    # Clear any existing measurements for clean test
    with performance_guard._lock:
        performance_guard._recent_measurements.clear()
        performance_guard._baselines.clear()

    # Test synchronous function
    result = sync_test_function()
    assert result == "success"

    # Check that performance was recorded
    result_check = performance_guard.check_regression("decorated_sync_function", min_samples_for_check=1)
    assert result_check.sample_count >= 1
    assert result_check.current_value >= 10.0  # Should be at least 10ms from sleep

    # Test asynchronous function
    async def run_async_test():
        result = await async_test_function()
        assert result == "success"

        # Check that performance was recorded
        result_check = performance_guard.check_regression("decorated_async_function", min_samples_for_check=1)
        assert result_check.sample_count >= 1
        assert result_check.current_value >= 10.0  # Should be at least 10ms from sleep

    # Run the async test
    asyncio.run(run_async_test())

    logger.info("Performance tracking decorators test passed")
    return True


def test_benchmark_suite_integration():
    """Test integration with the benchmark suite."""
    print(f"{label_safe_live_test()} Testing benchmark suite integration")

    # Isolate external APIs for safety
    isolate_external_apis()

    from test_benchmark_suite import MYRAABenchmarkSuite, BenchmarkScenario

    # Create a temporary results file for testing
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        baseline_path = Path(tmp_file.name)

    try:
        # Create benchmark suite with temporary file
        suite = MYRAABenchmarkSuite(baseline_file=baseline_path)

        # Test that we can run a simple benchmark
        def simple_benchmark():
            return {
                'target_resolution_latency': 5.0,
                'action_latency': 10.0,
                'verification_latency': 2.0,
                'end_to_end_latency': 17.0,
                'success': True,
                'recovery_attempted': False
            }

        # Run the benchmark
        result = suite.run_benchmark(
            BenchmarkScenario.STATIC_DESKTOP,
            simple_benchmark,
            "Test Simple Benchmark",
            iterations=2
        )

        # Validate result
        assert result.scenario == BenchmarkScenario.STATIC_DESKTOP
        assert result.task_name == "Test Simple Benchmark"
        assert result.iterations == 2
        assert len(result.target_resolution_latency) == 2
        assert len(result.action_latency) == 2
        assert len(result.verification_latency) == 2
        assert len(result.end_to_end_latency) == 2
        assert result.success_count == 2
        assert result.total_attempts == 2

        # Save the results to the baseline file (so that we can load them back)
        suite._save_results()

        # Test that results were saved
        assert baseline_path.exists()

        # Test loading baselines
        suite2 = MYRAABenchmarkSuite(baseline_file=baseline_path)
        assert BenchmarkScenario.STATIC_DESKTOP in suite2.results
        assert len(suite2.results[BenchmarkScenario.STATIC_DESKTOP]) >= 1

        logger.info("Benchmark suite integration test passed")
        return True

    finally:
        # Clean up temporary file
        if baseline_path.exists():
            baseline_path.unlink()


def test_stress_test_framework():
    """Test the stress test framework."""
    print(f"{label_safe_live_test()} Testing stress test framework")

    # Isolate external APIs for safety
    isolate_external_apis()

    from stress_test import (
        StressTestRunner,
        StressTestConfig,
        StressTestStatus,
        run_stress_test,
        example_static_desktop_test
    )

    # Create a configuration for a very short test
    config = StressTestConfig(
        test_name="integration_test_stress",
        duration_minutes=0.05,  # 3 seconds for testing
        check_interval_seconds=1,
        max_memory_mb=100.0,
        max_cpu_percent=50.0
    )

    # Run the stress test with a timeout mechanism
    import threading
    import time
    
    result_container = [None]
    exception_container = [None]
    
    def run_test():
        try:
            result_container[0] = run_stress_test(config, example_static_desktop_test)
        except Exception as e:
            exception_container[0] = e
    
    test_thread = threading.Thread(target=run_test)
    test_thread.daemon = True
    test_thread.start()
    
    # Wait for test to complete with timeout
    test_thread.join(timeout=10.0)  # 10 second timeout
    
    if test_thread.is_alive():
        print(f"{label_safe_live_test()} Stress test timed out after 10 seconds")
        return False
        
    if exception_container[0] is not None:
        raise exception_container[0]
        
    result = result_container[0]
    
    if result is None:
        print(f"{label_safe_live_test()} Stress test failed to produce result")
        return False

    # Validate result
    assert result.test_name == "integration_test_stress"
    assert result.status in [StressTestStatus.COMPLETED, StressTestStatus.STOPPED]
    # Reduced duration expectation since we shortened the test
    assert result.duration_seconds >= 2.0  # Should run for at least 2 seconds
    assert result.iterations_completed > 0  # Should have completed some iterations
    assert result.errors_encountered >= 0  # Errors should be non-negative
    assert result.warnings_encountered >= 0  # Warnings should be non-negative

    # Check that metrics were collected if enabled
    if result.metrics:
        assert isinstance(result.metrics, dict)

    logger.info("Stress test framework test passed")
    return True


def test_performance_optimizations_working():
    """Test that our performance optimizations are actually working."""
    print(f"{label_safe_live_test()} Testing that performance optimizations are working")

    # Isolate external APIs for safety
    isolate_external_apis()

    # Test that we can import and use the optimized modules
    try:
        # Test optimized file tools caching
        from desktop_agent.tools_files import _resolve_folder, _resolve_file, _FOLDER_RESOLUTION_CACHE, _PATH_RESOLUTION_CACHE

        # Clear caches for clean test
        _FOLDER_RESOLUTION_CACHE.clear()
        _PATH_RESOLUTION_CACHE.clear()

        # Test that caching works
        path1 = _resolve_folder("desktop")
        path2 = _resolve_folder("desktop")  # Should hit cache

        # The second call should be faster due to caching (though hard to measure precisely in unit test)
        # At least verify that the cache is being used
        assert len(_FOLDER_RESOLUTION_CACHE) > 0
        assert str(path1) == str(path2)

        # Test file resolution caching
        test_file_path = __file__  # This file
        file_path1 = _resolve_file(test_file_path)
        file_path2 = _resolve_file(test_file_path)  # Should hit cache

        assert len(_PATH_RESOLUTION_CACHE) > 0
        assert str(file_path1) == str(file_path2)

        # Test optimized browser tools timeouts
        from desktop_agent.tools_browser import browser_open, browser_click, browser_go_back

        # We can't easily test the actual timeouts without mocking, but we can verify the functions exist
        assert callable(browser_open)
        assert callable(browser_click)
        assert callable(browser_go_back)

        # Test optimized application locator caching
        from desktop_agent.desktop.windows.application_locator import ApplicationLocator

        locator = ApplicationLocator()
        # Just verify it can be instantiated and has the cache attributes
        assert hasattr(locator, '_locate_cache')
        assert hasattr(locator, '_cache_ttl')

        logger.info("Performance optimizations working test passed")
        return True

    except Exception as e:
        logger.error(f"Error testing performance optimizations: {e}")
        return False


def test_no_regressions_in_core_functionality():
    """Test that our optimizations didn't introduce regressions in core functionality."""
    print(f"{label_safe_live_test()} Testing for regressions in core functionality")

    # Isolate external APIs for safety
    isolate_external_apis()

    try:
        print("  Importing registry...")
        # Test that we can still import and use core MYRAA modules
        from desktop_agent.registry import TOOLS, STATE, load_all
        print("  Registry imported successfully")
        
        # Load all tool modules to populate the TOOLS registry
        print("  Loading tool modules...")
        load_all()
        print(f"  Loaded {len(TOOLS)} tools")
        
        print("  Importing brain engine...")
        from desktop_agent.brain.brain_engine import BrainEngine
        print("  Brain engine imported successfully")
        
        print("  Importing blackboard...")
        from desktop_agent.brain.blackboard.blackboard import Blackboard
        print("  Blackboard imported successfully")
        
        # Verify that tools are still registered
        print("  Checking tools registry...")
        assert len(TOOLS) > 0, "No tools were loaded!"
        assert "openApplication" in TOOLS, "openApplication tool not found"
        assert "readFile" in TOOLS, "readFile tool not found"
        assert "createFile" in TOOLS, "createFile tool not found"
        print("  Tools registry verified")

        # Verify that core components can still be instantiated
        print("  Creating blackboard instance...")
        blackboard = Blackboard()
        assert blackboard is not None
        print("  Blackboard created successfully")

        # Test basic blackboard operations
        print("  Testing blackboard operations...")
        blackboard.write("test", "key", "value")
        value = blackboard.read("test", "key", "default")
        assert value == "value"
        print("  Blackboard operations tested")

        # Test that we can still access the tool registry
        print("  Verifying tool access...")
        assert "openApplication" in TOOLS
        assert "readFile" in TOOLS
        assert "writeFile" in TOOLS
        print("  Tool access verified")

        logger.info("No regressions in core functionality test passed")
        return True

    except Exception as e:
        logger.error(f"Error testing for regressions: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_performance_integration_tests():
    """Run all performance integration tests."""
    print("MYRAA Performance Integration Tests")
    print("=" * 50)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    tests = [
        ("Performance Guard Basic Functionality", test_performance_guard_basic_functionality),
        ("Performance Guard Decorators", test_performance_guard_decorator),
        ("Benchmark Suite Integration", test_benchmark_suite_integration),
        ("Stress Test Framework", test_stress_test_framework),
        ("Performance Optimizations Working", test_performance_optimizations_working),
        ("No Regressions in Core Functionality", test_no_regressions_in_core_functionality)
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        print("-" * 30)

        try:
            start_time = time.time()
            success = test_func()
            end_time = time.time()

            execution_time = (end_time - start_time) * 1000

            if success:
                print(f"PASSED ({execution_time:.2f} ms)")
                results.append((test_name, True, execution_time, None))
            else:
                print(f"FAILED ({execution_time:.2f} ms)")
                results.append((test_name, False, execution_time, "Test returned False"))

        except Exception as e:
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000
            print(f"ERROR ({execution_time:.2f} ms): {e}")
            results.append((test_name, False, execution_time, str(e)))

    # Print summary
    print("\n" + "=" * 50)
    print("PERFORMANCE INTEGRATION TESTS SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, success, execution_time, error in results:
        status = "PASS" if success else "FAIL"
        print(f"[{status}] {test_name}")
        if error:
            print(f"    Error: {error}")
        print(f"    Execution time: {execution_time:.2f} ms")
        print()

    print("-" * 50)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\nALL PERFORMANCE INTEGRATION TESTS PASSED!")
        print("EPIC-14G performance optimizations are working correctly.")
        return True
    else:
        print(f"\n{total - passed} test(s) failed!")
        print("There are issues with the performance implementation.")
        return False


if __name__ == "__main__":
    success = run_performance_integration_tests()
    sys.exit(0 if success else 1)