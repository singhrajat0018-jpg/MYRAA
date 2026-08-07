from pathlib import Path

from desktop_agent.brain.knowledge.module_models.module_info import ModuleInfo

from .language_analyzer import LanguageAnalyzer
from .framework_analyzer import FrameworkAnalyzer
from .entrypoint_analyzer import EntryPointAnalyzer
from .package_manager_analyzer import PackageManagerAnalyzer
from .build_tool_analyzer import BuildToolAnalyzer
from .file_collector import FileCollector


class ModuleAnalyzer:

    def __init__(self):

        self.collector = FileCollector()

        self.language = LanguageAnalyzer()
        self.framework = FrameworkAnalyzer()
        self.entrypoint = EntryPointAnalyzer()
        self.package_manager = PackageManagerAnalyzer()
        self.build_tool = BuildToolAnalyzer()

    def analyze(self, workspace: str, folder: Path) -> ModuleInfo:

        files = self.collector.collect(folder)

        info = ModuleInfo(
            name=folder.name,
            workspace=workspace,
            root=str(folder),
        )

        info.languages = self.language.analyze(files)
        info.frameworks = self.framework.analyze(files)
        info.entry_points = self.entrypoint.analyze(files)

        info.package_managers = self.package_manager.analyze(folder)
        info.build_tools = self.build_tool.analyze(folder)

        return info