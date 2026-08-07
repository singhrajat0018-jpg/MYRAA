from pathlib import Path

from desktop_agent.brain.knowledge.projects.workspace_module_detector import (
    WorkspaceModuleDetector,
)

detector = WorkspaceModuleDetector()

for module in detector.discover(Path.cwd()):
    print(module.name)