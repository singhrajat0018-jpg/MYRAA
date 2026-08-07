"""
MYRAA Knowledge Database

Persistent storage for the Knowledge Engine.
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from ..module_models.symbol_info import SymbolInfo


class KnowledgeDB:

    def __init__(self, db_path: str | Path = "data/knowledge.db"):

        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            db_path,
            check_same_thread=False
        )

        self.conn.row_factory = sqlite3.Row

        self._create_tables()

    # ---------------------------------------------------------

    def _create_tables(self):

        cursor = self.conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            path TEXT UNIQUE,

            name TEXT,

            extension TEXT,

            size INTEGER,

            created_at TEXT,

            modified_at TEXT,

            parent TEXT,

            indexed INTEGER DEFAULT 0
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS folders (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            path TEXT UNIQUE,

            name TEXT,

            parent TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT UNIQUE,

            executable TEXT,

            install_path TEXT,

            publisher TEXT,

            version TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            root TEXT UNIQUE,

            name TEXT,

            languages TEXT,

            frameworks TEXT,

            has_git INTEGER DEFAULT 0,

            confidence REAL DEFAULT 0.0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS modules (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            workspace TEXT NOT NULL,

            name TEXT NOT NULL,

            root TEXT NOT NULL UNIQUE,

            languages TEXT,

            frameworks TEXT,

            dependencies TEXT,

            entry_points TEXT,

            package_managers TEXT,

            build_tools TEXT,

            confidence REAL DEFAULT 1.0
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS symbols (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            workspace TEXT,

            module TEXT,

            file TEXT,

            name TEXT,

            symbol_type TEXT,

            language TEXT,

            line INTEGER,

            end_line INTEGER,

            parent TEXT,

            signature TEXT,

            decorators TEXT,

            imports TEXT,

            exported INTEGER,

            confidence REAL,

            UNIQUE(
                file,
                name,
                symbol_type,
                line
            )

            )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_name
        ON symbols(name)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_module
        ON symbols(module)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_type
        ON symbols(symbol_type)
        """)
        self.conn.commit()

    def get_modules(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT
                workspace,
                name,
                root,
                languages,
                frameworks,
                dependencies,
                entry_points,
                package_managers,
                build_tools,
                confidence
            FROM modules
            """
        )

        rows = cursor.fetchall()

        modules = []

        for row in rows:

            modules.append(
                {
                    "workspace": row[0],
                    "name": row[1],
                    "root": row[2],
                    "languages": json.loads(row[3]),
                    "frameworks": json.loads(row[4]),
                    "dependencies": json.loads(row[5]),
                    "entry_points": json.loads(row[6]),
                    "package_managers": json.loads(row[7]),
                    "build_tools": json.loads(row[8]),
                    "confidence": row[9],
                }
            )

        return modules

    def save_module(self, module):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO modules(
                workspace,
                name,
                root,
                languages,
                frameworks,
                dependencies,
                entry_points,
                package_managers,
                build_tools,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                module.workspace,
                module.name,
                str(module.root),
                json.dumps(module.languages),
                json.dumps(module.frameworks),
                json.dumps(module.dependencies),
                json.dumps(module.entry_points),
                json.dumps(module.package_managers),
                json.dumps(module.build_tools),
                module.confidence,
            ),
        )

        self.conn.commit()

# ---------------------------------------------------------

    def save_symbol(self, symbol: SymbolInfo):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO symbols(
                workspace,
                module,
                file,
                name,
                symbol_type,
                language,
                line,
                end_line,
                parent,
                signature,
                decorators,
                imports,
                exported,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol.workspace,
                symbol.module,
                symbol.file,
                symbol.name,
                symbol.symbol_type,
                symbol.language,
                symbol.line,
                symbol.end_line,
                symbol.parent,
                symbol.signature,
                json.dumps(symbol.decorators),
                json.dumps(symbol.imports),
                int(symbol.exported),
                symbol.confidence,
            ),
        )

        self.conn.commit()

    # ---------------------------------------------------------

    def get_symbols(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM symbols
            ORDER BY module, line
            """
        )

        return cursor.fetchall()


    # ---------------------------------------------------------

    def find_symbol(self, name: str):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM symbols
            WHERE name = ?
            """,
            (name,),
        )

        return cursor.fetchall()

    # ---------------------------------------------------------

    def close(self):

        self.conn.close()