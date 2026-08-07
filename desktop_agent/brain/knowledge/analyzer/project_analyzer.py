from pathlib import Path

from .project_info import ProjectInfo
from .language_analyzer import LanguageAnalyzer
from .framework_analyzer import FrameworkAnalyzer
from .git_analyzer import GitAnalyzer
from .entrypoint_analyzer import EntryPointAnalyzer
from .file_collector import FileCollector
from .package_manager_analyzer import PackageManagerAnalyzer
from .build_tool_analyzer import BuildToolAnalyzer

class ProjectAnalyzer:

    def __init__(self):

        self.language = LanguageAnalyzer()
        self.framework = FrameworkAnalyzer()
        self.git = GitAnalyzer()
        self.entrypoint = EntryPointAnalyzer()
        self.collector = FileCollector()
        self.package_manager = PackageManagerAnalyzer()
        self.build_tool = BuildToolAnalyzer()
    # -----------------------------------------------------

    def analyze(
        self,
        folder: Path,
    ) -> ProjectInfo:

        files = self.collector.collect(folder)

        info = ProjectInfo(
            name=folder.name,
            root=str(folder),
        )

        info.languages = self.language.analyze(files)

        info.frameworks = self.framework.analyze(files)

        info.has_git = self.git.analyze(folder)

        info.dependencies = []

        info.package_managers = self.package_manager.analyze(folder)

        info.build_tools = self.build_tool.analyze(folder)

        info.confidence = 1.0

        info.entry_points = self.entrypoint.analyze(files)

        return info