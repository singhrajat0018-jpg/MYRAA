from dataclasses import dataclass
from pathlib import Path

from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
from desktop_agent.brain.knowledge.indexer.symbol_indexer import SymbolIndexer


@dataclass
class Module:
    workspace: str
    name: str
    root: str


def test_symbol_indexer_persists_symbols_from_module(tmp_path: Path, monkeypatch):
    module_root = tmp_path / "desktop_agent"
    module_root.mkdir()
    (module_root / "main.py").write_text(
        "class Assistant:\n"
        "    def speak(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "knowledge.db"

    indexer = SymbolIndexer()
    indexer.db.close()
    indexer.db = KnowledgeDB(db_path)

    total = indexer.index(Module("MYRAA", "desktop_agent", str(module_root)))
    rows = indexer.db.get_symbols()

    assert total == 2
    assert [row["name"] for row in rows] == ["Assistant", "speak"]
    assert [row["symbol_type"] for row in rows] == ["class", "method"]

    indexer.db.close()
