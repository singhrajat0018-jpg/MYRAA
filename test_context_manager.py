#!/usr/bin/env python3
"""
Test script for the ContextManager implementation.
"""

import sys
import os

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

def test_context_manager():
    """Test the ContextManager implementation."""
    print("Testing ContextManager...")

    # Import the ContextManager
    try:
        from desktop_agent.brain.context_manager import ContextManager
        from desktop_agent.brain.models import BrainContext
        print("[PASS] Successfully imported ContextManager and BrainContext")
    except Exception as e:
        print(f"[FAIL] Failed to import: {e}")
        return False

    # Test instantiation
    try:
        cm = ContextManager()
        print("[PASS] Successfully instantiated ContextManager")
    except Exception as e:
        print(f"[FAIL] Failed to instantiate ContextManager: {e}")
        return False

    # Test build method with basic parameters
    try:
        context = cm.build("test_tool", {"param": "value"})
        print("[PASS] Successfully built context with basic parameters")
        print(f"  Context metadata keys: {list(context.metadata.keys())}")
        print(f"  Context active_app: {context.active_app}")
        print(f"  Context active_window: {context.active_window}")
    except Exception as e:
        print(f"[FAIL] Failed to build context: {e}")
        return False

    # Test build_from_state method
    try:
        context = cm.build_from_state()
        print("[PASS] Successfully built context from state")
        print(f"  Context metadata keys: {list(context.metadata.keys())}")
    except Exception as e:
        print(f"[FAIL] Failed to build context from state: {e}")
        return False

    # Test with perception, blackboard, and memory manager (mocks)
    try:
        # Create mock objects
        class MockScreenState:
            active_application = "TestApp"
            active_window = "TestWindow"
            timestamp = "2026-08-16"

        class MockPerceptionState:
            screen_state = MockScreenState()

        class MockPerception:
            state = MockPerceptionState()

        class MockBlackboard:
            def get_current_goal(self):
                return "TestGoal"

            def get_current_task(self):
                return {"task": "TestTask"}

            def get_recent_conversation(self, limit=5):
                return [{"role": "user", "text": "Hello"}, {"role": "assistant", "text": "Hi"}]

        class MockMemoryManager:
            def get_relevant_memories(self, query):
                return [{"memory": "TestMemory", "relevance": 0.9}]

        perception = MockPerception()
        blackboard = MockBlackboard()
        memory_manager = MockMemoryManager()

        cm_with_deps = ContextManager(perception, blackboard, memory_manager)
        context = cm_with_deps.build("test_tool", {"param": "value"})

        print("[PASS] Successfully built context with dependencies")
        print(f"  Context active_app: {context.active_app}")
        print(f"  Context active_window: {context.active_window}")
        print(f"  Context metadata keys: {list(context.metadata.keys())}")
        print(f"  Context memory: {context.memory}")

    except Exception as e:
        print(f"[FAIL] Failed to build context with dependencies: {e}")
        return False

    print("\n[PASS] All ContextManager tests passed!")
    return True

if __name__ == "__main__":
    success = test_context_manager()
    sys.exit(0 if success else 1)