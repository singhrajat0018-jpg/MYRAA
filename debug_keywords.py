#!/usr/bin/env python3
"""
Debug script to see what keywords are being matched
"""

import sys
import os
import re

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

from desktop_agent.brain.ai.ai_manager import AIManager

def debug_keywords():
    """Debug keyword matching"""

    ai_manager = AIManager()

    test_cases = [
        'can you help me with something',
        'what do you think about this',
        'relationship between diet and health',
        'trends in technology',
        'hello',
        'open notepad',
        'explain how photosynthesis works',
        'how are you doing'
    ]

    for prompt in test_cases:
        print(f"\nTesting: '{prompt}'")
        combined_text = prompt.lower().strip()
        words = set(re.findall(r'\b\w+\b', combined_text))
        complex_matches = len(words.intersection(ai_manager._complex_keywords))
        simple_matches = len(words.intersection(ai_manager._simple_keywords))
        print(f"  Words: {words}")
        print(f"  Complex matches: {complex_matches} - {words.intersection(ai_manager._complex_keywords)}")
        print(f"  Simple matches: {simple_matches} - {words.intersection(ai_manager._simple_keywords)}")

        # Check simple patterns
        user_prompt_lower = prompt.lower().strip()
        pattern_matched = False
        for pattern in ai_manager._compiled_simple_patterns:
            if pattern.match(user_prompt_lower):
                pattern_matched = True
                print(f"  Matched simple pattern: {pattern.pattern}")
                break
        if not pattern_matched:
            print(f"  No simple pattern matched")

        # Check phrases
        deep_planning_matched = False
        for phrase in ai_manager._deep_planning_phrases:
            if re.search(phrase, combined_text):
                deep_planning_matched = True
                print(f"  Matched deep planning phrase: {phrase}")
                break

        complex_phrase_matched = False
        for phrase in ai_manager._complex_phrases:
            if phrase in combined_text:
                complex_phrase_matched = True
                print(f"  Matched complex phrase: {phrase}")
                break

        medium_phrase_matched = False
        for phrase in ai_manager._medium_phrases:
            if phrase in combined_text:
                medium_phrase_matched = True
                print(f"  Matched medium phrase: {phrase}")
                break

if __name__ == "__main__":
    debug_keywords()