#!/usr/bin/env python3
"""
Test script for AI Manager 3.0 semantic routing implementation
"""

import sys
import os

# Add the desktop_agent to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

from desktop_agent.brain.ai.ai_manager import AIManager

def test_ai_manager_3():
    """Test the AI Manager 3.0 implementation"""
    print("Testing AI Manager 3.0 Semantic Routing...")

    # Initialize AI Manager
    ai_manager = AIManager()

    # Test cases
    test_cases = [
        # Simple greetings - should use fast path
        ("hello", "greeting", "should be fast deterministic"),
        ("hi there", "greeting", "should be fast deterministic"),
        ("thanks", "thanks", "should be fast deterministic"),

        # Simple commands - should use fast model
        ("open notepad", "app_control", "should be fast model"),
        ("close chrome", "app_control", "should be fast model"),
        ("volume 50", "audio_control", "should be fast model"),

        # Time queries - should use fast deterministic with real-time freshness
        ("what time is it", "time_query", "should be fast deterministic with real-time"),
        ("current time", "time_query", "should be fast deterministic with real-time"),

        # Simple questions - should use fast model
        ("what is python", "simple_question", "should be fast model"),
        ("who is einstein", "simple_question", "should be fast model"),

        # Explanation requests - should use deep reasoning
        ("explain how photosynthesis works", "explanation", "should be deep reasoning"),
        ("explain the theory of relativity", "explanation", "should be deep reasoning"),

        # Analysis requests - should use deep reasoning
        ("analyze the pros and cons of renewable energy", "analysis", "should be deep reasoning"),
        ("compare machine learning algorithms", "comparison", "should be deep reasoning"),

        # Strategy requests - should use deep reasoning
        ("strategies for learning programming", "strategies", "should be deep reasoning"),
        ("approaches to problem solving", "approaches", "should be deep reasoning"),

        # Why questions - should use deep reasoning
        ("why is the sky blue", "why_question", "should be deep reasoning"),
        ("why do we need sleep", "why_question", "should be deep reasoning"),

        # Calculation requests - should use fast model (general domain)
        ("calculate 2+2", "calculation", "should be fast model"),
        ("solve x^2 + 5x + 6 = 0", "equation", "should be fast model"),
        ("what is the formula for area of circle", "formula", "should be fast model"),

        # Relationship queries - should use fast model (after fix)
        ("relationship between diet and health", "relationship", "should be fast model"),
        ("correlation between exercise and mood", "relationship", "should be fast model"),

        # Architecture/framework queries - should NOT be caught by fast path greetings
        ("software architecture patterns", "architecture", "should NOT be fast deterministic greeting"),
        ("machine learning framework comparison", "framework", "should NOT be fast deterministic greeting"),
        ("explain the theory of relativity", "explanation", "should NOT be fast deterministic greeting"),

        # Trading queries - should use trading engine
        ("analyze nifty trend", "trading_analysis", "should use trading engine"),
        ("should I buy reliance stock", "trading_decision", "should use trading engine"),
        ("monitor market volatility", "trading_monitoring", "should use trading engine"),

        # Coding queries - should use coding engine
        ("debug this python code", "coding_debug", "should use coding engine"),
        ("create a website with html and css", "coding_build", "should use coding engine"),

        # Creation queries - should use creation engine
        ("create a presentation about ai", "creation_document", "should use creation engine"),
        ("make a document for project proposal", "creation_document", "should use creation engine"),

        # Research queries - should use research pipeline
        ("research latest developments in quantum computing", "researching", "should use research pipeline"),
        ("investigate blockchain technology trends", "investigating", "should use research pipeline"),

        # System queries - should use system diagnostics
        ("check system performance", "system_diagnostics", "should use system diagnostics"),
        ("diagnose computer issues", "system_diagnostics", "should use system diagnostics"),

        # Hinglish queries - should work with hinglish support
        ("youtube kholo", "app_control", "should work with hinglish"),
        ("nifty analyze karo", "trading_analysis", "should work with hinglish"),
        ("website banao", "creation_document", "should work with hinglish"),
    ]

    passed = 0
    total = len(test_cases)

    for query, expected_intent, description in test_cases:
        try:
            route = ai_manager.route(user_prompt=query)
            # route.intent.value is an int (auto() enum); compare by name.
            intent_match = route.intent.name.lower() == expected_intent

            status = "PASS" if intent_match else "FAIL"
            print(f"{status}: '{query}' -> {route.intent.name.lower()} (expected {expected_intent}) - {description}")
            print(f"  Execution mode: {route.execution_mode.value}")
            print(f"  Reasoning depth: {route.reasoning_depth.value}")
            print(f"  Confidence: {route.confidence:.2f}")
            print(f"  Provider preference: {route.provider_preference}")
            if route.explanation:
                print(f"  Explanation: {route.explanation}")
            print()

            if intent_match:
                passed += 1

        except Exception as e:
            print(f"ERROR: '{query}' -> Exception: {e}")
            print()

    print(f"Results: {passed}/{total} tests passed")
    if passed == total:
        print("All tests passed!")
        return True
    else:
        print("Some tests failed.")
        return False

if __name__ == "__main__":
    success = test_ai_manager_3()
    sys.exit(0 if success else 1)