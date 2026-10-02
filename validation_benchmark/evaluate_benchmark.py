#!/usr/bin/env python3
"""
Evaluate AI Manager 3.0 against the validation benchmark.
DO NOT modify desktop_agent/brain/ai/ai_manager.py during this evaluation.
"""

import json
import time
import statistics
from typing import Dict, List, Tuple
from collections import defaultdict
from pathlib import Path

# Import the AI Manager (do not modify this import or the underlying code)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from desktop_agent.brain.ai.ai_manager import AIManager, Intent, Domain, ExecutionMode, ReasoningDepth, Freshness, RiskLevel

def load_benchmark(filename: str) -> List[Dict]:
    """Load benchmark dataset"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def convert_string_to_enum(value: str, enum_class) -> any:
    """Convert string to enum value"""
    try:
        return enum_class[value.upper()]
    except KeyError:
        # Try lowercase if uppercase fails
        try:
            return enum_class[value]
        except KeyError:
            # Return first enum value as fallback
            return list(enum_class)[0]

def evaluate_ai_manager(benchmark_data: List[Dict]) -> Dict:
    """Evaluate AI Manager against benchmark data"""
    ai_manager = AIManager()

    # Metrics tracking
    metrics = {
        'total': len(benchmark_data),
        'intent_correct': 0,
        'domain_correct': 0,
        'capability_correct': 0,
        'execution_mode_correct': 0,
        'reasoning_depth_correct': 0,
        'freshness_correct': 0,
        'tools_required_correct': 0,
        'risk_level_correct': 0,
        'language_correct': 0,  # We'll infer from request
        'complexity_correct': 0,  # We'll infer from request
        'response_quality_scores': [],  # Subjective scoring
        'latencies': [],
        'confidence_scores': [],
        'fast_path_used': 0,
        'semantic_path_used': 0,
        'unsafe_routing': 0,  # Routes that should not use fast path but do
        'provider_usage': defaultdict(int),
        'errors': [],
        'details': []  # Store detailed results for analysis
    }

    # For confusion matrices
    intent_confusion = defaultdict(lambda: defaultdict(int))
    domain_confusion = defaultdict(lambda: defaultdict(int))
    capability_confusion = defaultdict(lambda: defaultdict(int))
    execution_mode_confusion = defaultdict(lambda: defaultdict(int))

    print(f"Evaluating {len(benchmark_data)} benchmark items...")

    for i, item in enumerate(benchmark_data):
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(benchmark_data)}")

        try:
            start_time = time.perf_counter()

            # Convert string values back to enums for comparison
            expected_intent = convert_string_to_enum(item['intent'], Intent)
            expected_domain = convert_string_to_enum(item['domain'], Domain)
            expected_execution_mode = convert_string_to_enum(item['execution_mode'], ExecutionMode)
            expected_reasoning_depth = convert_string_to_enum(item['reasoning_depth'], ReasoningDepth)
            expected_freshness = convert_string_to_enum(item['freshness'], Freshness)
            expected_risk_level = convert_string_to_enum(item['risk_level'], RiskLevel)

            # Route the request
            route = ai_manager.route(
                user_prompt=item['request'],
                system_prompt="",  # Empty system prompt for evaluation
                task=None
            )

            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            # Track latency
            metrics['latencies'].append(latency_ms)
            metrics['confidence_scores'].append(route.confidence)

            # Check if fast path was used
            if route.execution_mode in [ExecutionMode.FAST_DETERMINISTIC, ExecutionMode.FAST_MODEL]:
                metrics['fast_path_used'] += 1
                # Check if this was unsafe (should have used semantic path)
                if expected_execution_mode not in [ExecutionMode.FAST_DETERMINISTIC, ExecutionMode.FAST_MODEL]:
                    metrics['unsafe_routing'] += 1
            else:
                metrics['semantic_path_used'] += 1

            # Track provider usage
            if route.provider_preference:
                provider = route.provider_preference[0]
                metrics['provider_usage'][provider] += 1

            # Compare intent
            intent_match = route.intent == expected_intent
            if intent_match:
                metrics['intent_correct'] += 1
            intent_confusion[expected_intent.value][route.intent.value] += 1

            # Compare domain
            domain_match = route.domain == expected_domain
            if domain_match:
                metrics['domain_correct'] += 1
            domain_confusion[expected_domain.value][route.domain.value] += 1

            # Compare execution mode
            exec_match = route.execution_mode == expected_execution_mode
            if exec_match:
                metrics['execution_mode_correct'] += 1
            execution_mode_confusion[expected_execution_mode.value][route.execution_mode.value] += 1

            # Compare reasoning depth
            reasoning_match = route.reasoning_depth == expected_reasoning_depth
            if reasoning_match:
                metrics['reasoning_depth_correct'] += 1

            # Compare freshness
            freshness_match = route.freshness == expected_freshness
            if freshness_match:
                metrics['freshness_correct'] += 1

            # Compare risk level
            risk_match = route.risk_level == expected_risk_level
            if risk_match:
                metrics['risk_level_correct'] += 1

            # Check tools required (boolean match)
            tools_match = route.tool_required == bool(item['tools_required'])
            if tools_match:
                metrics['tools_required_correct'] += 1

            # For language and complexity, we infer from request (simple check)
            # Language: check for Hinglish indicators
            request_lower = item['request'].lower()
            is_hinglish = any(word in request_lower for word in ['kholo', 'banao', 'karo', 'tayyar'])
            expected_hinglish = item['language'] == 'Hinglish'
            language_match = is_hinglish == expected_hinglish
            if language_match:
                metrics['language_correct'] += 1

            # Complexity: simple heuristic based on length and keywords
            is_complex = len(item['request']) > 25 or any(word in request_lower for word in ['explain', 'analyze', 'compare', 'create', 'build', 'research'])
            expected_complex = item['complexity'] == 'complex'
            complexity_match = is_complex == expected_complex
            if complexity_match:
                metrics['complexity_correct'] += 1

            # Subjective response quality (0-1 scale based on confidence and correctness)
            quality_score = route.confidence
            if not (intent_match and domain_match and exec_match):
                quality_score *= 0.5  # Penalty for major mismatches
            metrics['response_quality_scores'].append(quality_score)

            # Store detailed result for failure analysis
            metrics['details'].append({
                'index': i,
                'request': item['request'],
                'expected_intent': expected_intent.value,
                'actual_intent': route.intent.value,
                'intent_correct': intent_match,
                'expected_domain': expected_domain.value,
                'actual_domain': route.domain.value,
                'domain_correct': domain_match,
                'confidence': route.confidence,
                'latency_ms': latency_ms,
                'execution_mode': route.execution_mode.value,
                'expected_execution_mode': expected_execution_mode.value
            })

        except Exception as e:
            metrics['errors'].append({
                'index': i,
                'request': item.get('request', 'unknown'),
                'error': str(e)
            })
            print(f"    Error on item {i}: {e}")

    # Calculate final metrics
    total = metrics['total']
    if total > 0:
        metrics['intent_accuracy'] = metrics['intent_correct'] / total
        metrics['domain_accuracy'] = metrics['domain_correct'] / total
        metrics['execution_mode_accuracy'] = metrics['execution_mode_correct'] / total
        metrics['reasoning_depth_accuracy'] = metrics['reasoning_depth_correct'] / total
        metrics['freshness_accuracy'] = metrics['freshness_correct'] / total
        metrics['risk_level_accuracy'] = metrics['risk_level_correct'] / total
        metrics['tools_required_accuracy'] = metrics['tools_required_correct'] / total
        metrics['language_accuracy'] = metrics['language_correct'] / total
        metrics['complexity_accuracy'] = metrics['complexity_correct'] / total
        metrics['avg_latency'] = statistics.mean(metrics['latencies']) if metrics['latencies'] else 0
        metrics['median_latency'] = statistics.median(metrics['latencies']) if metrics['latencies'] else 0
        metrics['p95_latency'] = statistics.quantiles(metrics['latencies'], n=20)[18] if len(metrics['latencies']) >= 20 else (max(metrics['latencies']) if metrics['latencies'] else 0)
        metrics['p99_latency'] = statistics.quantiles(metrics['latencies'], n=100)[98] if len(metrics['latencies']) >= 100 else (max(metrics['latencies']) if metrics['latencies'] else 0)
        metrics['avg_confidence'] = statistics.mean(metrics['confidence_scores']) if metrics['confidence_scores'] else 0
        metrics['fast_path_precision'] = metrics['fast_path_used'] / total if total > 0 else 0
        metrics['unsafe_routing_rate'] = metrics['unsafe_routing'] / total if total > 0 else 0
        metrics['response_quality_avg'] = statistics.mean(metrics['response_quality_scores']) if metrics['response_quality_scores'] else 0

    # Convert confusion matrices to regular dicts for JSON serialization
    metrics['intent_confusion'] = {k: dict(v) for k, v in intent_confusion.items()}
    metrics['domain_confusion'] = {k: dict(v) for k, v in domain_confusion.items()}
    metrics['execution_mode_confusion'] = {k: dict(v) for k, v in execution_mode_confusion.items()}

    return metrics

def main():
    print("Starting AI Manager 3.0 generalization validation...")

    # Load held-out test set (never used for training/tuning)
    current_dir = Path(__file__).parent
    held_out_data = load_benchmark(current_dir / "held_out.json")
    print(f"Loaded held-out test set: {len(held_out_data)} items")

    # Evaluate
    results = evaluate_ai_manager(held_out_data)

    # Save results
    current_dir = Path(__file__).parent
    with open(current_dir / "evaluation_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "="*50)
    print("EVALUATION RESULTS")
    print("="*50)
    print(f"Total samples: {results['total']}")
    print(f"Intent accuracy: {results.get('intent_accuracy', 0):.3f}")
    print(f"Domain accuracy: {results.get('domain_accuracy', 0):.3f}")
    print(f"Execution mode accuracy: {results.get('execution_mode_accuracy', 0):.3f}")
    print(f"Reasoning depth accuracy: {results.get('reasoning_depth_accuracy', 0):.3f}")
    print(f"Freshness accuracy: {results.get('freshness_accuracy', 0):.3f}")
    print(f"Risk level accuracy: {results.get('risk_level_accuracy', 0):.3f}")
    print(f"Tools required accuracy: {results.get('tools_required_accuracy', 0):.3f}")
    print(f"Language accuracy: {results.get('language_accuracy', 0):.3f}")
    print(f"Complexity accuracy: {results.get('complexity_accuracy', 0):.3f}")
    print(f"Average latency: {results.get('avg_latency', 0):.2f} ms")
    print(f"Median latency: {results.get('median_latency', 0):.2f} ms")
    print(f"P95 latency: {results.get('p95_latency', 0):.2f} ms")
    print(f"P99 latency: {results.get('p99_latency', 0):.2f} ms")
    print(f"Average confidence: {results.get('avg_confidence', 0):.3f}")
    print(f"Fast path usage: {results.get('fast_path_precision', 0):.3f}")
    print(f"Unsafe routing rate: {results.get('unsafe_routing_rate', 0):.3f}")
    print(f"Average response quality: {results.get('response_quality_avg', 0):.3f}")

    if results['errors']:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results['errors'][:5]:  # Show first 5 errors
            print(f"  - {error['request'][:50]}...: {error['error']}")

    # Show top confusion areas
    print("\nTop intent confusions (expected -> actual):")
    intent_conf = results.get('intent_confusion', {})
    for expected, actual_dict in intent_conf.items():
        for actual, count in actual_dict.items():
            if expected != actual and count > 2:
                # Convert numeric IDs back to enum names for readability
                try:
                    expected_name = Intent(int(expected)).name
                    actual_name = Intent(int(actual)).name
                    print(f"  {expected_name} -> {actual_name}: {count}")
                except ValueError:
                    # Fallback to numeric if conversion fails
                    print(f"  {expected} -> {actual}: {count}")

    print("\nEvaluation complete! Results saved to evaluation_results.json")

if __name__ == "__main__":
    main()