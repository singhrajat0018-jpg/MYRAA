"""
===============================================================================
MYRAA Brain Diagnostics
===============================================================================

Author  : MYRAA Project
Purpose : Complete Brain Health Diagnostics

Run:
    python -m desktop_agent.tests.brain_diagnostics

This tool validates:

✓ Brain Engine
✓ Memory System
✓ Observer Pipeline
✓ Cognitive Cycle
✓ Reasoning Pipeline
✓ Executive Controller
✓ Planner
✓ Executor
✓ Reflection Engine
✓ Working Memory
✓ Performance

===============================================================================
"""

from __future__ import annotations

import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Any



# ============================================================================
# Import MYRAA Modules
# ============================================================================

from desktop_agent.brain.brain_engine import BrainEngine

from desktop_agent.brain.orchestrator.orchestrator import Orchestrator



# ============================================================================
# Console Colors
# ============================================================================

class Color:

    RESET = "\033[0m"

    RED = "\033[91m"

    GREEN = "\033[92m"

    YELLOW = "\033[93m"

    BLUE = "\033[94m"

    CYAN = "\033[96m"

    BOLD = "\033[1m"



# ============================================================================
# Result Model
# ============================================================================

@dataclass
class CheckResult:

    name: str

    passed: bool

    duration: float = 0.0

    details: str = ""



# ============================================================================
# Statistics
# ============================================================================

@dataclass
class DiagnosticStats:

    total: int = 0

    passed: int = 0

    failed: int = 0

    warnings: int = 0

    execution_time: float = 0.0



# ============================================================================
# Diagnostics Exception
# ============================================================================

class DiagnosticFailure(Exception):
    """Raised when a diagnostic test fails."""
    pass



# ============================================================================
# Timer
# ============================================================================

class Timer:

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    @property
    def elapsed(self):
        return time.perf_counter() - self.start

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass



# ============================================================================
# Banner
# ============================================================================

def print_banner():

    print()

    print(Color.CYAN + "=" * 70)

    print("                    MYRAA BRAIN DIAGNOSTICS")

    print("=" * 70 + Color.RESET)

    print()



# ============================================================================
# Footer
# ============================================================================

def print_footer():

    print()

    print(Color.CYAN + "=" * 70 + Color.RESET)

    print()



# ============================================================================
# Utility
# ============================================================================

def safe_name(obj: Any) -> str:

    if obj is None:

        return "None"

    return obj.__class__.__name__



# ============================================================================
# PASS Printer
# ============================================================================

def ok(msg: str):

    print(f"{Color.GREEN}[PASS]{Color.RESET} {msg}")



# ============================================================================
# FAIL Printer
# ============================================================================

def fail(msg: str):

    print(f"{Color.RED}[FAIL]{Color.RESET} {msg}")



# ============================================================================
# WARN Printer
# ============================================================================

def warn(msg: str):

    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")



# ============================================================================
# INFO Printer
# ============================================================================

def info(msg: str):

    print(f"{Color.BLUE}[INFO]{Color.RESET} {msg}")


# ============================================================================
# Brain Diagnostics
# ============================================================================

class BrainDiagnostics:

    """
    Enterprise diagnostics for MYRAA Brain.

    This class performs:

    1. Module Validation
    2. Dependency Validation
    3. Observer Pipeline Test
    4. Command Pipeline Test
    5. Reflection Validation
    6. Performance Diagnostics
    7. Final Health Report
    """

    # ------------------------------------------------------------------------

    def __init__(self):

        self.results: List[CheckResult] = []

        self.stats = DiagnosticStats()

        self.brain: Optional[BrainEngine] = None

        self.orchestrator = None

        self.start_time = 0.0

        self.end_time = 0.0

    # ------------------------------------------------------------------------

    def initialize(self):

        info("Initializing Brain Engine...")

        from desktop_agent.main import BRAIN

        self.brain = BRAIN.brain_engine
        self.orchestrator = self.brain.orchestrator

        ok("Brain Engine initialized")

    # ------------------------------------------------------------------------

    def add_result(
        self,
        name: str,
        passed: bool,
        duration: float = 0.0,
        details: str = "",
    ):

        result = CheckResult(
            name=name,
            passed=passed,
            duration=duration,
            details=details,
        )

        self.results.append(result)

        self.stats.total += 1

        if passed:

            self.stats.passed += 1

        else:

            self.stats.failed += 1

    # ------------------------------------------------------------------------

    def run_test(
        self,
        name: str,
        callback: Callable,
    ):

        info(f"Running: {name}")

        with Timer() as timer:

            try:

                callback()

                self.add_result(
                    name=name,
                    passed=True,
                    duration=timer.elapsed,
                )

                ok(name)

            except Exception as e:

                self.add_result(
                    name=name,
                    passed=False,
                    duration=timer.elapsed,
                    details=str(e),
                )

                fail(name)

                print(traceback.format_exc())

    # ------------------------------------------------------------------------

    def start(self):

        self.start_time = time.perf_counter()

        print_banner()

        self.initialize()

    # ------------------------------------------------------------------------

    def finish(self):

        self.end_time = time.perf_counter()

        self.stats.execution_time = (

            self.end_time

            - self.start_time

        )

    # ------------------------------------------------------------------------

    @property
    def health(self) -> float:

        if self.stats.total == 0:

            return 0.0

        return (

            self.stats.passed

            / self.stats.total

        ) * 100.0

    # ------------------------------------------------------------------------

    @property
    def failed(self):

        return [

            r

            for r in self.results

            if not r.passed

        ]

    # ------------------------------------------------------------------------

    @property
    def passed(self):

        return [

            r

            for r in self.results

            if r.passed

        ]

    # ------------------------------------------------------------------------

    def require_brain(self):

        if self.brain is None:

            raise DiagnosticFailure(

                "BrainEngine not initialized."

            )

        return self.brain

# ============================================================================
# Module Validation
# ============================================================================

    def validate_brain_engine(self):

        brain = self.require_brain()

        if not isinstance(brain, BrainEngine):

            raise DiagnosticFailure(
                "Invalid BrainEngine instance."
            )


    # ------------------------------------------------------------------------

    def validate_working_memory(self):

        brain = self.require_brain()

        if not hasattr(brain, "working_memory"):

            raise DiagnosticFailure(
                "working_memory missing."
            )

        if brain.working_memory is None:

            raise DiagnosticFailure(
                "working_memory is None."
            )


    # ------------------------------------------------------------------------

    def validate_memory_manager(self):

        brain = self.require_brain()

        if not hasattr(brain, "memory"):

            raise DiagnosticFailure(
                "MemoryManager missing."
            )

        memory = brain.memory

        required = [

            "working",

            "episodic",

            "semantic",

        ]

        for attr in required:

            if not hasattr(memory, attr):

                raise DiagnosticFailure(

                    f"MemoryManager missing '{attr}'."

                )


    # ------------------------------------------------------------------------

    def validate_attention(self):

        brain = self.require_brain()

        if not hasattr(brain, "attention"):

            raise DiagnosticFailure(

                "AttentionEngine missing."

            )


    # ------------------------------------------------------------------------

    def validate_reasoning_pipeline(self):

        brain = self.require_brain()

        if not hasattr(brain, "reasoning_pipeline"):

            raise DiagnosticFailure(

                "ReasoningPipeline missing."

            )


    # ------------------------------------------------------------------------

    def validate_intent_classifier(self):

        brain = self.require_brain()

        if not hasattr(brain, "intent_classifier"):

            raise DiagnosticFailure(

                "IntentClassifier missing."

            )


    # ------------------------------------------------------------------------

    def validate_executive(self):

        brain = self.require_brain()

        if not hasattr(brain, "executive"):

            raise DiagnosticFailure(

                "ExecutiveController missing."

            )

        if brain.executive is None:

            raise DiagnosticFailure(

                "ExecutiveController is None."

            )


    # ------------------------------------------------------------------------

    def validate_planner(self):

        brain = self.require_brain()

        if not hasattr(brain, "planner"):

            raise DiagnosticFailure(

                "Planner missing."

            )

        planner = brain.planner

        if not hasattr(planner, "create_plan"):

            raise DiagnosticFailure(

                "Planner.create_plan() missing."

            )


    # ------------------------------------------------------------------------

    def validate_executor(self):

        brain = self.require_brain()

        if not hasattr(brain, "execute"):
            raise DiagnosticFailure(
                "BrainEngine.execute() missing."
            )

        if not callable(brain.execute):
            raise DiagnosticFailure(
                "BrainEngine.execute() is not callable."
            )


    # ------------------------------------------------------------------------

    def validate_reflection(self):

        brain = self.require_brain()

        if not hasattr(brain, "reflection"):

            raise DiagnosticFailure(

                "ReflectionEngine missing."

            )

        reflection = brain.reflection

        if not hasattr(reflection, "learn"):

            raise DiagnosticFailure(

                "Reflection.learn() missing."

            )


    # ------------------------------------------------------------------------

    def validate_orchestrator(self):

        brain = self.require_brain()

        if not hasattr(brain, "orchestrator"):

            raise DiagnosticFailure(

                "Execution Orchestrator missing."

            )


# ============================================================================
# Execute All Module Tests
# ============================================================================

    def run_module_validation(self):

        print()

        print("=" * 70)

        print("MODULE VALIDATION")

        print("=" * 70)

        print()

        self.run_test(

            "Brain Engine",

            self.validate_brain_engine,

        )

        self.run_test(

            "Working Memory",

            self.validate_working_memory,

        )

        self.run_test(

            "Memory Manager",

            self.validate_memory_manager,

        )

        self.run_test(

            "Attention Engine",

            self.validate_attention,

        )

        self.run_test(

            "Reasoning Pipeline",

            self.validate_reasoning_pipeline,

        )

        self.run_test(

            "Intent Classifier",

            self.validate_intent_classifier,

        )

        self.run_test(

            "Executive Controller",

            self.validate_executive,

        )

        self.run_test(

            "Planner",

            self.validate_planner,

        )

        self.run_test(

            "Executor",

            self.validate_executor,

        )

        self.run_test(

            "Reflection Engine",

            self.validate_reflection,

        )

        self.run_test(

            "Execution Orchestrator",

            self.validate_orchestrator,

        )

# ============================================================================
# Observer Pipeline Diagnostics
# ============================================================================

    class FakeObserverEvent:

        def __init__(self):

            self.source = "Diagnostics"

            self.title = "Brain Diagnostics"

            self.message = "Observer pipeline validation."

            self.severity = "high"

            self.payload = {

                "test": True,

                "origin": "brain_diagnostics",

            }

            self.timestamp = time.time()


    # ------------------------------------------------------------------------

    def _working_memory_event_count(self):

        brain = self.require_brain()

        wm = brain.working_memory

        snapshot = None

        try:

            snapshot = wm.snapshot()

        except Exception:

            try:

                snapshot = wm.get_snapshot()

            except Exception:

                return None

        if snapshot is None:

            return None

        if hasattr(snapshot, "events"):

            events = snapshot.events

            if hasattr(events, "recent_events"):

                try:

                    return len(events.recent_events)

                except Exception:

                    return None

        return None


    # ------------------------------------------------------------------------

    def observer_pipeline_test(self):

        brain = self.require_brain()

        before = self._working_memory_event_count()

        event = self.FakeObserverEvent()

        brain.process_event(event)

        after = self._working_memory_event_count()

        if before is not None and after is not None:

            if after <= before:

                raise DiagnosticFailure(

                    "Observer event was not stored in WorkingMemory."

                )


    # ------------------------------------------------------------------------

    def episodic_memory_test(self):

        brain = self.require_brain()

        episodic = brain.memory.episodic

        event = self.FakeObserverEvent()

        before = None

        after = None

        if hasattr(episodic, "recent"):

            try:

                before = len(episodic.recent())

            except Exception:

                pass

        brain.process_event(event)

        if hasattr(episodic, "recent"):

            try:

                after = len(episodic.recent())

            except Exception:

                pass

        if before is not None and after is not None:

            if after <= before:

                raise DiagnosticFailure(

                    "Observer event not recorded into EpisodicMemory."

                )


    # ------------------------------------------------------------------------

    def attention_queue_test(self):

        brain = self.require_brain()

        event = self.FakeObserverEvent()

        brain.process_event(event)

        attention = brain.attention

        if hasattr(attention, "next"):

            item = attention.next()

            if item is None:

                raise DiagnosticFailure(

                    "Attention queue did not receive event."

                )


    # ------------------------------------------------------------------------

    def cognitive_cycle_test(self):

        brain = self.require_brain()

        event = self.FakeObserverEvent()

        brain.process_event(event)

        brain.cognitive_cycle.run()


    # ------------------------------------------------------------------------

    def run_observer_pipeline(self):

        print()

        print("=" * 70)

        print("OBSERVER PIPELINE")

        print("=" * 70)

        print()

        self.run_test(

            "Working Memory Event",

            self.observer_pipeline_test,

        )

        self.run_test(

            "Episodic Memory",

            self.episodic_memory_test,

        )

        self.run_test(

            "Attention Queue",

            self.attention_queue_test,

        )

        self.run_test(

            "Cognitive Cycle",

            self.cognitive_cycle_test,

        )

# ============================================================================
# Command Pipeline Diagnostics
# ============================================================================

    def semantic_parser_test(self):

        brain = self.require_brain()

        parser = brain.semantic_parser

        if parser is None:

            raise DiagnosticFailure(

                "SemanticParser not initialized."

            )

        task = parser.parse(

            "open notepad",

            None,

        )

        if task is None:

            raise DiagnosticFailure(

                "SemanticParser returned None."

            )

        self._semantic_task = task


    # ------------------------------------------------------------------------

    def thinking_test(self):

        brain = self.require_brain()

        if not hasattr(self, "_semantic_task"):

            raise DiagnosticFailure(

                "SemanticTask not available."

            )

        context = brain.think(

            self._semantic_task

        )

        if context is None:

            raise DiagnosticFailure(

                "BrainContext is None."

            )

        self._brain_context = context


    # ------------------------------------------------------------------------

    def decision_test(self):

        brain = self.require_brain()

        if not hasattr(self, "_semantic_task"):

            raise DiagnosticFailure(

                "SemanticTask missing."

            )

        if not hasattr(self, "_brain_context"):

            raise DiagnosticFailure(

                "BrainContext missing."

            )

        decision = brain.decision.decide(

            self._semantic_task,

            self._brain_context,

        )

        if decision is None:

            raise DiagnosticFailure(

                "DecisionEngine returned None."

            )

        self._decision = decision


    # ------------------------------------------------------------------------

    def planner_test(self):

        brain = self.require_brain()

        if not hasattr(self, "_decision"):

            raise DiagnosticFailure(

                "Decision unavailable."

            )

        plan = brain.planner.create_plan(

            self._decision

        )

        if plan is None:

            raise DiagnosticFailure(

                "Planner returned None."

            )

        self._plan = plan


    # ------------------------------------------------------------------------

    def execution_plan_test(self):

        if not hasattr(self, "_plan"):

            raise DiagnosticFailure(

                "ExecutionPlan missing."

            )

        plan = self._plan

        if not hasattr(plan, "steps"):

            raise DiagnosticFailure(

                "ExecutionPlan has no steps."

            )

        if len(plan.steps) == 0:

            raise DiagnosticFailure(

                "ExecutionPlan contains zero steps."

            )


    # ------------------------------------------------------------------------

    def executor_validation(self):

        brain = self.require_brain()

        if not hasattr(brain, "execute"):
            raise DiagnosticFailure(
                "BrainEngine.execute() missing."
            )

        if not callable(brain.execute):
            raise DiagnosticFailure(
                "BrainEngine.execute() is not callable."
            )

        if not hasattr(brain, "orchestrator"):
            raise DiagnosticFailure(
                "Execution Orchestrator missing."
            )

        if brain.orchestrator is None:
            raise DiagnosticFailure(
                "Execution Orchestrator is None."
            )




    # ------------------------------------------------------------------------

    def run_command_pipeline(self):

        print()

        print("=" * 70)

        print("COMMAND PIPELINE")

        print("=" * 70)

        print()

        self.run_test(

            "Semantic Parser",

            self.semantic_parser_test,

        )

        self.run_test(

            "Thinking",

            self.thinking_test,

        )

        self.run_test(

            "Decision Engine",

            self.decision_test,

        )

        self.run_test(

            "Planner",

            self.planner_test,

        )

        self.run_test(

            "Execution Plan",

            self.execution_plan_test,

        )

        self.run_test(

            "Executor Validation",

            self.executor_validation,

        )

# ============================================================================
# Reflection & Performance Diagnostics
# ============================================================================

    def reflection_validation(self):

        brain = self.require_brain()

        reflection = brain.reflection

        if reflection is None:

            raise DiagnosticFailure(

                "ReflectionEngine not initialized."

            )

        if not hasattr(reflection, "learn"):

            raise DiagnosticFailure(

                "Reflection.learn() missing."

            )


    # ------------------------------------------------------------------------

    def working_memory_snapshot_test(self):

        brain = self.require_brain()

        wm = brain.working_memory

        snapshot = None

        if hasattr(wm, "get_snapshot"):

            snapshot = wm.get_snapshot()

        elif hasattr(wm, "snapshot"):

            snapshot = wm.snapshot()

        if snapshot is None:

            raise DiagnosticFailure(

                "WorkingMemory snapshot unavailable."

            )

        self._working_snapshot = snapshot


    # ------------------------------------------------------------------------

    def brain_state_test(self):

        brain = self.require_brain()

        if not hasattr(brain, "state"):

            raise DiagnosticFailure(

                "BrainState missing."

            )

        if brain.state is None:

            raise DiagnosticFailure(

                "BrainState is None."

            )


    # ------------------------------------------------------------------------

    def goal_manager_test(self):

        brain = self.require_brain()

        if not hasattr(brain, "goals"):

            raise DiagnosticFailure(

                "GoalManager missing."

            )

        goal = brain.current_goal()

        _ = goal


    # ------------------------------------------------------------------------

    def perception_test(self):

        brain = self.require_brain()

        if not hasattr(brain, "perception"):

            raise DiagnosticFailure(

                "Perception module missing."

            )

        _ = brain.perception.snapshot


    # ------------------------------------------------------------------------

    def world_model_test(self):

        brain = self.require_brain()

        if not hasattr(brain, "world"):

            raise DiagnosticFailure(

                "WorldModel missing."

            )

        _ = brain.world.state


    # ------------------------------------------------------------------------

    def context_builder_test(self):

        brain = self.require_brain()

        if not hasattr(self, "_semantic_task"):

            raise DiagnosticFailure(

                "SemanticTask unavailable."

            )

        context = brain._build_context(

            self._semantic_task

        )

        if context is None:

            raise DiagnosticFailure(

                "BrainContext creation failed."

            )


    # ------------------------------------------------------------------------

    def performance_test(self):

        brain = self.require_brain()

        start = time.perf_counter()

        for _ in range(10):

            brain.working_snapshot()

        elapsed = time.perf_counter() - start

        if elapsed > 1.0:

            raise DiagnosticFailure(

                f"WorkingMemory snapshot too slow ({elapsed:.3f}s)"

            )


    # ------------------------------------------------------------------------

    def dependency_report(self):

        brain = self.require_brain()

        modules = [

            ("Perception", brain.perception),

            ("WorldModel", brain.world),

            ("Reasoning", brain.reasoning),

            ("WorkingMemory", brain.working_memory),

            ("MemoryManager", brain.memory),

            ("Planner", brain.planner),

            ("Orchestrator", brain.orchestrator),

            ("Reflection", brain.reflection),

            ("Attention", brain.attention),

            ("Decision", brain.decision),

            ("IntentClassifier", brain.intent_classifier),

            ("Executive", brain.executive),

        ]

        print()

        print("=" * 70)

        print("DEPENDENCY REPORT")

        print("=" * 70)

        print()

        for name, module in modules:

            if module is None:

                warn(f"{name:<25} : None")

            else:

                ok(f"{name:<25} : {safe_name(module)}")


    # ------------------------------------------------------------------------

    def run_reflection_validation(self):

        print()

        print("=" * 70)

        print("REFLECTION & PERFORMANCE")

        print("=" * 70)

        print()

        self.run_test(

            "Reflection Engine",

            self.reflection_validation,

        )

        self.run_test(

            "Working Memory Snapshot",

            self.working_memory_snapshot_test,

        )

        self.run_test(

            "Brain State",

            self.brain_state_test,

        )

        self.run_test(

            "Goal Manager",

            self.goal_manager_test,

        )

        self.run_test(

            "Perception",

            self.perception_test,

        )

        self.run_test(

            "World Model",

            self.world_model_test,

        )

        self.run_test(

            "Context Builder",

            self.context_builder_test,

        )

        self.run_test(

            "Performance",

            self.performance_test,

        )

        self.dependency_report()

# ============================================================================
# Final Report Generator
# ============================================================================

    def print_summary(self):

        print()

        print("=" * 70)

        print("DIAGNOSTICS SUMMARY")

        print("=" * 70)

        print()

        for result in self.results:

            status = "PASS" if result.passed else "FAIL"

            color = Color.GREEN if result.passed else Color.RED

            print(

                f"{color}[{status}]{Color.RESET}"

                f" {result.name:<35}"

                f"{result.duration:.4f}s"

            )

            if result.details:

                print(

                    f"      {Color.YELLOW}"

                    f"{result.details}"

                    f"{Color.RESET}"

                )


    # ------------------------------------------------------------------------

    def print_statistics(self):

        print()

        print("=" * 70)

        print("STATISTICS")

        print("=" * 70)

        print()

        print(f"Total Tests      : {self.stats.total}")

        print(f"Passed           : {self.stats.passed}")

        print(f"Failed           : {self.stats.failed}")

        print(f"Warnings         : {self.stats.warnings}")

        print(

            f"Execution Time   : "

            f"{self.stats.execution_time:.3f}s"

        )


    # ------------------------------------------------------------------------

    def print_health(self):

        score = self.health

        print()

        print("=" * 70)

        print("SYSTEM HEALTH")

        print("=" * 70)

        print()

        if score >= 95:

            color = Color.GREEN

            status = "EXCELLENT"

        elif score >= 80:

            color = Color.CYAN

            status = "GOOD"

        elif score >= 60:

            color = Color.YELLOW

            status = "WARNING"

        else:

            color = Color.RED

            status = "CRITICAL"

        print(

            color

            + f"Overall Health : {score:.1f}%"

            + Color.RESET

        )

        print(

            color

            + f"Status         : {status}"

            + Color.RESET

        )


    # ------------------------------------------------------------------------

    def print_failures(self):

        if not self.failed:

            return

        print()

        print("=" * 70)

        print("FAILED TESTS")

        print("=" * 70)

        print()

        for item in self.failed:

            fail(item.name)

            print()

            print(item.details)

            print()


    # ------------------------------------------------------------------------

    def print_performance(self):

        if not self.results:

            return

        fastest = min(

            self.results,

            key=lambda x: x.duration,

        )

        slowest = max(

            self.results,

            key=lambda x: x.duration,

        )

        print()

        print("=" * 70)

        print("PERFORMANCE REPORT")

        print("=" * 70)

        print()

        print(

            f"Fastest Test : "

            f"{fastest.name}"

        )

        print(

            f"Time         : "

            f"{fastest.duration:.6f}s"

        )

        print()

        print(

            f"Slowest Test : "

            f"{slowest.name}"

        )

        print(

            f"Time         : "

            f"{slowest.duration:.6f}s"

        )


    # ------------------------------------------------------------------------

    def generate_report(self):

        self.finish()

        self.print_summary()

        self.print_statistics()

        self.print_health()

        self.print_performance()

        self.print_failures()

        print_footer()


    # ------------------------------------------------------------------------

    def run(self):

        self.start()

        self.run_module_validation()

        self.run_observer_pipeline()

        self.run_command_pipeline()

        self.run_reflection_validation()

        self.generate_report()

# ============================================================================
# Main
# ============================================================================

def main():

    diagnostics = BrainDiagnostics()

    try:

        diagnostics.run()

    except KeyboardInterrupt:

        print()

        warn("Diagnostics interrupted by user.")

        sys.exit(1)

    except Exception:

        print()

        fail("Fatal diagnostics error")

        traceback.print_exc()

        sys.exit(1)

    print()

    ok("Diagnostics completed successfully.")

    if diagnostics.stats.failed == 0:

        print()

        print(Color.GREEN + "MYRAA Brain is HEALTHY." + Color.RESET)

        sys.exit(0)

    print()

    print(Color.RED + "MYRAA Brain requires attention." + Color.RESET)

    sys.exit(2)


if __name__ == "__main__":

    main()   