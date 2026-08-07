from desktop_agent.brain.blackboard.blackboard import Blackboard
from desktop_agent.brain.orchestrator.orchestrator import Orchestrator
from desktop_agent.desktop.vision.vision_manager import VisionManager
from desktop_agent.runtime.runtime_manager import RuntimeManager
from desktop_agent.brain.brain_engine import BrainEngine


def main():

    blackboard = Blackboard()

    orchestrator = Orchestrator()

    brain = BrainEngine(
        orchestrator=orchestrator,
    )

    vision = VisionManager()

    runtime = RuntimeManager(
        brain=brain,
        vision=vision,
        blackboard=blackboard,
    )

    print("\nStarting Runtime...\n")

    runtime.start()

    print(runtime.health())

    runtime.stop()

    print("\nRuntime Stopped")


if __name__ == "__main__":
    main()