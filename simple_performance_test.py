#!/usr/bin/env python3
"""
Simple test to verify performance infrastructure components are working.
"""

import time
import tempfile
import os
import sys
from pathlib import Path

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def test_performance_guard():
    """Test the performance regression guard."""
    print("Testing Performance Regression Guard...")

    # Import the performance guard
    from desktop_agent.brain.performance_guard import (
        PerformanceRegressionGuard,
        record_performance,
        check_performance_regression,
        RegressionStatus
    )

    # Create a temporary baseline file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        baseline_path = Path(tmp_file.name)

    try:
        # Create guard with temporary file
        guard = PerformanceRegressionGuard(baseline_file=baseline_path)

        # Record some measurements
        guard.record_measurement("test_op", 10.0)
        guard.record_measurement("test_op", 12.0)
        guard.record_measurement("test_op", 11.0)

        # Check regression (should establish baseline)
        result = guard.check_regression("test_op", min_samples_for_check=2)
        print(f"  Baseline establishment: {result.status}")
        assert result.status == RegressionStatus.UNKNOWN
        assert result.sample_count == 3

        # Record better performance
        guard.record_measurement("test_op", 8.0)
        guard.record_measurement("test_op", 9.0)

        # Check for improvement
        result = guard.check_regression("test_op", min_samples_for_check=2)
        print(f"  Improvement check: {result.status} ({result.change_pct:.1f}%)")

        # Record worse performance
        guard.record_measurement("test_op", 20.0)
        guard.record_measurement("test_op", 25.0)

        # Check for regression
        result = guard.check_regression("test_op", min_samples_for_check=2)
        print(f"  Regression check: {result.status} ({result.change_pct:.1f}%)")

        # Verify file was created
        assert baseline_path.exists()
        print("  Baseline file created successfully")

        return True

    finally:
        # Clean up
        if baseline_path.exists():
            baseline_path.unlink()

def test_latency_tracing():
    """Test latency tracing functionality."""
    print("\nTesting Latency Tracing...")

    from desktop_agent.brain.latency_tracing import trace_latency, LatencyContext
    from desktop_agent.brain.metrics import metrics_collector

    # Test decorator
    @trace_latency("test_decorator")
    def test_function():
        time.sleep(0.01)  # 10ms
        return "done"

    result = test_function()
    assert result == "done"

    # Test context manager
    with LatencyContext("test_context"):
        time.sleep(0.01)  # 10ms

    print("  Latency tracing components working")
    return True

def test_metrics_collection():
    """Test that metrics collection is working."""
    print("\nTesting Metrics Collection...")

    from desktop_agent.brain.metrics import metrics_collector, record_action_latency

    # Test recording a metric
    record_action_latency("test_action", 0.05)  # 50ms

    # Get metrics
    metrics = metrics_collector.get_all_metrics()
    histograms = metrics.get("histograms", {})

    # Check if our metric is there
    assert "action_latency_test_action" in histograms
    print("  Metrics collection working")
    return True

def main():
    """Run all simple tests."""
    print("Simple Performance Infrastructure Tests")
    print("=" * 40)

    try:
        test_performance_guard()
        test_latency_tracing()
        test_metrics_collection()

        print("\n" + "=" * 40)
        print("All tests passed! [PASS]")
        print("Performance infrastructure is working correctly.")
        return True

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)