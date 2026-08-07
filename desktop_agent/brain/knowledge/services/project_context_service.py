from pathlib import Path
from .project_context import ProjectContext
from .project_cache import ProjectCache

from ..analyzer.project_analyzer import ProjectAnalyzer


class ProjectContextService:

    def __init__(self, knowledge_manager):

        self.cache = ProjectCache()

        self.analyzer = ProjectAnalyzer()

        self.knowledge = knowledge_manager

    # ---------------------------------------------------------

    def get_project(self, project_name: str):

        cached = self.cache.get(project_name)

        if cached:
            return cached

        # --------------------------------------------
        # Resolve project using Knowledge Engine
        # --------------------------------------------

        results = self.knowledge.find_project(project_name)

        if not results:
            return None

        project = results[0]

        project_root = Path(project.path)

        # --------------------------------------------
        # Analyze resolved project
        # --------------------------------------------

        info = self.analyzer.analyze(project_root)

        if info is None:
            return None

        context = ProjectContext(

            name=info.name,

            root=info.root,

            languages=info.languages,

            frameworks=info.frameworks,

            dependencies=info.dependencies,

            entry_points=info.entry_points,

            package_managers=info.package_managers,

            build_tools=info.build_tools,

            has_git=info.has_git,

            git_branch=getattr(info, "git_branch", None),

            confidence=info.confidence,
        )

        self.cache.put(context)

        return context