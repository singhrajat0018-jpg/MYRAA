#!/usr/bin/env python3
"""
Simple Performance Audit Script for MYRAA EPIC-14G
Measures basic system performance without full MYRAA initialization
"""

import time
import psutil
import threading
import json
import os
import sys
from datetime import datetime
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional
import subprocess


class SimplePerformanceAuditor:
    def __init__(self):
        self.metrics = {
            'latency': defaultdict(list),
            'cpu': defaultdict(list),
            'memory': defaultdict(list),
            'network': defaultdict(list)
        }
        self.baseline_process = psutil.Process()
        self.start_time = time.time()
        self.monitoring = False
        self.monitor_thread = None

    def start_monitoring(self, interval=0.5):
        """Start background monitoring of system resources"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_resources, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def _monitor_resources(self, interval):
        """Background thread to monitor system resources"""
        while self.monitoring:
            timestamp = time.time()

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.metrics['cpu']['system_percent'].append((timestamp, cpu_percent))

            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics['memory']['system_used_mb'].append((timestamp, memory.used / 1024 / 1024))
            self.metrics['memory']['system_percent'].append((timestamp, memory.percent))

            # Network I/O
            net_io = psutil.net_io_counters()
            self.metrics['network']['bytes_sent'].append((timestamp, net_io.bytes_sent))
            self.metrics['network']['bytes_recv'].append((timestamp, net_io.bytes_recv))
            self.metrics['network']['packets_sent'].append((timestamp, net_io.packets_sent))
            self.metrics['network']['packets_recv'].append((timestamp, net_io.packets_recv))

            time.sleep(interval)

    def measure_latency(self, operation_name: str, func, *args, **kwargs):
        """Measure latency of a function execution"""
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            self.metrics['latency'][operation_name].append(latency_ms)
            return result, latency_ms
        except Exception as e:
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            self.metrics['latency'][f'{operation_name}_error'].append(latency_ms)
            raise e

    def get_summary(self):
        """Get performance summary"""
        summary = {
            'audit_duration_seconds': time.time() - self.start_time,
            'latency_stats': {},
            'cpu_stats': {},
            'memory_stats': {},
            'network_stats': {}
        }

        # Latency statistics
        for op, latencies in self.metrics['latency'].items():
            if latencies and not op.endswith('_error'):  # Skip error metrics for cleaner display
                summary['latency_stats'][op] = {
                    'count': len(latencies),
                    'min_ms': min(latencies),
                    'max_ms': max(latencies),
                    'avg_ms': sum(latencies) / len(latencies),
                    'p50_ms': sorted(latencies)[len(latencies) // 2] if latencies else 0,
                    'p95_ms': sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies) if latencies else 0,
                    'p99_ms': sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) >= 100 else max(latencies) if latencies else 0
                }

        # CPU statistics
        for metric, values in self.metrics['cpu'].items():
            if values:
                value_list = [v for _, v in values]
                summary['cpu_stats'][metric] = {
                    'avg': sum(value_list) / len(value_list),
                    'max': max(value_list),
                    'min': min(value_list)
                }

        # Memory statistics
        for metric, values in self.metrics['memory'].items():
            if values:
                value_list = [v for _, v in values]
                summary['memory_stats'][metric] = {
                    'avg_mb': sum(value_list) / len(value_list),
                    'max_mb': max(value_list),
                    'min_mb': min(value_list)
                }

        return summary

    def save_results(self, filepath: str):
        """Save audit results to file"""
        summary = self.get_summary()
        summary['timestamp'] = datetime.now().isoformat()
        summary['raw_metrics'] = {k: dict(v) for k, v in self.metrics.items()}

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)


def audit_file_operations():
    """Audit file operations performance"""
    def file_ops():
        # Create, write, read, delete a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Performance test data\n" * 100)
            temp_filename = f.name

        # Read the file
        with open(temp_filename, 'r') as f:
            content = f.read()

        # Delete the file
        os.unlink(temp_filename)
        return len(content)

    return file_ops


def audit_process_spawning():
    """Audit process spawning performance"""
    def spawn_process():
        # Simple process spawn
        result = subprocess.run(['echo', 'hello'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0

    return spawn_process


def audit_module_imports():
    """Audit safe module imports (no provider startup)"""
    def import_modules():
        # Import only safe modules that don't trigger full initialization
        import desktop_agent.config.settings
        import desktop_agent.brain.ai.provider
        # Import providers individually to avoid init issues
        try:
            import desktop_agent.brain.ai.providers.ollama_provider
        except ImportError:
            pass
        return True

    return import_modules


def audit_tool_registry_size():
    """Audit tool registry size"""
    def get_tool_count():
        try:
            from desktop_agent.registry import TOOLS
            return len(TOOLS)
        except Exception:
            return 0

    return get_tool_count


def main():
    """Main performance audit function"""
    print("Starting MYRAA Simple Performance Audit for EPIC-14G...")
    print("=" * 60)

    auditor = SimplePerformanceAuditor()

    # Start background monitoring
    auditor.start_monitoring(interval=0.2)

    try:
        # Audit 1: File operations
        print("1. Auditing file operations...")
        _, latency = auditor.measure_latency('file_operations', audit_file_operations())
        print(f"   File ops latency: {latency:.2f} ms")

        # Audit 2: Process spawning
        print("2. Auditing process spawning...")
        _, latency = auditor.measure_latency('process_spawning', audit_process_spawning())
        print(f"   Process spawn latency: {latency:.2f} ms")

        # Audit 3: Safe module imports
        print("3. Auditing safe module imports...")
        _, latency = auditor.measure_latency('safe_module_imports', audit_module_imports())
        print(f"   Safe module import latency: {latency:.2f} ms")

        # Audit 4: Tool registry
        print("4. Auditing tool registry...")
        tool_count, latency = auditor.measure_latency('tool_registry_size', audit_tool_registry_size())
        print(f"   Tool registry size: {tool_count} tools")
        print(f"   Tool registry latency: {latency:.2f} ms")

        # Audit 5: Configuration access
        print("5. Auditing configuration access...")
        def access_config():
            from desktop_agent.config.settings import (
                TAVILY_API_KEY, OLLAMA_MODEL
            )
            return {
                'tavily_key_set': bool(TAVILY_API_KEY),
                'ollama_model': OLLAMA_MODEL,
            }

        config, latency = auditor.measure_latency('config_access', access_config)
        print(f"   Config accessed: Ollama model: {config['ollama_model']}")
        print(f"   Config access latency: {latency:.2f} ms")

        # Let monitoring run for a bit to get baseline readings
        print("6. Collecting baseline system metrics (5 seconds)...")
        time.sleep(5)

    finally:
        # Stop monitoring
        auditor.stop_monitoring()

    # Get and display summary
    print("\n" + "=" * 60)
    print("SIMPLE PERFORMANCE AUDIT SUMMARY")
    print("=" * 60)

    summary = auditor.get_summary()

    print(f"Audit Duration: {summary['audit_duration_seconds']:.2f} seconds")
    print()

    # Latency results
    print("LATENCY METRICS (milliseconds):")
    for op, stats in summary['latency_stats'].items():
        print(f"  {op}:")
        print(f"    Count: {stats['count']}, Avg: {stats['avg_ms']:.2f}ms")
        print(f"    Range: {stats['min_ms']:.2f} - {stats['max_ms']:.2f}ms")
        print(f"    P50: {stats['p50_ms']:.2f}ms, P95: {stats['p95_ms']:.2f}ms, P99: {stats['p99_ms']:.2f}ms")
    print()

    # System resource averages
    print("SYSTEM RESOURCE USAGE (AVERAGES):")
    cpu_stats = summary['cpu_stats']
    if cpu_stats:
        for metric, stats in cpu_stats.items():
            if 'percent' in metric:
                print(f"  CPU {metric}: {stats['avg']:.1f}% (max: {stats['max']:.1f}%)")

    mem_stats = summary['memory_stats']
    if mem_stats:
        for metric, stats in mem_stats.items():
            if '_mb' in metric:
                print(f"  Memory {metric}: {stats['avg_mb']:.0f} MB (max: {stats['max_mb']:.0f} MB)")

    print("\nSimple performance audit completed!")


if __name__ == "__main__":
    main()