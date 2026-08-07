from typing import Dict

from .project_context import ProjectContext


class ProjectCache:

    def __init__(self):

        self._cache: Dict[str, ProjectContext] = {}

    def get(self, name: str):

        return self._cache.get(name.lower())

    def put(self, context: ProjectContext):

        self._cache[context.name.lower()] = context

    def clear(self):

        self._cache.clear()