"""
MYRAA Knowledge Search Engine
"""

from __future__ import annotations

from ..database.knowledge_db import KnowledgeDB
from ..models import SearchResult


class SearchEngine:

    def __init__(self, db: KnowledgeDB):

        self.db = db

    # -----------------------------------------------------

    def search_files(
        self,
        query: str,
        limit: int = 20,
    ):

        cursor = self.db.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM files
            WHERE
                name LIKE ?
                OR path LIKE ?
            LIMIT ?
            """,
            (
                f"%{query}%",
                f"%{query}%",
                limit,
            ),
        )

        rows = cursor.fetchall()

        results = []

        for row in rows:

            results.append(

                SearchResult(
                    score=1.0,
                    path=row["path"],
                    title=row["name"],
                )

            )

        return results


    # -----------------------------------------------------

    def search_projects(
        self,
        query: str,
        limit: int = 10,
    ):

        cursor = self.db.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM projects
            WHERE
                name LIKE ?
                OR root LIKE ?
            LIMIT ?
            """,
            (
                f"%{query}%",
                f"%{query}%",
                limit,
            ),
        )

        rows = cursor.fetchall()

        results = []

        for row in rows:

            results.append(
                SearchResult(
                    score=1.0,
                    path=row["root"],
                    title=row["name"],
                    metadata={
                        "type": "project",
                    },
                )
            )

        return results