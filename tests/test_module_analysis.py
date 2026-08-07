from pathlib import Path

from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
from desktop_agent.brain.knowledge.indexer.module_indexer import ModuleIndexer

db = KnowledgeDB()

indexer = ModuleIndexer(db)

indexer.index(
    "MYRAA",
    Path.cwd(),
)