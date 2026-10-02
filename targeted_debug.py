#!/usr/bin/env python3
"""
Targeted debug for specific failing cases
"""

import sys
import os
import re

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

from desktop_agent.brain.ai.ai_manager import AIManager

def debug_specific_failures():
    """Debug specific failing test cases"""

    ai_manager = AIManager()

    # Cases that should be simple but are classified as complex
    should_be_simple = [
        ('relationship between diet and health', 'Relationship'),
        ('trends in technology', 'Trends'),
        ('law of diminishing returns', 'Law'),
        ('architecture for scalable web application', 'Architecture'),
        ('structure for organizational hierarchy', 'Structure'),
        ('framework for machine learning pipeline', 'Framework'),
        ('model for financial forecasting', 'Model'),
        ('theory of organizational behavior', 'Theory'),
        ('background of the historical event completely', 'Background'),
        ('optimize the supply chain logistics', 'Optimizing'),
        ('fix the architectural flaw', 'Fixing'),
        ('innovate in the technology space', 'Innovating'),
        ('calculate optimal resource allocation', 'Optimizing'),
        ('compute risk-adjusted returns', 'Computing'),
        ('solve the optimization problem', 'Solving'),
        ('solution for network security', 'Solution'),
    ]

    # Cases that should be complex but are classified as deep_planning
    should_be_complex_but_deep = [
        'design a complete software system',
        'strategies for learning',
        'approaches to problem solving',
        'methods of data analysis',
        'procedure for emergency response',
        'design a complete software system',
        'architecture for scalable web application',
        'structure for organizational hierarchy',
        'framework for machine learning pipeline',
        'model for financial forecasting',
        'theory of organizational behavior',
        'create the marketing campaign strategy',
    ]

    print("=== Cases that should be SIMPLE but are COMPLEX ===")
    for prompt, description in should_be_simple:
        if isinstance(prompt, tuple):
            prompt_text, description = prompt
        else:
            prompt_text = prompt
        hints = ai_manager._determine_complexity_hints("", prompt_text)
        predicted = hints[0] if hints else "unknown"
        print(f"[{'PASS' if predicted == 'simple' else 'FAIL'}] '{prompt_text}' -> {predicted} (expected: simple) [{description}]")

        # Debug details
        combined_text = prompt_text.lower().strip()
        words = set(re.findall(r'\b\w+\b', combined_text))
        complex_matches = len(words.intersection(ai_manager._complex_keywords))
        simple_matches = len(words.intersection(ai_manager._simple_keywords))

        # Check patterns
        pattern_matched = False
        for pattern in ai_manager._compiled_simple_patterns:
            if pattern.match(prompt_text.lower()):
                pattern_matched = True
                break

        print(f"   Words: {sorted(words)}")
        print(f"   Complex matches ({complex_matches}): {sorted(words.intersection(ai_manager._complex_keywords))}")
        print(f"   Simple matches ({simple_matches}): {sorted(words.intersection(ai_manager._simple_keywords))}")
        print(f"   Pattern matched: {pattern_matched}")
        print()

    print("=== Cases that should be COMPLEX but are DEEP_PLANNING ===")
    for prompt in should_be_complex_but_deep:
        hints = ai_manager._determine_complexity_hints("", prompt)
        predicted = hints[0] if hints else "unknown"
        print(f"[{'PASS' if predicted == 'complex' else 'FAIL'}] '{prompt}' -> {predicted} (expected: complex)")

        # Debug details
        combined_text = prompt.lower().strip()
        words = set(re.findall(r'\b\w+\b', combined_text))
        complex_matches = len(words.intersection(ai_manager._complex_keywords))
        simple_matches = len(words.intersection(ai_manager._simple_keywords))

        # Check deep planning phrases
        deep_matched = False
        deep_phrase = ""
        for phrase in ai_manager._deep_planning_phrases:
            if re.search(phrase, combined_text):
                deep_matched = True
                deep_phrase = phrase
                break

        # Check complex phrases
        complex_phrase_matched = False
        complex_phrase = ""
        for phrase in ai_manager._complex_phrases:
            if phrase in combined_text:
                complex_phrase_matched = True
                complex_phrase = phrase
                break

        print(f"   Words: {sorted(words)}")
        print(f"   Complex matches ({complex_matches}): {sorted(words.intersection(ai_manager._complex_keywords))}")
        print(f"   Simple matches ({simple_matches}): {sorted(words.intersection(ai_manager._simple_keywords))}")
        print(f"   Deep planning phrase matched: {deep_matched} ('{deep_phrase}')")
        print(f"   Complex phrase matched: {complex_phrase_matched} ('{complex_phrase}')")
        print()

if __name__ == "__main__":
    debug_specific_failures()