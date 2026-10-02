#!/usr/bin/env python3
"""
Focused test for specific cases
"""

import sys
import os

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

from desktop_agent.brain.ai.ai_manager import AIManager

def test_specific_cases():
    """Test specific cases to understand classification"""

    ai_manager = AIManager()

    test_cases = [
        # From medium complexity section
        ("can you help me with something", "General request - MEDIUM"),
        ("what do you think about this", "Opinion request - MEDIUM"),
        ("i need some information", "General request - MEDIUM"),
        ("let's discuss the project", "Discussion - MEDIUM"),
        ("how are you doing", "Conversational - MEDIUM"),
        ("tell me about yourself", "Conversational - MEDIUM"),
        ("what's the weather like", "General inquiry - MEDIUM"),

        # From simple section - these should be simple
        ("hello", "Simple greeting - SIMPLE"),
        ("hi", "Simple greeting - SIMPLE"),
        ("thanks", "Simple thanks - SIMPLE"),
        ("open notepad", "App launch - SIMPLE"),
        ("what time is it", "Time query - SIMPLE"),
        ("what is python", "Simple question - SIMPLE"),  # This was failing

        # From complex section - these should be complex
        ("explain how photosynthesis works", "Explanation request - COMPLEX"),
        ("analyze the pros and cons of renewable energy", "Analysis request - COMPLEX"),
        ("why is the sky blue", "Why question - COMPLEX"),
        ("relationship between diet and health", "Relationship - COMPLEX"),
        ("trends in technology", "Trends - COMPLEX"),

        # Edge cases
        ("strategies for learning", "Strategies - should be COMPLEX or MEDIUM?"),
    ]

    print("Testing specific cases:")
    print("=" * 60)

    for prompt, description in test_cases:
        hints = ai_manager._determine_complexity_hints("", prompt)
        predicted = hints[0] if hints else "unknown"

        # Extract expected from description
        if "- SIMPLE" in description:
            expected = "simple"
        elif "- MEDIUM" in description:
            expected = "medium"
        elif "- COMPLEX" in description:
            expected = "complex"
        else:
            expected = "unknown"

        status = "PASS" if predicted == expected else "FAIL"
        print(f"[{status}] '{prompt}' -> {predicted} (expected: {expected}) [{description}]")

        # Show details for failures or interesting cases
        if predicted != expected or "edge" in description.lower():
            print(f"   Combined text: '{{{prompt}}}'.lower().strip()")
            words = set(re.findall(r'\b\w+\b', prompt.lower()))
            complex_matches = len(words.intersection(ai_manager._complex_keywords))
            simple_matches = len(words.intersection(ai_manager._simple_keywords))
            print(f"   Complex matches: {complex_matches}, Simple matches: {simple_matches}")

            # Check simple patterns
            user_prompt_lower = prompt.lower().strip()
            pattern_matched = False
            for pattern in ai_manager._compiled_simple_patterns:
                if pattern.match(user_prompt_lower):
                    pattern_matched = True
                    print(f"   Matched simple pattern: {pattern.pattern}")
                    break
            if not pattern_matched and "Simple" in description:
                print(f"   No simple pattern matched")
            print()

if __name__ == "__main__":
    import re
    test_specific_cases()