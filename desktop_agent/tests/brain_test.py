"""
MYRAA Brain Diagnostic

Tests:
- Brain Engine
- Blackboard
- Planner
- Thinking
- Reflection
- Memory
"""
from __future__ import annotations

import sys
from pathlib import Path

# -------------------------------------------------------
# Add MYRAA project root to Python path
# -------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import traceback


class BrainTest:

    def __init__(self):

        self.total = 0
        self.passed = 0
        self.failed = 0

    # -----------------------------------------------------

    def run(self, name, func):

        self.total += 1

        print("-" * 60)
        print(name)
        print("-" * 60)

        try:

            func()

            self.passed += 1

            print("PASS")

        except Exception:

            self.failed += 1

            print("FAIL")

            traceback.print_exc()

        print()

    # -----------------------------------------------------

    def summary(self):

        print("=" * 60)

        print("Brain Test Summary")

        print("=" * 60)

        print(f"Passed : {self.passed}")

        print(f"Failed : {self.failed}")

        print(f"Total  : {self.total}")

        if self.total:

            percent = self.passed / self.total * 100

            print(f"Health : {percent:.1f}%")

    # =====================================================
    # Blackboard
    # =====================================================

    def test_blackboard(self):

        from desktop_agent.brain.blackboard.blackboard import Blackboard

        bb = Blackboard()

        bb.write("test", "value", 123)

        assert bb.read("test", "value") == 123

        print("Blackboard OK")

    # =====================================================
    # Working Memory
    # =====================================================

    def test_working_memory(self):

        from desktop_agent.brain.working_memory.working_memory import WorkingMemory

        wm = WorkingMemory()

        assert wm is not None

        print("Working Memory OK")

    # =====================================================
    # Reflection
    # =====================================================

    def test_reflection(self):

        from desktop_agent.brain.reflection.reflection_engine import ReflectionEngine

        from desktop_agent.brain.working_memory.working_memory import WorkingMemory

        reflection = ReflectionEngine(

            working_memory=WorkingMemory()

        )

        assert reflection is not None

        print("Reflection Engine OK")

    # =====================================================
    # Planner
    # =====================================================

    def test_planner(self):

        from desktop_agent.brain.planner.planner import Planner

        planner = Planner()

        assert planner is not None

        print("Planner OK")

    # =====================================================
    # Thinking
    # =====================================================

    def test_thinking(self):

        from desktop_agent.brain.blackboard.blackboard import Blackboard

        from desktop_agent.brain.thinking.thinking_engine import ThinkingEngine

        engine = ThinkingEngine(

            blackboard=Blackboard()

        )

        assert engine is not None

        print("Thinking Engine OK")

    # =====================================================
    # Brain Engine
    # =====================================================

    def test_brain(self):

        from unittest.mock import MagicMock

        from desktop_agent.brain.brain_engine import BrainEngine

        from desktop_agent.brain.orchestrator.orchestrator import Orchestrator

        dispatcher = MagicMock()

        dispatcher.dispatch.return_value = None

        orchestrator = Orchestrator(

            dispatcher=dispatcher,

        )

        brain = BrainEngine(

            orchestrator=orchestrator,

        )

        assert brain is not None

        print("Brain Engine OK")


# ==========================================================
# Main
# ==========================================================

def main():

    test = BrainTest()

    test.run(

        "Blackboard",

        test.test_blackboard,

    )

    test.run(

        "Working Memory",

        test.test_working_memory,

    )

    test.run(

        "Reflection",

        test.test_reflection,

    )

    test.run(

        "Planner",

        test.test_planner,

    )

    test.run(

        "Thinking",

        test.test_thinking,

    )

    test.run(

        "Brain Engine",

        test.test_brain,

    )

    test.summary()


if __name__ == "__main__":

    main()