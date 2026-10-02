from pathlib import Path

from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
from desktop_agent.brain.knowledge.module_models.module_info import ModuleInfo


def test_knowledge_db_saves_and_loads_modules(tmp_path: Path):
    db = KnowledgeDB(tmp_path / "knowledge.db")

    db.save_module(
        ModuleInfo(
            workspace="MYRAA",
            name="desktop_agent",
            root=str(tmp_path / "desktop_agent"),
            languages=["Python"],
            frameworks=["FastAPI"],
            dependencies=[],
            entry_points=["main.py"],
            package_managers=["requirements.txt"],
            build_tools=[],
            confidence=1.0,
        )
    )

    assert db.get_modules() == [
        {
            "workspace": "MYRAA",
            "name": "desktop_agent",
            "root": str(tmp_path / "desktop_agent"),
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "dependencies": [],
            "entry_points": ["main.py"],
            "package_managers": ["requirements.txt"],
            "build_tools": [],
            "confidence": 1.0,
        }
    ]

    db.close()
