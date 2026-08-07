from pathlib import Path

from ..database.knowledge_db import KnowledgeDB
from ..parser.python_parser import PythonParser
from ..parser.typescript_parser import TypeScriptParser
from ..parser.javascript_parser import JavaScriptParser


class SymbolIndexer:

    def __init__(self):

        self.db = KnowledgeDB()

        self.python = PythonParser()
        self.typescript = TypeScriptParser()
        self.javascript = JavaScriptParser()

    # ---------------------------------------------------------

    def index(self, module):

        root = Path(module.root)

        total = 0

        for file in root.rglob("*"):

            if not file.is_file():
                continue

            suffix = file.suffix.lower()

            symbols = []

            # ------------------------
            # Python
            # ------------------------

            if suffix == ".py":

                parser = PythonParser()

                symbols = parser.parse(
                    module.workspace,
                    module.name,
                    file,
                )

            # ------------------------
            # TypeScript
            # ------------------------

            elif suffix in (".ts", ".tsx"):

                symbols = TypeScriptParser.parse(
                    str(file),
                    module.workspace,
                    module.name,
                )

            # ------------------------
            # JavaScript
            # ------------------------

            elif suffix in (
                ".js",
                ".jsx",
                ".mjs",
                ".cjs",
            ):

                symbols = JavaScriptParser.parse(
                    str(file),
                    module.workspace,
                    module.name,
                )

            else:
                continue

            for symbol in symbols:
                self.db.save_symbol(symbol)

            total += len(symbols)

        return total