"""
==========================================================
                    MYRAA DIAGNOSTIC
==========================================================

Professional Health Check System

Checks

✓ Python
✓ Operating System
✓ CPU
✓ RAM
✓ GPU
✓ Installed Packages
✓ Project Structure
✓ Imports
✓ Brain
✓ Memory
✓ Blackboard
✓ Thinking
✓ Vision
✓ Voice
✓ Knowledge
✓ Planner
✓ Execution

Run

    python myraa_test.py
"""

from __future__ import annotations

import os
import sys
import time
import platform
import traceback
import importlib
from pathlib import Path
from dataclasses import dataclass, field

from desktop_agent.config.settings import TAVILY_API_KEY

try:
    import psutil
except Exception:
    psutil = None

# ==========================================================
# PROJECT ROOT
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent

# ==========================================================
# RESULT
# ==========================================================

@dataclass
class TestResult:

    name: str

    passed: bool

    message: str = ""

    duration: float = 0.0


# ==========================================================
# DIAGNOSTIC
# ==========================================================

class MyraaDiagnostic:

    def __init__(self):

        self.results: list[TestResult] = []

        self.start_time = time.perf_counter()

    # ------------------------------------------------------

    def banner(self):

        print()

        print("=" * 70)

        print("               MYRAA COMPLETE DIAGNOSTIC")

        print("=" * 70)

        print()

    # ------------------------------------------------------

    def add(

        self,

        name,

        passed,

        message="",

        duration=0,

    ):

        self.results.append(

            TestResult(

                name=name,

                passed=passed,

                message=message,

                duration=duration,

            )

        )

    # ------------------------------------------------------

    def run_test(

        self,

        name,

        func,

    ):

        start = time.perf_counter()

        print()

        print("-" * 60)

        print(name)

        print("-" * 60)

        try:

            func()

            elapsed = time.perf_counter() - start

            self.add(

                name,

                True,

                duration=elapsed,

            )

            print("PASS")

        except Exception as e:

            elapsed = time.perf_counter() - start

            self.add(

                name,

                False,

                str(e),

                elapsed,

            )

            print("FAIL")

            traceback.print_exc()

    # ======================================================
    # BASIC TESTS
    # ======================================================

    def test_python(self):

        print("Version :", sys.version)

        assert sys.version_info >= (3, 11)

    # ------------------------------------------------------

    def test_os(self):

        print(platform.platform())

    # ------------------------------------------------------

    def test_cpu(self):

        if psutil:

            print(

                "CPU :", psutil.cpu_percent(interval=1),

                "%"

            )

    # ------------------------------------------------------

    def test_ram(self):

        if psutil:

            ram = psutil.virtual_memory()

            print(

                "RAM :",

                round(

                    ram.used / 1024**3,

                    2,

                ),

                "/",

                round(

                    ram.total / 1024**3,

                    2,

                ),

                "GB",

            )

    # ------------------------------------------------------

    def test_project(self):

        required = [

            "desktop_agent",

            "backend",

            "frontend",

        ]

        for folder in required:

            path = PROJECT_ROOT / folder

            print(

                folder,

                "OK"

                if path.exists()

                else "Missing",

            )

    # ------------------------------------------------------

    def summary(self):

        print()

        print("=" * 70)

        print("SUMMARY")

        print("=" * 70)

        passed = sum(

            r.passed

            for r in self.results

        )

        total = len(self.results)

        print()

        for r in self.results:

            status = "PASS" if r.passed else "FAIL"

            print(

                f"{status:<8}",

                f"{r.name:<30}",

                f"{r.duration:.2f}s",

            )

        print()

        print("-" * 70)

        print(

            "Health Score :",

            f"{passed}/{total}",

        )

        print(

            "Percentage   :",

            round(

                passed / total * 100,

                2,

            ),

            "%",

        )

        print(

            "Total Time   :",

            round(

                time.perf_counter()

                - self.start_time,

                2,

            ),

            "sec",

        )

        print("-" * 70)


    # ======================================================
    # IMPORT TEST
    # ======================================================

    def test_imports(self):

        modules = [

            "desktop_agent",

            "desktop_agent.brain",

            "desktop_agent.brain.brain_engine",

            "desktop_agent.brain.blackboard.blackboard",

            "desktop_agent.brain.memory.manager",

            "desktop_agent.brain.working_memory.working_memory",

            "desktop_agent.brain.reasoning_engine",

            "desktop_agent.brain.planner.planner",

            "desktop_agent.brain.reflection.reflection_engine",

            "desktop_agent.brain.thinking.thinking_engine",

        ]

        failed = []

        print()

        print("Checking Imports...\n")

        for module in modules:

            try:

                importlib.import_module(module)

                print(f"[OK] {module}")

            except Exception as e:

                failed.append(module)

                print(f"[FAIL] {module}")

                print(e)

        if failed:

            raise RuntimeError(

                f"{len(failed)} imports failed."

            )

    # ======================================================
    # BLACKBOARD TEST
    # ======================================================

    def test_blackboard(self):

        from desktop_agent.brain.blackboard.blackboard import Blackboard

        bb = Blackboard()

        bb.write(

            "system",

            "status",

            "online",

        )

        value = bb.read(

            "system",

            "status",

        )

        assert value == "online"

        print("Read/Write OK")

        events = []

        def callback(data):

            events.append(data)

        bb.subscribe(

            "brain.ready",

            callback,

        )

        bb.publish(

            "brain.ready",

            value=123,

        )

        assert len(events) == 1

        print("Publish OK")

        bb.clear()

        print("Clear OK")

    # ======================================================
    # MEMORY TEST
    # ======================================================

    def test_memory(self):

        from desktop_agent.brain.memory.manager import MemoryManager

        memory = MemoryManager()

        assert memory is not None

        print("Memory Manager OK")

        print()

        for attr in [

            "working",

            "episodic",

            "semantic",

        ]:

            if hasattr(memory, attr):

                print(f"{attr:<15} OK")

            else:

                print(f"{attr:<15} Missing")

    # ======================================================
    # BRAIN ENGINE TEST
    # ======================================================

    def test_brain(self):

        print()

        print("Initializing Brain Engine...")

        from unittest.mock import MagicMock

        from desktop_agent.brain.orchestrator.orchestrator import (
            Orchestrator,
        )

        from desktop_agent.brain.brain_engine import (
            BrainEngine,
        )

        # -----------------------------------------
        # Fake Dispatcher
        # -----------------------------------------

        dispatcher = MagicMock()

        dispatcher.dispatch.return_value = MagicMock(
            ok=True,
            tool="diagnostic",
            error=None,
        )

        # -----------------------------------------
        # Orchestrator
        # -----------------------------------------

        orchestrator = Orchestrator(

            dispatcher=dispatcher,

        )

        # -----------------------------------------
        # Brain
        # -----------------------------------------

        brain = BrainEngine(

            orchestrator=orchestrator,

        )

        assert brain is not None

        print("Brain Initialized")

        print("Brain Type :", type(brain).__name__)

        print("Orchestrator OK")

    # ======================================================
    # THINKING TEST
    # ======================================================

    def test_thinking(self):

        print()

        print("Testing Thinking Engine...")

        from desktop_agent.brain.blackboard.blackboard import Blackboard

        from desktop_agent.brain.thinking.thinking_engine import (

            ThinkingEngine,

        )

        from desktop_agent.brain.thinking.confidence_engine import (

            ConfidenceItem,

            ConfidenceSource,

        )

        bb = Blackboard()

        thinking = ThinkingEngine(

            blackboard=bb,

        )

        result = thinking.think(

            observation="Open VS Code",

            required_fields={

                "application": "VS Code",

            },

            confidence_inputs=[

                ConfidenceItem(

                    source=ConfidenceSource.INTENT,

                    score=0.95,

                    explanation="Intent",

                )

            ],

        )

        assert result is not None

        print("Thinking Engine OK")

    # ======================================================
    # PLANNER TEST
    # ======================================================

    def test_planner(self):

        print()

        print("Testing Planner...")

        from desktop_agent.brain.blackboard.blackboard import Blackboard

        from desktop_agent.brain.planner.planner import Planner

        planner = Planner(

            blackboard=Blackboard(),

        )

        assert planner is not None

        print("Planner Initialized")

    # ======================================================
    # REFLECTION TEST
    # ======================================================

    def test_reflection(self):

        print()

        print("Testing Reflection...")

        from desktop_agent.brain.blackboard.blackboard import Blackboard

        from desktop_agent.brain.working_memory.working_memory import (

            WorkingMemory,

        )

        from desktop_agent.brain.reflection.reflection_engine import (

            ReflectionEngine,

        )

        reflection = ReflectionEngine(

            working_memory=WorkingMemory(),

            blackboard=Blackboard(),

        )

        reflection.record(

            action="Test",

            success=True,

            message="Diagnostic",

        )

        assert reflection.last() is not None

        print("Reflection OK")

    # ======================================================
    # KNOWLEDGE TEST
    # ======================================================

    def test_knowledge(self):

        print()

        print("Testing Knowledge System...")
        

        from desktop_agent.brain.knowledge.providers.tavily_provider import (
            TavilyProvider,
        )

        from desktop_agent.config.settings import TAVILY_API_KEY

        api_key = TAVILY_API_KEY

        if not api_key:

            raise RuntimeError(

                "TAVILY_API_KEY environment variable not found."

            )

        provider = TavilyProvider(

            api_key=api_key,

        )

        provider = TavilyProvider(
            api_key=api_key,
        )

        print("[PASS] Tavily Provider Created")

        try:

            from desktop_agent.brain.knowledge.models.knowledge_request import (
                KnowledgeRequest,
            )

            request = KnowledgeRequest(

                query="What is artificial intelligence?",

                max_sources=2,

            )

            result = provider.search(

                request,

            )

            if result.success:

                print("[PASS] Tavily Search")

                print()

                print("Answer:")

                print(result.answer[:200])

            else:

                raise RuntimeError(

                    result.metadata.get(

                        "error",

                        "Unknown Tavily Error",

                    )

                )

        except Exception as e:

            raise RuntimeError(

                f"Tavily Search Failed: {e}"

            )

        print()

        print("Knowledge Provider OK")

    # ======================================================
    # EXECUTION COORDINATOR
    # ======================================================

    def test_execution(self):

        print()

        print("Testing Execution Coordinator...")

        from desktop_agent.brain.executive.execution_monitor import (
            ExecutionMonitor,
        )

        from desktop_agent.brain.executive.execution_verifier import (
            ExecutionVerifier,
        )

        from desktop_agent.brain.executive.retry_manager import (
            RetryManager,
        )

        from desktop_agent.brain.executive.recovery_manager import (
            RecoveryManager,
        )

        from desktop_agent.brain.executive.execution_coordinator import (
            ExecutionCoordinator,
        )

        coordinator = ExecutionCoordinator(

            execution_monitor=ExecutionMonitor(),

            execution_verifier=ExecutionVerifier(),

            retry_manager=RetryManager(),

            recovery_manager=RecoveryManager(),

        )

        assert coordinator is not None

        print("Execution Coordinator OK")

    # ======================================================
    # ORCHESTRATOR
    # ======================================================

    def test_orchestrator(self):

        print()

        print("Testing Orchestrator...")

        from unittest.mock import MagicMock

        from desktop_agent.brain.orchestrator.orchestrator import (
            Orchestrator,
        )

        dispatcher = MagicMock()

        dispatcher.dispatch.return_value = None

        orchestrator = Orchestrator(

            dispatcher=dispatcher,

        )

        assert orchestrator is not None

        print("Orchestrator OK")

    # ======================================================
    # WORKING MEMORY
    # ======================================================

    def test_working_memory(self):

        print()

        print("Testing Working Memory...")

        from desktop_agent.brain.working_memory.working_memory import (
            WorkingMemory,
        )

        wm = WorkingMemory()

        assert wm is not None

        print("Working Memory Initialized")

def main():

    diag = MyraaDiagnostic()

    diag.banner()

    diag.run_test(

        "Python",

        diag.test_python,

    )

    diag.run_test(

        "Operating System",

        diag.test_os,

    )

    diag.run_test(

        "CPU",

        diag.test_cpu,

    )

    diag.run_test(

        "RAM",

        diag.test_ram,

    )

    diag.run_test(

        "Project Structure",

        diag.test_project,

    )

    diag.run_test(

        "Imports",

        diag.test_imports,

    )

    diag.run_test(

        "Blackboard",

        diag.test_blackboard,

    )

    diag.run_test(

        "Memory",

        diag.test_memory,

    )

    diag.run_test(

        "Brain",

        diag.test_brain,

    )

    diag.run_test(

        "Thinking",

        diag.test_thinking,

    )

    diag.run_test(

        "Planner",

        diag.test_planner,

    )

    diag.run_test(

        "Reflection",

        diag.test_reflection,

    )

    diag.run_test(

        "Knowledge",

        diag.test_knowledge,

    )

    diag.run_test(

        "Execution",

        diag.test_execution,

    )

    diag.run_test(

        "Orchestrator",

        diag.test_orchestrator,

    )

    diag.run_test(

        "Working Memory",

        diag.test_working_memory,

    )
    diag.summary()


if __name__ == "__main__":

    main()


