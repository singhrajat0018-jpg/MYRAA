"""Phase H — Personal World Model + Digital Life Intelligence Tests.

Coverage:
- Entity CRUD + dedup
- Relationships + traverse + path
- Temporal state + history + diff
- Events + ingestion + dedup
- Memory 2.0 integration
- Goal/project awareness
- Application/browser state
- Privacy + permissions
- Conflict detection
- Proactive intelligence
- Context packaging
- Persistence + recovery
- Performance benchmarks
"""

import time
import threading
import pytest
from unittest.mock import MagicMock

from desktop_agent.world_model.entity import Entity, EntityType, EntityState, EntitySource, EntityScope
from desktop_agent.world_model.relationship import Relationship, RelationshipType, RelationshipGraph
from desktop_agent.world_model.temporal import TemporalState, TimelineEntry, TemporalPhase
from desktop_agent.world_model.events import WorldEvent, EventType, EventIngestor
from desktop_agent.world_model.model import WorldModel
from desktop_agent.world_model.query import WorldQueryEngine
from desktop_agent.world_model.privacy import DataClassification, PrivacyGate
from desktop_agent.world_model.context import WorldContext, ContextPackager
from desktop_agent.world_model.persistence import WorldModelPersistence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_world_model():
    """Reset WorldModel singleton before each test."""
    WorldModel.reset_instance()
    yield
    WorldModel.reset_instance()


@pytest.fixture
def wm():
    """Fresh WorldModel instance."""
    return WorldModel()


@pytest.fixture
def graph():
    """Fresh RelationshipGraph."""
    return RelationshipGraph()


@pytest.fixture
def temporal():
    """Fresh TemporalState."""
    return TemporalState()


@pytest.fixture
def events():
    """Fresh EventIngestor."""
    return EventIngestor()


# ============================================================
# 1. ENTITY CRUD
# ============================================================

class TestEntityCRUD:
    def test_create_entity(self, wm):
        e = wm.create_entity(EntityType.PROJECT, "MYRAA", state=EntityState.ACTIVE)
        assert e.name == "MYRAA"
        assert e.type == EntityType.PROJECT
        assert e.state == EntityState.ACTIVE
        assert e.id in [ent.id for ent in wm.find_entity(EntityType.PROJECT)]

    def test_get_entity(self, wm):
        e = wm.create_entity(EntityType.TASK, "Phase H")
        fetched = wm.get_entity(e.id)
        assert fetched is not None
        assert fetched.name == "Phase H"

    def test_update_entity(self, wm):
        e = wm.create_entity(EntityType.TASK, "Bug fix")
        ok = wm.update_entity(e.id, state=EntityState.COMPLETED, description="Fixed")
        assert ok is True
        updated = wm.get_entity(e.id)
        assert updated.state == EntityState.COMPLETED
        assert updated.description == "Fixed"

    def test_delete_entity(self, wm):
        e = wm.create_entity(EntityType.FILE, "temp.txt")
        ok = wm.delete_entity(e.id)
        assert ok is True
        assert wm.get_entity(e.id) is None

    def test_delete_nonexistent(self, wm):
        ok = wm.delete_entity("nonexistent")
        assert ok is False

    def test_find_entity_by_type(self, wm):
        wm.create_entity(EntityType.TASK, "Task 1")
        wm.create_entity(EntityType.TASK, "Task 2")
        wm.create_entity(EntityType.PROJECT, "Project 1")
        tasks = wm.find_entity(entity_type=EntityType.TASK)
        assert len(tasks) == 2

    def test_find_entity_by_state(self, wm):
        wm.create_entity(EntityType.TASK, "Active", state=EntityState.ACTIVE)
        wm.create_entity(EntityType.TASK, "Blocked", state=EntityState.BLOCKED)
        blocked = wm.find_entity(entity_type=EntityType.TASK, state=EntityState.BLOCKED)
        assert len(blocked) == 1
        assert blocked[0].name == "Blocked"

    def test_find_entity_by_name(self, wm):
        wm.create_entity(EntityType.APPLICATION, "VS Code")
        found = wm.find_entity(name="VS Code")
        assert len(found) == 1

    def test_entity_to_dict_roundtrip(self):
        e = Entity.create(EntityType.STOCK, "RELIANCE", source=EntitySource.USER_INPUT)
        d = e.to_dict()
        e2 = Entity.from_dict(d)
        assert e2.id == e.id
        assert e2.type == EntityType.STOCK
        assert e2.name == "RELIANCE"

    def test_entity_stale_detection(self):
        e = Entity.create(EntityType.FILE, "old.py")
        e.updated_at = time.time() - 7200  # 2 hours ago
        assert e.is_stale(max_age_seconds=3600) is True
        assert e.is_stale(max_age_seconds=10000) is False

    def test_entity_freshness_decay(self):
        e = Entity.create(EntityType.TASK, "Task")
        e.updated_at = time.time() - 86400  # 1 day ago
        e.decay_freshness(half_life_seconds=86400)
        assert 0.3 < e.freshness < 0.7  # ~50% after 1 half-life

    def test_entity_metadata(self, wm):
        e = wm.create_entity(
            EntityType.WORKFLOW,
            "Deploy Pipeline",
            metadata={"steps": 5, "avg_duration_s": 120},
        )
        assert e.metadata["steps"] == 5


# ============================================================
# 2. RELATIONSHIPS
# ============================================================

class TestRelationships:
    def test_create_relationship(self, wm):
        p = wm.create_entity(EntityType.PROJECT, "MYRAA")
        t = wm.create_entity(EntityType.TASK, "Phase H")
        rel = wm.create_relationship(p.id, t.id, RelationshipType.CONTAINS)
        assert rel.source_id == p.id
        assert rel.target_id == t.id

    def test_graph_outgoing(self, graph):
        e1 = Entity.create(EntityType.PROJECT, "P1")
        e2 = Entity.create(EntityType.TASK, "T1")
        e3 = Entity.create(EntityType.TASK, "T2")
        graph.create(e1.id, e2.id, RelationshipType.CONTAINS)
        graph.create(e1.id, e3.id, RelationshipType.CONTAINS)
        out = graph.outgoing(e1.id)
        assert len(out) == 2

    def test_graph_incoming(self, graph):
        e1 = Entity.create(EntityType.PROJECT, "P1")
        e2 = Entity.create(EntityType.TASK, "T1")
        graph.create(e1.id, e2.id, RelationshipType.CONTAINS)
        inc = graph.incoming(e2.id)
        assert len(inc) == 1
        assert inc[0].source_id == e1.id

    def test_graph_neighbors(self, graph):
        e1 = Entity.create(EntityType.PROJECT, "P1")
        e2 = Entity.create(EntityType.TASK, "T1")
        e3 = Entity.create(EntityType.FILE, "F1")
        graph.create(e1.id, e2.id, RelationshipType.CONTAINS)
        graph.create(e2.id, e3.id, RelationshipType.USES)
        n = graph.neighbors(e1.id)
        assert e2.id in n

    def test_graph_traverse_bfs(self, graph):
        e1 = Entity.create(EntityType.PROJECT, "P1")
        e2 = Entity.create(EntityType.TASK, "T1")
        e3 = Entity.create(EntityType.FILE, "F1")
        graph.create(e1.id, e2.id, RelationshipType.CONTAINS)
        graph.create(e2.id, e3.id, RelationshipType.USES)
        result = graph.traverse_bfs(e1.id, max_depth=5)
        ids = [eid for eid, _ in result]
        assert e1.id in ids
        assert e2.id in ids
        assert e3.id in ids

    def test_graph_find_path(self, graph):
        e1 = Entity.create(EntityType.PROJECT, "P1")
        e2 = Entity.create(EntityType.TASK, "T1")
        e3 = Entity.create(EntityType.FILE, "F1")
        graph.create(e1.id, e2.id, RelationshipType.CONTAINS)
        graph.create(e2.id, e3.id, RelationshipType.USES)
        path = graph.find_path(e1.id, e3.id)
        assert path is not None
        assert path[0] == e1.id
        assert path[-1] == e3.id

    def test_graph_dependencies(self, graph):
        t1 = Entity.create(EntityType.TASK, "T1")
        t2 = Entity.create(EntityType.TASK, "T2")
        graph.create(t1.id, t2.id, RelationshipType.DEPENDS_ON)
        deps = graph.dependencies_of(t1.id)
        assert t2.id in deps

    def test_graph_dependents(self, graph):
        t1 = Entity.create(EntityType.TASK, "T1")
        t2 = Entity.create(EntityType.TASK, "T2")
        graph.create(t1.id, t2.id, RelationshipType.DEPENDS_ON)
        deps = graph.dependents_of(t2.id)
        assert t1.id in deps

    def test_graph_delete_relationship(self, graph):
        e1 = Entity.create(EntityType.PROJECT, "P1")
        e2 = Entity.create(EntityType.TASK, "T1")
        rel = graph.create(e1.id, e2.id, RelationshipType.CONTAINS)
        ok = graph.delete(rel.id)
        assert ok is True
        assert graph.count() == 0

    def test_graph_by_type(self, graph):
        e1 = Entity.create(EntityType.PROJECT, "P1")
        e2 = Entity.create(EntityType.TASK, "T1")
        e3 = Entity.create(EntityType.FILE, "F1")
        graph.create(e1.id, e2.id, RelationshipType.CONTAINS)
        graph.create(e1.id, e3.id, RelationshipType.USES)
        contains = graph.by_type(RelationshipType.CONTAINS)
        assert len(contains) == 1

    def test_relationship_to_dict_roundtrip(self):
        rel = Relationship(
            id="r1", source_id="s1", target_id="t1",
            type=RelationshipType.USES, weight=0.8,
        )
        d = rel.to_dict()
        rel2 = Relationship.from_dict(d)
        assert rel2.id == "r1"
        assert rel2.weight == 0.8


# ============================================================
# 3. TEMPORAL STATE
# ============================================================

class TestTemporalState:
    def test_record_and_query(self, temporal):
        temporal.record("entity1", "active")
        temporal.record("entity1", "blocked")
        current = temporal.current_state("entity1")
        assert current.state == "blocked"

    def test_history(self, temporal):
        temporal.record("e1", "active", timestamp=100.0)
        temporal.record("e1", "blocked", timestamp=200.0)
        temporal.record("e1", "completed", timestamp=300.0)
        h = temporal.history("e1", limit=2)
        assert len(h) == 2
        assert h[-1].state == "completed"

    def test_diff(self, temporal):
        temporal.record("e1", "active", timestamp=100.0)
        temporal.record("e1", "blocked", timestamp=200.0)
        d = temporal.diff("e1", 100.0, 200.0)
        assert d is not None
        assert d["state_at_a"] == "active"
        assert d["state_at_b"] == "blocked"
        assert d["changed"] is True

    def test_what_changed_since(self, temporal):
        now = time.time()
        temporal.record("e1", "active", timestamp=now - 100)
        temporal.record("e2", "blocked", timestamp=now - 50)
        changes = temporal.what_changed_since(now - 80)
        assert len(changes) == 1
        assert changes[0]["entity_id"] == "e2"

    def test_stale_entities(self, temporal):
        temporal.record("e1", "active", timestamp=time.time() - 7200)
        stale = temporal.stale_entities(max_age_seconds=3600)
        assert len(stale) == 1
        assert stale[0]["entity_id"] == "e1"

    def test_temporal_phase_default(self):
        now = time.time()
        entry = TimelineEntry("e1", "done", now)
        assert entry.phase == TemporalPhase.PRESENT  # default

    def test_temporal_phase_explicit(self):
        entry = TimelineEntry("e1", "done", time.time(), phase=TemporalPhase.PAST)
        assert entry.phase == TemporalPhase.PAST

    def test_all_current_states(self, temporal):
        temporal.record("e1", "active")
        temporal.record("e2", "blocked")
        states = temporal.all_current_states()
        assert states["e1"] == "active"
        assert states["e2"] == "blocked"


# ============================================================
# 4. EVENTS
# ============================================================

class TestEvents:
    def test_ingest_event(self, events):
        evt = WorldEvent(
            id="e1",
            type=EventType.ENTITY_CREATED,
            entity_id="ent1",
            timestamp=time.time(),
            importance=0.6,
        )
        ok = events.ingest(evt)
        assert ok is True
        assert len(events.recent()) == 1

    def test_dedup(self, events):
        now = time.time()
        evt1 = WorldEvent(id="e1", type=EventType.ENTITY_CREATED, entity_id="ent1", timestamp=now, importance=0.6)
        evt2 = WorldEvent(id="e2", type=EventType.ENTITY_CREATED, entity_id="ent1", timestamp=now, importance=0.6)
        events.ingest(evt1)
        ok = events.ingest(evt2)
        assert ok is False  # deduped

    def test_importance_filter(self, events):
        evt = WorldEvent(id="e1", type=EventType.ENTITY_CREATED, entity_id="ent1", timestamp=time.time(), importance=0.01)
        ok = events.ingest(evt)
        assert ok is False  # filtered

    def test_subscribe(self, events):
        received = []
        events.subscribe(EventType.ENTITY_CREATED.value, lambda e: received.append(e))
        evt = WorldEvent(id="e1", type=EventType.ENTITY_CREATED, entity_id="ent1", timestamp=time.time(), importance=0.6)
        events.ingest(evt)
        assert len(received) == 1

    def test_by_entity(self, events):
        events.ingest(WorldEvent(id="e1", type=EventType.ENTITY_CREATED, entity_id="ent1", timestamp=time.time(), importance=0.6))
        events.ingest(WorldEvent(id="e2", type=EventType.ENTITY_UPDATED, entity_id="ent1", timestamp=time.time(), importance=0.5))
        events.ingest(WorldEvent(id="e3", type=EventType.ENTITY_CREATED, entity_id="ent2", timestamp=time.time(), importance=0.6))
        by_ent = events.by_entity("ent1")
        assert len(by_ent) == 2

    def test_stats(self, events):
        events.ingest(WorldEvent(id="e1", type=EventType.ENTITY_CREATED, entity_id="ent1", timestamp=time.time(), importance=0.6))
        stats = events.stats()
        assert stats["total_ingested"] == 1


# ============================================================
# 5. WORLD MODEL INTEGRATION
# ============================================================

class TestWorldModelIntegration:
    def test_full_lifecycle(self, wm):
        """Test create → relate → update → query → delete lifecycle."""
        # Create
        project = wm.create_entity(EntityType.PROJECT, "MYRAA")
        task = wm.create_entity(EntityType.TASK, "Phase H", state=EntityState.ACTIVE)
        file = wm.create_entity(EntityType.FILE, "model.py")

        # Relate
        wm.create_relationship(project.id, task.id, RelationshipType.CONTAINS)
        wm.create_relationship(task.id, file.id, RelationshipType.USES)

        # Update
        wm.update_entity(task.id, state=EntityState.COMPLETED)

        # Query
        q = wm.query
        blocked = q.query_blocked()
        assert len(blocked) == 0

        active = q.query_active()
        assert len(active) >= 1

        deps = q.query_dependencies(task.id)
        assert len(deps["depends_on"]) == 0

        path = q.query_path(project.id, file.id)
        assert path is not None
        assert len(path["path"]) == 3

        # Delete
        wm.delete_entity(file.id)
        assert wm.get_entity(file.id) is None

    def test_context_packaging(self, wm):
        """Test context for user request."""
        wm.create_entity(EntityType.PROJECT, "MYRAA", state=EntityState.ACTIVE)
        wm.create_entity(EntityType.TASK, "World Model", state=EntityState.ACTIVE)

        ctx = wm.context_for_request("What am I working on?")
        assert ctx.what != ""
        assert ctx.confidence > 0

    def test_health(self, wm):
        wm.create_entity(EntityType.PROJECT, "Test")
        h = wm.health()
        assert h["entity_count"] == 1
        assert h["relationship_count"] == 0

    def test_repair(self, wm):
        wm.create_entity(EntityType.TASK, "T1")
        r = wm.repair()
        assert "entity_count" in r
        assert r["entity_count"] == 1


# ============================================================
# 6. PRIVACY
# ============================================================

class TestPrivacy:
    def test_classify(self):
        pg = PrivacyGate()
        assert pg.classify("system", {}) == DataClassification.PUBLIC
        assert pg.classify("trading_account", {}) == DataClassification.SENSITIVE
        assert pg.classify("task", {}) == DataClassification.PRIVATE

    def test_reject_secrets(self):
        pg = PrivacyGate()
        ok, reason = pg.reject_secrets({"api_key": "secret123"})
        assert ok is False
        assert "credential" in reason.lower()

    def test_accept_non_secrets(self):
        pg = PrivacyGate()
        ok, reason = pg.reject_secrets({"name": "MYRAA", "steps": 5})
        assert ok is True

    def test_freeze_entity(self):
        pg = PrivacyGate()
        pg.freeze_entity("e1")
        assert pg.check_permission("e1", "update") is False
        assert pg.check_permission("e1", "read") is True

    def test_restrict_entity(self):
        pg = PrivacyGate()
        pg.restrict_entity("e1")
        assert pg.check_permission("e1", "read") is True
        assert pg.check_permission("e1", "update") is False

    def test_user_correction(self):
        pg = PrivacyGate()
        pg.apply_user_correction("e1", "language", "Hinglish")
        assert pg.get_correction("e1", "language") == "Hinglish"

    def test_secret_rejection_in_entity(self, wm):
        with pytest.raises(ValueError, match="credential"):
            wm.create_entity(
                EntityType.SYSTEM,
                "Config",
                metadata={"password": "secret123"},
            )


# ============================================================
# 7. QUERY ENGINE
# ============================================================

class TestQueryEngine:
    def test_query_by_type(self, wm):
        wm.create_entity(EntityType.TASK, "T1")
        wm.create_entity(EntityType.TASK, "T2")
        wm.create_entity(EntityType.PROJECT, "P1")
        q = wm.query
        tasks = q.query_by_type(EntityType.TASK)
        assert len(tasks) == 2

    def test_query_blocked(self, wm):
        wm.create_entity(EntityType.TASK, "Blocked", state=EntityState.BLOCKED)
        wm.create_entity(EntityType.TASK, "Active")
        blocked = wm.query.query_blocked()
        assert len(blocked) == 1

    def test_query_natural(self, wm):
        wm.create_entity(EntityType.TASK, "Active", state=EntityState.ACTIVE)
        wm.create_entity(EntityType.TASK, "Blocked", state=EntityState.BLOCKED)
        q = wm.query
        result = q.query_natural("What is blocked?")
        assert "blocked" in result["answer"].lower() or len(result["blocked"]) > 0

    def test_query_high_importance(self, wm):
        e1 = wm.create_entity(EntityType.TASK, "Important", confidence=0.9)
        e2 = wm.create_entity(EntityType.TASK, "Low", confidence=0.2)
        wm.update_entity(e1.id, freshness=0.9)
        wm.update_entity(e2.id, freshness=0.2)
        high = wm.query.query_high_importance(min_importance=0.8)
        assert len(high) == 1


# ============================================================
# 8. PERSISTENCE
# ============================================================

class TestPersistence:
    def test_save_and_load(self, wm):
        wm.create_entity(EntityType.PROJECT, "MYRAA")
        wm.create_entity(EntityType.TASK, "Phase H")
        ok = wm.save()
        assert ok is True

        # Reset and load
        WorldModel.reset_instance()
        wm2 = WorldModel()
        ok = wm2.load()
        assert ok is True
        assert wm2.health()["entity_count"] == 2

    def test_persistence_roundtrip(self):
        p = WorldModelPersistence()
        entities = [
            {"id": "e1", "type": "task", "name": "T1", "state": "active",
             "created_at": time.time(), "updated_at": time.time(),
             "source": "system", "confidence": 1.0, "freshness": 1.0,
             "scope": "private", "tags": [], "metadata": {}, "description": ""},
        ]
        ok = p.save_entities(entities)
        assert ok is True
        loaded = p.load_entities()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "T1"


# ============================================================
# 9. THREAD SAFETY
# ============================================================

class TestThreadSafety:
    def test_concurrent_create(self, wm):
        """Test concurrent entity creation."""
        errors = []

        def create_entity(i):
            try:
                wm.create_entity(EntityType.TASK, f"Task {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_entity, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert wm.health()["entity_count"] == 20

    def test_concurrent_read_write(self, wm):
        wm.create_entity(EntityType.TASK, "Shared")
        errors = []

        def read_entity():
            try:
                for _ in range(10):
                    wm.find_entity(EntityType.TASK)
            except Exception as e:
                errors.append(e)

        def write_entity(i):
            try:
                wm.create_entity(EntityType.TASK, f"New {i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=read_entity))
            threads.append(threading.Thread(target=write_entity, args=(i,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ============================================================
# 10. PERFORMANCE
# ============================================================

class TestPerformance:
    def test_entity_query_speed(self, wm):
        """Entity query should be <5ms."""
        for i in range(100):
            wm.create_entity(EntityType.TASK, f"Task {i}", state=EntityState.ACTIVE if i % 2 == 0 else EntityState.PENDING)

        start = time.perf_counter()
        wm.find_entity(EntityType.TASK, state=EntityState.ACTIVE)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5, f"Query took {elapsed_ms:.2f}ms"

    def test_relationship_lookup_speed(self, wm):
        """Relationship lookup should be <10ms."""
        e1 = wm.create_entity(EntityType.PROJECT, "P1")
        for i in range(50):
            t = wm.create_entity(EntityType.TASK, f"T{i}")
            wm.create_relationship(e1.id, t.id, RelationshipType.CONTAINS)

        start = time.perf_counter()
        wm.query.query_relationships(e1.id, direction="outgoing")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 10, f"Lookup took {elapsed_ms:.2f}ms"

    def test_context_packaging_speed(self, wm):
        """Context packaging should be <20ms."""
        wm.create_entity(EntityType.PROJECT, "MYRAA", state=EntityState.ACTIVE)
        wm.create_entity(EntityType.TASK, "Phase H", state=EntityState.ACTIVE)
        wm.create_entity(EntityType.TASK, "Bug fix", state=EntityState.BLOCKED)

        start = time.perf_counter()
        wm.context_for_request("What am I working on?")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 20, f"Context took {elapsed_ms:.2f}ms"

    def test_event_ingestion_speed(self, wm):
        """Event ingestion should be <10ms."""
        start = time.perf_counter()
        for i in range(100):
            wm.ingest_event(WorldEvent(
                id=f"e{i}",
                type=EventType.ENTITY_UPDATED,
                entity_id=f"ent{i % 10}",
                timestamp=time.time(),
                importance=0.5,
            ))
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, f"100 events took {elapsed_ms:.2f}ms"


# ============================================================
# 11. GOAL / PROJECT INTELLIGENCE
# ============================================================

class TestGoalProjectIntelligence:
    def test_goal_tracking(self, wm):
        g = wm.create_entity(EntityType.GOAL, "Build World Model", state=EntityState.ACTIVE)
        t1 = wm.create_entity(EntityType.TASK, "Entity System", state=EntityState.COMPLETED)
        t2 = wm.create_entity(EntityType.TASK, "Relationship Graph", state=EntityState.ACTIVE)

        wm.create_relationship(g.id, t1.id, RelationshipType.CONTAINS)
        wm.create_relationship(g.id, t2.id, RelationshipType.CONTAINS)
        wm.create_relationship(t2.id, t1.id, RelationshipType.DEPENDS_ON)

        q = wm.query
        deps = q.query_dependencies(t2.id)
        assert t1.id in [d.get("id") or d for d in deps["depends_on"] if isinstance(d, dict)]

    def test_project_files(self, wm):
        p = wm.create_entity(EntityType.PROJECT, "MYRAA")
        f1 = wm.create_entity(EntityType.FILE, "model.py")
        f2 = wm.create_entity(EntityType.FILE, "entity.py")
        wm.create_relationship(p.id, f1.id, RelationshipType.CONTAINS)
        wm.create_relationship(p.id, f2.id, RelationshipType.CONTAINS)
        outgoing = wm.query.query_relationships(p.id, direction="outgoing")
        assert len(outgoing) == 2


# ============================================================
# 12. APPLICATION / WORKSPACE
# ============================================================

class TestApplicationAwareness:
    def test_active_application(self, wm):
        app = wm.create_entity(EntityType.APPLICATION, "VS Code", state=EntityState.ACTIVE)
        wm.create_entity(EntityType.APPLICATION, "Chrome", state=EntityState.INACTIVE)
        active = wm.find_entity(entity_type=EntityType.APPLICATION, state=EntityState.ACTIVE)
        assert len(active) == 1
        assert active[0].name == "VS Code"


# ============================================================
# 13. CONFLICT DETECTION
# ============================================================

class TestConflictDetection:
    def test_state_conflict_detection(self, wm):
        e = wm.create_entity(EntityType.TASK, "T1", state=EntityState.ACTIVE)
        wm.update_entity(e.id, state=EntityState.COMPLETED)
        # Repair should detect rapid state changes
        r = wm.repair()
        assert "state_conflicts" in r


# ============================================================
# 14. PROACTIVITY
# ============================================================

class TestProactivity:
    def test_high_importance_entities(self, wm):
        e1 = wm.create_entity(EntityType.DEADLINE, "Phase H deadline", confidence=0.95)
        e2 = wm.create_entity(EntityType.REMINDER, "Low priority", confidence=0.3)
        wm.update_entity(e1.id, freshness=0.9)
        wm.update_entity(e2.id, freshness=0.2)
        high = wm.query.query_high_importance(0.8)
        assert len(high) >= 1
        assert high[0]["entity"]["name"] == "Phase H deadline"
