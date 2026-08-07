"""
MYRAA Knowledge Engine
Index Manager

Coordinates scanning and indexing.
"""

from __future__ import annotations

from pathlib import Path

from ..database.knowledge_db import KnowledgeDB
from ..scanner.drive_scanner import DriveScanner
from .metadata_indexer import MetadataIndexer

from ..queue.event_queue import KnowledgeEventQueue
from ..queue.worker import KnowledgeWorker
from .project_indexer import ProjectIndexer

class IndexManager:

    def __init__(self, db):

        self.db = db

        self.scanner = DriveScanner()

        self.metadata = MetadataIndexer(db)

        # Create Queue
        self.queue = KnowledgeEventQueue()

        # Start Worker
        self.worker = KnowledgeWorker(
            self.queue,
            self,
        )

        self.worker.start()

        self.projects = ProjectIndexer(db)
    # ---------------------------------------------------------

    def index_path(
        self,
        root: str | Path,
    ):

        root = Path(root)

        print(f"[Knowledge] Indexing: {root}")

        indexed = 0

        for path in self.scanner.scan(root):

            self.metadata.index(path)

            self.projects.index(path)

            indexed += 1

            if indexed % 100 == 0:
                print(f"[Knowledge] Indexed {indexed}")

        print(f"[Knowledge] Finished ({indexed} items)")


