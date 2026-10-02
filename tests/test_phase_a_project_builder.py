"""
Phase A Test Suite -- Project Builder Engine.

Uses temporary test projects only. Never manipulates user's actual projects.
"""
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from desktop_agent.brain.super_brain.project_manager import (
    ProjectManager, ProjectState, ProjectTask, ProjectMilestone,
    ProjectTaskGraph, ProjectCheckpoint, TaskStatus, MilestoneStatus,
)
from desktop_agent.brain.super_brain.project_builder_engine import (
    ProjectBuilderEngine, ProjectBuildRequest, ProjectBuildResult,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def pm():
    return ProjectManager()


@pytest.fixture
def engine():
    eng = ProjectBuilderEngine.__new__(ProjectBuilderEngine)
    eng.capability_id = "PROJECT_BUILDER"
    eng.dispatcher = MagicMock()
    eng.memory_2_0 = None
    eng.project_manager = ProjectManager()
    eng._projects_dir = Path(tempfile.mkdtemp())
    return eng


class _Goal:
    def __init__(self, text):
        self.text = text


# === 1. Project Goal Understanding ===

class TestGoalUnderstanding:
    def test_python_goal(self, engine):
        r = engine._parse_goal(_Goal("Create a Python project called my_app"), {})
        assert r.project_name == "my_app"
        assert r.project_type == "python"

    def test_web_goal(self, engine):
        r = engine._parse_goal(_Goal("Build a website called my_blog"), {})
        assert r.project_name == "my_blog"
        assert r.project_type == "web"

    def test_api_goal(self, engine):
        r = engine._parse_goal(_Goal("Create a REST API service"), {})
        assert r.project_type == "api"

    def test_continue_mode(self, engine):
        r = engine._parse_goal(_Goal("Continue my project"), {})
        assert r.mode == "continue"

    def test_debug_mode(self, engine):
        r = engine._parse_goal(_Goal("Fix the build errors"), {})
        assert r.mode == "debug"

    def test_test_mode(self, engine):
        r = engine._parse_goal(_Goal("Run tests on my project"), {})
        assert r.mode == "test"

    def test_document_mode(self, engine):
        r = engine._parse_goal(_Goal("Generate readme for my project"), {})
        assert r.mode == "document"

    def test_called_pattern(self, engine):
        r = engine._parse_goal(_Goal("Create a project called attendance_tracker"), {})
        assert r.project_name == "attendance_tracker"

    def test_build_pattern(self, engine):
        r = engine._parse_goal(_Goal("Build expense_tracker project"), {})
        assert r.project_name == "expense_tracker"


# === 2. Requirements Extraction ===

class TestRequirements:
    def test_with_requirements(self, engine):
        r = engine._parse_goal(_Goal("Create a Python project with flask and sqlalchemy"), {})
        assert len(r.requirements) > 0

    def test_multiple_requirements(self, engine):
        r = engine._parse_goal(_Goal("Create a project with auth and database and api"), {})
        assert len(r.requirements) >= 2


# === 3. Architecture Planning ===

class TestArchitecture:
    def test_python_structure(self, engine):
        s = engine._get_structure("python")
        assert "src" in s and "tests" in s and "requirements.txt" in s

    def test_web_structure(self, engine):
        s = engine._get_structure("web")
        assert "src" in s and "package.json" in s

    def test_api_structure(self, engine):
        s = engine._get_structure("api")
        assert "src" in s and "requirements.txt" in s

    def test_data_science_structure(self, engine):
        s = engine._get_structure("data_science")
        assert "notebooks" in s and "data" in s


# === 4. Scaffolding ===

class TestScaffolding:
    def test_creates_dirs(self, engine, tmp_dir):
        p = Path(tmp_dir) / "s1"
        r = engine._scaffold_project(p, ProjectBuildRequest("T", "s1", "python"))
        assert r.success and p.exists()
        assert (p / "src").exists() and (p / "tests").exists()

    def test_creates_files(self, engine, tmp_dir):
        p = Path(tmp_dir) / "s2"
        engine._scaffold_project(p, ProjectBuildRequest("T", "s2", "python"))
        assert (p / "README.md").exists()
        assert (p / ".gitignore").exists()
        assert (p / "requirements.txt").exists()

    def test_creates_main(self, engine, tmp_dir):
        p = Path(tmp_dir) / "s3"
        engine._scaffold_project(p, ProjectBuildRequest("T", "s3", "python"))
        m = p / "src" / "main.py"
        assert m.exists() and "s3" in m.read_text(encoding="utf-8")

    def test_creates_test_file(self, engine, tmp_dir):
        p = Path(tmp_dir) / "s4"
        engine._scaffold_project(p, ProjectBuildRequest("T", "s4", "python"))
        t = p / "tests" / "test_main.py"
        assert t.exists() and "test_main_runs" in t.read_text(encoding="utf-8")

    def test_web_project(self, engine, tmp_dir):
        p = Path(tmp_dir) / "s5"
        r = engine._scaffold_project(p, ProjectBuildRequest("T", "s5", "web"))
        assert r.success and (p / "src" / "index.js").exists()

    def test_api_project(self, engine, tmp_dir):
        p = Path(tmp_dir) / "s6"
        r = engine._scaffold_project(p, ProjectBuildRequest("T", "s6", "api"))
        assert r.success and (p / "requirements.txt").exists()


# === 5. File Content ===

class TestFileContent:
    def test_readme(self, engine):
        r = ProjectBuildRequest("An app", "myapp", "python", requirements=["auth"])
        c = engine._get_readme_template(r)
        assert "myapp" in c and "auth" in c

    def test_gitignore_python(self, engine):
        c = engine._get_gitignore("python")
        assert "__pycache__" in c and ".env" in c

    def test_gitignore_web(self, engine):
        c = engine._get_gitignore("web")
        assert "node_modules" in c

    def test_main_content(self, engine):
        r = ProjectBuildRequest("T", "hello", "python")
        c = engine._get_main_content(r)
        assert "hello" in c and "def main" in c

    def test_web_main_content(self, engine):
        r = ProjectBuildRequest("T", "webapp", "web")
        c = engine._get_main_content(r)
        assert "webapp" in c

    def test_test_content(self, engine):
        r = ProjectBuildRequest("T", "mytest", "python")
        c = engine._get_test_content(r)
        assert "test_main_runs" in c


# === 6. Project Manager ===

class TestProjectManager:
    def test_create_project(self, pm):
        s = pm.create_project("test_proj", "A test", "python")
        assert s.name == "test_proj"
        assert s.project_id.startswith("proj-")

    def test_get_by_name(self, pm):
        pm.create_project("myapp", "desc")
        assert pm.get_project_by_name("myapp") is not None
        assert pm.get_project_by_name("MYAPP") is not None

    def test_list_projects(self, pm):
        pm.create_project("p1")
        pm.create_project("p2")
        assert len(pm.list_projects()) == 2

    def test_remove_project(self, pm):
        s = pm.create_project("delme")
        assert pm.remove_project(s.project_id)
        assert pm.get_project(s.project_id) is None

    def test_find_by_path(self, pm, tmp_dir):
        s = pm.create_project("path_test", root_path=tmp_dir)
        assert pm.find_project_by_path(tmp_dir) is not None

    def test_update_task(self, pm):
        s = pm.create_project("upd")
        t = ProjectTask(id="t1", title="Task 1")
        pm.add_task_to_project(s.project_id, t)
        updated = pm.update_task(s.project_id, "t1", status=TaskStatus.COMPLETED)
        assert updated.status == TaskStatus.COMPLETED

    def test_add_task(self, pm):
        s = pm.create_project("addtask")
        t = ProjectTask(id="t1", title="T1")
        assert pm.add_task_to_project(s.project_id, t)
        assert s.task_graph.get_task("t1") is not None

    def test_add_milestone(self, pm):
        s = pm.create_project("addms")
        m = ProjectMilestone(id="m1", title="M1")
        assert pm.add_milestone_to_project(s.project_id, m)
        assert "m1" in s.task_graph.milestones

    def test_checkpoint(self, pm):
        s = pm.create_project("cp")
        cp = pm.create_checkpoint(s.project_id)
        assert cp is not None
        assert pm.get_latest_checkpoint(s.project_id) is not None

    def test_progress_report(self, pm):
        s = pm.create_project("prog")
        t1 = ProjectTask(id="t1", title="T1")
        t2 = ProjectTask(id="t2", title="T2")
        pm.add_task_to_project(s.project_id, t1)
        pm.add_task_to_project(s.project_id, t2)
        pm.update_task(s.project_id, "t1", status=TaskStatus.COMPLETED)
        report = pm.progress_report(s.project_id)
        assert report["progress_pct"] == 50.0
        assert report["completed"] == 1
        assert report["total"] == 2

    def test_milestone_auto_update(self, pm):
        s = pm.create_project("msauto")
        m = ProjectMilestone(id="m1", title="M1")
        pm.add_milestone_to_project(s.project_id, m)
        t = ProjectTask(id="t1", title="T1", milestone="m1")
        pm.add_task_to_project(s.project_id, t)
        pm.update_task(s.project_id, "t1", status=TaskStatus.COMPLETED)
        assert s.task_graph.milestones["m1"].status == MilestoneStatus.COMPLETED
        assert "m1" in s.completed_milestones

    def test_cleanup(self, pm):
        s = pm.create_project("old")
        s.updated_at = time.time() - 100000
        s.task_graph.add_task(ProjectTask(id="t1", title="T1", status=TaskStatus.COMPLETED))
        removed = pm.cleanup_temp_projects(max_age_hours=0.001)
        assert removed >= 1


# === 7. Task Graph ===

class TestTaskGraph:
    def test_next_ready(self):
        tg = ProjectTaskGraph()
        tg.add_task(ProjectTask(id="a", title="A"))
        tg.add_task(ProjectTask(id="b", title="B", depends_on=["a"]))
        ready = tg.next_ready_tasks()
        assert len(ready) == 1 and ready[0].id == "a"

    def test_progress(self):
        tg = ProjectTaskGraph()
        tg.add_task(ProjectTask(id="a", title="A", status=TaskStatus.COMPLETED))
        tg.add_task(ProjectTask(id="b", title="B", status=TaskStatus.PENDING))
        assert tg.progress_pct() == 50.0

    def test_all_finished(self):
        tg = ProjectTaskGraph()
        tg.add_task(ProjectTask(id="a", title="A", status=TaskStatus.COMPLETED))
        assert tg.all_finished()
        tg.add_task(ProjectTask(id="b", title="B"))
        assert not tg.all_finished()

    def test_has_failures(self):
        tg = ProjectTaskGraph()
        tg.add_task(ProjectTask(id="a", title="A", status=TaskStatus.FAILED))
        assert tg.has_failures()


# === 8. Full Build Flow ===

class TestFullBuild:
    def test_new_project_end_to_end(self, engine, tmp_dir):
        engine._projects_dir = Path(tmp_dir)
        class G:
            text = "Create a Python project called e2e_test"
        result = engine.execute(G(), {})
        assert result["success"]
        assert result["project_path"] is not None
        assert Path(result["project_path"]).exists()
        assert len(result["created_files"]) > 0

    def test_continue_nonexistent_fails(self, engine):
        result = engine.execute(_Goal("Continue nonexistent_project"), {})
        assert not result["success"]

    def test_document_nonexistent_fails(self, engine):
        result = engine.execute(_Goal("Generate readme for nonexistent"), {})
        assert not result["success"]

    def test_verify_project(self, engine, tmp_dir):
        p = Path(tmp_dir) / "verify_test"
        p.mkdir()
        (p / "README.md").write_text("test")
        (p / ".gitignore").write_text("test")
        r = engine._verify_project(p, ProjectBuildRequest("T", "v", "python"))
        assert r.success

    def test_verify_missing_files(self, engine, tmp_dir):
        p = Path(tmp_dir) / "verify_fail"
        p.mkdir()
        r = engine._verify_project(p, ProjectBuildRequest("T", "v", "python"))
        assert not r.success


# === 9. No Duplicate Systems ===

class TestNoDuplicates:
    def test_engine_uses_existing_dispatcher(self, engine):
        assert hasattr(engine, "dispatcher")
        assert engine.dispatcher is not None

    def test_engine_uses_existing_memory(self, engine):
        assert hasattr(engine, "memory_2_0")

    def test_project_manager_not_recreated(self, pm):
        s = pm.create_project("dup1")
        assert pm.get_project(s.project_id) is s


# === 10. Safety ===

class TestSafety:
    def test_no_destructive_actions_in_scaffold(self, engine, tmp_dir):
        p = Path(tmp_dir) / "safe_test"
        r = engine._scaffold_project(p, ProjectBuildRequest("T", "safe", "python"))
        assert r.success

    def test_project_isolation(self, pm):
        s1 = pm.create_project("iso1")
        s2 = pm.create_project("iso2")
        t = ProjectTask(id="t1", title="T1")
        pm.add_task_to_project(s1.project_id, t)
        assert s2.task_graph.get_task("t1") is None


# === 11. Existing SuperBrain Integration ===

class TestSuperBrainIntegration:
    def test_engine_is_capability(self, engine):
        from desktop_agent.brain.super_brain.capability_orchestrator import CapabilityEngine
        assert isinstance(engine, CapabilityEngine)

    def test_engine_capability_id(self, engine):
        assert engine.capability_id == "PROJECT_BUILDER"
