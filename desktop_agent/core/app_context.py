from desktop_agent.core.service_registry import ServiceRegistry

# DO NOT instantiate heavy services at module level
# They will be created on-demand via lazy initialization

registry = ServiceRegistry()

_knowledge_db = None
_search_engine = None
_index_manager = None
_knowledge_manager = None
_project_context = None
_project_brain = None


def get_knowledge_db():
    """Lazy initialization of KnowledgeDB."""
    global _knowledge_db
    if _knowledge_db is None:
        from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
        _knowledge_db = KnowledgeDB()
        registry.register("knowledge_db", _knowledge_db)
    return _knowledge_db


def get_search_engine():
    """Lazy initialization of SearchEngine."""
    global _search_engine
    if _search_engine is None:
        from desktop_agent.brain.knowledge.search.search_engine import SearchEngine
        _search_engine = SearchEngine(get_knowledge_db())
        registry.register("knowledge_search", _search_engine)
    return _search_engine


def get_index_manager():
    """Lazy initialization of IndexManager (starts background worker)."""
    global _index_manager
    if _index_manager is None:
        from desktop_agent.brain.knowledge.indexer.index_manager import IndexManager
        _index_manager = IndexManager(get_knowledge_db())
        registry.register("knowledge_indexer", _index_manager)
    return _index_manager


def get_knowledge_manager():
    """Lazy initialization of KnowledgeManager."""
    global _knowledge_manager
    if _knowledge_manager is None:
        from desktop_agent.brain.knowledge.services.knowledge_manager import KnowledgeManager
        _knowledge_manager = KnowledgeManager(
            db=get_knowledge_db(),
            search=get_search_engine(),
            indexer=get_index_manager(),
        )
        registry.register("knowledge_manager", _knowledge_manager)
    return _knowledge_manager


def get_project_context():
    """Lazy initialization of ProjectContextService."""
    global _project_context
    if _project_context is None:
        from desktop_agent.brain.knowledge.services.project_context_service import (
            ProjectContextService,
        )
        _project_context = ProjectContextService(
            knowledge_manager=get_knowledge_manager(),
        )
        registry.register("project_context", _project_context)
    return _project_context


def get_project_brain():
    """Lazy initialization of ProjectBrain."""
    global _project_brain
    if _project_brain is None:
        from desktop_agent.brain.knowledge.services.project_brain import ProjectBrain
        _project_brain = ProjectBrain(
            project_context=get_project_context(),
        )
        registry.register("project_brain", _project_brain)
    return _project_brain


# Backward compatibility: provide module-level accessors that return lazy instances
# Code that imports these will get the lazy-initialized versions
def __getattr__(name):
    """Module-level lazy attribute access for backward compatibility."""
    if name == "knowledge_db":
        return get_knowledge_db()
    elif name == "search_engine":
        return get_search_engine()
    elif name == "index_manager":
        return get_index_manager()
    elif name == "knowledge_manager":
        return get_knowledge_manager()
    elif name == "project_context":
        return get_project_context()
    elif name == "project_brain":
        return get_project_brain()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")