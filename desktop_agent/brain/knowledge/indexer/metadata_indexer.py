"""
MYRAA Metadata Indexer

Stores file metadata in the Knowledge Database.
"""

from __future__ import annotations

from pathlib import Path

from ..database.knowledge_db import KnowledgeDB


class MetadataIndexer:

    def __init__(self, db: KnowledgeDB):

        self.db = db

    # ---------------------------------------------------------

    def index(
        self,
        path: Path,
    ):

        try:

            stat = path.stat()

            cursor = self.db.conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO files
                (
                    path,
                    name,
                    extension,
                    size,
                    created_at,
                    modified_at,
                    parent,
                    indexed
                )
                VALUES
                (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    str(path),
                    path.name,
                    path.suffix.lower(),
                    stat.st_size,
                    stat.st_ctime,
                    stat.st_mtime,
                    str(path.parent),
                ),
            )

            self.db.conn.commit()

        except Exception as e:

            print(f"[Indexer] {path} -> {e}")