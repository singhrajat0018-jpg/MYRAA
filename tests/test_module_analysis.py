from pathlib import Path

from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
from desktop_agent.brain.knowledge.indexer.module_indexer import ModuleIndexer


def test_module_analysis_detects_python_project_metadata(tmp_path: Path):
    workspace = tmp_path / "workspace"
    desktop_agent = workspace / "desktop_agent"
    desktop_agent.mkdir(parents=True)

    (desktop_agent / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )
    (desktop_agent / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    db = KnowledgeDB(tmp_path / "knowledge.db")
    indexer = ModuleIndexer(db)

    indexer.index("MYRAA", workspace)

    module = db.get_modules()[0]
    assert module["name"] == "desktop_agent"
    assert "Python" in module["languages"]
    assert "FastAPI" in module["frameworks"]
    assert module["package_managers"] == []

    db.close()
