#!/usr/bin/env python3
"""
Performance Audit Script for MYRAA EPIC-14G
Measures latency, CPU, RAM, GPU, network usage across components
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

# GPU monitoring - optional
try:
    import GPUtil
    GPU_MONITORING_AVAILABLE = True
except ImportError:
    GPU_MONITORING_AVAILABLE = False

# Import tools at module level to avoid syntax errors in functions
try:
    from desktop_agent.tools_applications import *
    from desktop_agent.tools_browser import *
    from desktop_agent.tools_files import *
    from desktop_agent.tools_system import *
except ImportError:
    # Handle case where tools modules might not be available in test environment
    pass


class PerformanceAuditor:
    def __init__(self):
        self.metrics = {
            'latency': defaultdict(list),
            'cpu': defaultdict(list),
            'memory': defaultdict(list),
            'gpu': defaultdict(list),
            'network': defaultdict(list),
            'queues': defaultdict(list)
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

            # GPU usage (if available)
            if GPU_MONITORING_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    for i, gpu in enumerate(gpus):
                        self.metrics['gpu'][f'gpu_{i}_utilization'].append((timestamp, gpu.load * 100))
                        self.metrics['gpu'][f'gpu_{i}_memory_mb'].append((timestamp, gpu.memoryUsed))
                        self.metrics['gpu'][f'gpu_{i}_temperature'].append((timestamp, gpu.temperature))
                except:
                    pass  # GPU monitoring not available

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
            'gpu_stats': {},
            'network_stats': {}
        }

        # Latency statistics
        for op, latencies in self.metrics['latency'].items():
            if latencies:
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

        # GPU statistics
        for metric, values in self.metrics['gpu'].items():
            if values:
                value_list = [v for _, v in values]
                summary['gpu_stats'][metric] = {
                    'avg': sum(value_list) / len(value_list),
                    'max': max(value_list),
                    'min': min(value_list)
                }

        return summary

    def save_results(self, filepath: str):
        """Save audit results to file"""
        summary = self.get_summary()
        summary['timestamp'] = datetime.now().isoformat()
        summary['raw_metrics'] = {k: dict(v) for k, v in self.metrics.items()}

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)


def audit_desktop_agent_imports():
    """Audit desktop agent module imports"""
    def import_modules():
        # Import key MYRAA modules to measure cold start performance
        # Avoid importing main.py as it triggers full system init with known bugs
        import desktop_agent.registry
        import desktop_agent.brain.ai.ai_manager
        import desktop_agent.brain.brain_engine
        import desktop_agent.tools_pc
        # Tools already imported at module level
        return True

    return import_modules


def audit_brain_components():
    """Audit brain component initialization"""
    def init_brain():
        from desktop_agent.brain.brain_engine import BrainEngine
        from desktop_agent.brain.ai.ai_manager import AIManager
        # We don't instantiate to avoid dependency issues in the audit
        return BrainEngine, AIManager

    return init_brain


def audit_tool_registry():
    """Audit tool registry loading"""
    def load_tools():
        from desktop_agent.registry import TOOLS
        # Tools already imported at module level
        return len(TOOLS)

    return load_tools


def audit_ai_provider_loading():
    """Audit AI provider loading"""
    def load_providers():
        from desktop_agent.brain.ai.providers.ollama_provider import OllamaProvider
        from desktop_agent.brain.ai.ai_manager import AIManager

        ollama = OllamaProvider()
        manager = AIManager()

        return ollama.available()

    return load_providers


def main():
    """Main performance audit function"""
    print("Starting MYRAA Performance Audit for EPIC-14G...")
    print("=" * 60)

    auditor = PerformanceAuditor()

    # Start background monitoring
    auditor.start_monitoring(interval=0.2)

    try:
        # Audit 1: Module imports (cold start)
        print("1. Auditing module imports...")
        _, latency = auditor.measure_latency('desktop_agent_imports', audit_desktop_agent_imports())
        print(f"   Import latency: {latency:.2f} ms")

        # Audit 2: Brain component initialization
        print("2. Auditing brain component initialization...")
        _, latency = auditor.measure_latency('brain_init', audit_brain_components())
        print(f"   Brain init latency: {latency:.2f} ms")

        # Audit 3: Tool registry loading
        print("3. Auditing tool registry...")
        tool_count, latency = auditor.measure_latency('tool_registry_load', audit_tool_registry())
        print(f"   Loaded {tool_count} tools in {latency:.2f} ms")

        # Audit 4: AI provider loading
        print("4. Auditing AI providers...")
        availability, latency = auditor.measure_latency('ai_provider_load', audit_ai_provider_loading())
        print(f"   Provider availability: Ollama={availability}")
        print(f"   Provider load latency: {latency:.2f} ms")

        # Audit 5: Configuration loading
        print("5. Auditing configuration loading...")
        def load_config():
            from desktop_agent.config.settings import (
                TAVILY_API_KEY, OLLAMA_MODEL
            )
            return {
                'tavily_key_set': bool(TAVILY_API_KEY),
                'ollama_model': OLLAMA_MODEL,
            }

        config, latency = auditor.measure_latency('config_load', load_config)
        print(f"   Config loaded: Ollama model: {config['ollama_model']}")
        print(f"   Config latency: {latency:.2f} ms")

        # Let monitoring run for a bit to get baseline readings
        print("6. Collecting baseline system metrics (5 seconds)...")
        time.sleep(5)

    finally:
        # Stop monitoring
        auditor.stop_monitoring()

    # Get and display summary
    print("\n" + "=" * 60)
    print("PERFORMANCE AUDIT SUMMARY")
    print("=" * 60)

    summary = auditor.get_summary()

    print(f"Audit Duration: {summary['audit_duration_seconds']:.2f} seconds")
    print()

    # Latency results
    print("LATENCY METRICS (milliseconds):")
    for op, stats in summary['latency_stats'].items():
        if not op.endswith('_error'):  # Skip error metrics for cleaner display
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

    gpu_stats = summary['gpu_stats']
    if gpu_stats:
        print("  GPU METRICS:")
        for metric, stats in gpu_stats.items():
            if 'utilization' in metric:
                print(f"    {metric}: {stats['avg']:.1f}% (max: {stats['max']:.1f}%)")
            elif 'memory' in metric:
                print(f"    {metric}: {stats['avg']:.0f} MB (max: {stats['max']:.0f} MB)")
            elif 'temperature' in metric:
                print(f"    {metric}: {stats['avg']:.1f}°C (max: {stats['max']:.1f}°C)")
    elif not gpu_stats:
        print("  GPU MONITORING: Not available (no NVIDIA GPU or drivers)")
    print()

    # Save results
    results_file = f"performance_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    auditor.save_results(results_file)
    print(f"Detailed results saved to: {results_file}")

    print("\nPerformance audit completed!")


if __name__ == "__main__":
    main()