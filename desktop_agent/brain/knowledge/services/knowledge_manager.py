from __future__ import annotations

from pathlib import Path

from ..database.knowledge_db import KnowledgeDB
from ..indexer.index_manager import IndexManager
from ..search.search_engine import SearchEngine


class KnowledgeManager:

    def __init__(
        self,
        db,
        search,
        indexer,
    ):
        self.db = db
        self.search = search
        self.indexer = indexer

    # --------------------------------------------------

    def index(self, root: str | Path):

        self.indexer.index_path(root)

    # --------------------------------------------------

    def find(self, query: str):

        return self.search.search_files(query)

    # --------------------------------------------------

    def find_project(self, query: str):

        return self.search.search_projects(query)


    # --------------------------------------------------

    def find_file(self, query: str):

        return self.search.search_files(query)


    # --------------------------------------------------

    def exists(self, query: str) -> bool:

        return len(self.search.search_files(query, limit=1)) > 0