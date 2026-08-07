from pathlib import Path

from desktop_agent.brain.knowledge.analyzer.module_analyzer import ModuleAnalyzer
from desktop_agent.brain.knowledge.projects.workspace_module_detector import WorkspaceModuleDetector

class ModuleIndexer:

    def __init__(self, db):

        self.db = db
        self.detector = WorkspaceModuleDetector()
        self.analyzer = ModuleAnalyzer()
    def index(self, workspace_name: str, workspace: Path):

        modules = self.detector.discover(workspace)

        for folder in modules:

            info = self.analyzer.analyze(
                workspace_name,
                folder,
            )

            self.db.save_module(info)

            print(
                f"Indexed module: {info.name}"
            )
    