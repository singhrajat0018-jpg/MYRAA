from desktop_agent.core.service_registry import ServiceRegistry

from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
from desktop_agent.brain.knowledge.search.search_engine import SearchEngine
from desktop_agent.brain.knowledge.indexer.index_manager import IndexManager
from desktop_agent.brain.knowledge.services.knowledge_manager import KnowledgeManager
from desktop_agent.brain.knowledge.services.project_context_service import (
    ProjectContextService,
)
from desktop_agent.brain.knowledge.services.project_brain import ProjectBrain


registry = ServiceRegistry()

# Shared database
knowledge_db = KnowledgeDB()

registry.register("knowledge_db", knowledge_db)

# Shared search engine
search_engine = SearchEngine(knowledge_db)

registry.register("knowledge_search", search_engine)

# Shared index manager
index_manager = IndexManager(knowledge_db)

registry.register("knowledge_indexer", index_manager)

# Knowledge manager
knowledge_manager = KnowledgeManager(
    db=knowledge_db,
    search=search_engine,
    indexer=index_manager,
)

registry.register("knowledge_manager", knowledge_manager)
# Project Context Service
project_context = ProjectContextService(
    knowledge_manager=knowledge_manager,
)

registry.register(
    "project_context",
    project_context,
)

project_brain = ProjectBrain(
    project_context=project_context,
)

registry.register(
    "project_brain",
    project_brain,
)