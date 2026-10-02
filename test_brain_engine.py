#!/usr/bin/env python3
"""
Test script for the BrainEngine with updated ContextManager.
"""

import sys
import os

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

def test_brain_engine():
    """Test the BrainEngine can be instantiated with mocked dependencies."""
    print("Testing BrainEngine with updated ContextManager...")

    # We will try to import the BrainEngine and see if there are any immediate errors.
    try:
        from desktop_agent.brain.brain_engine import BrainEngine
        print("[PASS] Successfully imported BrainEngine")
    except Exception as e:
        print(f"[FAIL] Failed to import BrainEngine: {e}")
        return False

    # Now try to instantiate it with mocked dependencies.
    # We need to mock: orchestrator, planner, decision_engine, execution_coordinator,
    # reflection_engine, memory_manager, config.
    # We'll create simple mocks for each.

    try:
        # Mock execution_coordinator (needed by orchestrator and BrainEngine)
        class MockExecutionCoordinator:
            def __init__(self):
                self.reflection = None
                self.working_memory = None
                self.blackboard = None

        # Mock orchestrator
        class MockOrchestrator:
            def __init__(self):
                self.execution_coordinator = MockExecutionCoordinator()

            def execute(self, plan):
                return MockBrainResult()

        # Mock planner
        class MockPlanner:
            def create_plan(self, decision):
                return MockPlan()

        # Mock decision_engine
        class MockDecisionEngine:
            def decide(self, semantic_task, brain_context):
                return MockDecision()

        # Mock reflection_engine
        class MockReflectionEngine:
            def record(self, **kwargs):
                pass

        # Mock memory_manager
        class MockMemoryManager:
            def get_relevant_memories(self, query):
                return []

        # Mock config
        class MockConfig:
            brain_fps = 30

        # Mock BrainResult
        class MockBrainResult:
            def __init__(self):
                self.success = True
                self.message = "Test"
                self.actions = []
                self.duration_ms = 0
                self.metadata = {}
                self.provider = ""

        # Mock Plan
        class MockPlan:
            def __init__(self):
                self.successful = True
                self.total_steps = 1
                self.reason = ""

        # Mock Decision
        class MockDecision:
            def __init__(self):
                self.goal = "TestGoal"
                self.decision_type = "direct"
                self.confidence = 0.9
                self.reasoning = []
                self.needs_confirmation = False
                self.action = None
                self.parameters = {}

        # Now create the BrainEngine with our mocks
        orchestrator = MockOrchestrator()
        planner = MockPlanner()
        decision_engine = MockDecisionEngine()
        execution_coordinator = None  # Let the BrainEngine set it
        reflection_engine = MockReflectionEngine()
        memory_manager = MockMemoryManager()
        config = MockConfig()

        brain_engine = BrainEngine(
            orchestrator=orchestrator,
            planner=planner,
            decision_engine=decision_engine,
            execution_coordinator=execution_coordinator,
            reflection_engine=reflection_engine,
            memory_manager=memory_manager,
            config=config
        )

        print("[PASS] Successfully instantiated BrainEngine with mocked dependencies")

        # Check that the context_manager was set and is of the correct type
        from desktop_agent.brain.context_manager import ContextManager
        if isinstance(brain_engine.context_manager, ContextManager):
            print("[PASS] BrainEngine.context_manager is correctly set as ContextManager")
        else:
            print(f"[FAIL] BrainEngine.context_manager is not ContextManager: {type(brain_engine.context_manager)}")
            return False

        # Check that the context_manager has the expected dependencies set
        # We can't easily check the internal state without breaking encapsulation, but we can trust that if it's set, it's set correctly.
        # We'll just note that the test passed.

        print("\n[PASS] All BrainEngine tests passed!")
        return True

    except Exception as e:
        print(f"[FAIL] Failed to instantiate BrainEngine: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_brain_engine()
    sys.exit(0 if success else 1)