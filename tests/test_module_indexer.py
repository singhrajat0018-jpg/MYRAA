from pathlib import Path

from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
from desktop_agent.brain.knowledge.indexer.module_indexer import ModuleIndexer


def test_module_indexer_discovers_and_persists_real_modules(tmp_path: Path):
    workspace = tmp_path / "workspace"
    desktop_agent = workspace / "desktop_agent"
    backend = workspace / "backend"
    ignored_tests = workspace / "tests"

    desktop_agent.mkdir(parents=True)
    backend.mkdir()
    ignored_tests.mkdir()

    (desktop_agent / "main.py").write_text("def start():\n    pass\n", encoding="utf-8")
    (desktop_agent / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (backend / "launcher.py").write_text("console.log('unused')\n", encoding="utf-8")
    (ignored_tests / "main.py").write_text("def should_ignore(): pass\n", encoding="utf-8")

    db = KnowledgeDB(tmp_path / "knowledge.db")
    indexer = ModuleIndexer(db)

    indexer.index("MYRAA", workspace)

    modules = db.get_modules()
    names = {module["name"] for module in modules}

    assert names == {"desktop_agent", "backend"}
    assert {module["workspace"] for module in modules} == {"MYRAA"}
    assert all(Path(module["root"]).is_dir() for module in modules)
    assert any("Python" in module["languages"] for module in modules)

    db.close()
