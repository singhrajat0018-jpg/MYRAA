"""
MYRAA Super-Brain -- Project Builder Engine (Phase A).

Specialized capability engine for autonomous project building workflows.
Integrates with ProjectManager for state/checkpoint/resume, and uses existing
tools (createFile, writeFile, createProjectFolder, writeCodeFile, runShellCommand,
runPythonScript, git tools) for all file/code operations.

NEVER creates a second planner, memory, or tool registry.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from desktop_agent.brain.super_brain.capability_orchestrator import CapabilityEngine
from desktop_agent.brain.super_brain.project_manager import (
    ProjectManager,
    ProjectState,
    ProjectTask,
    ProjectMilestone,
    ProjectTaskGraph,
    ProjectCheckpoint,
    TaskStatus,
    MilestoneStatus,
)
from desktop_agent.brain.knowledge.services.project_context import ProjectContext
from desktop_agent.core.application_container import ApplicationContainer
from desktop_agent.registry import TOOLS

log = logging.getLogger(__name__)


@dataclass
class ProjectBuildRequest:
    description: str
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    root_path: Optional[Path] = None
    requirements: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    mode: str = "new"


@dataclass
class ProjectBuildResult:
    success: bool = False
    message: str = ""
    project_path: Optional[Path] = None
    created_files: List[Path] = field(default_factory=list)
    modified_files: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    project_state: Optional[ProjectState] = None
    progress: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProjectBuilderEngine(CapabilityEngine):
    """Capability engine for autonomous project building (Phase A)."""

    capability_id = "PROJECT_BUILDER"

    def __init__(self, container: Optional[ApplicationContainer] = None):
        self.container = container
        self.dispatcher = getattr(container, "dispatcher", None)
        self.memory_2_0 = getattr(container, "memory_2_0", None) if container else None
        self.project_manager = ProjectManager(memory_2_0=self.memory_2_0)
        self._projects_dir = Path.cwd() / "myraa_projects"

    def execute(self, goal: Any, context: Any) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            request = self._parse_goal(goal, context)
            result = self._handle_project_build(request)
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "success": result.success,
                "message": result.message,
                "project_path": str(result.project_path) if result.project_path else None,
                "created_files": [str(f) for f in result.created_files],
                "modified_files": [str(f) for f in result.modified_files],
                "errors": result.errors,
                "warnings": result.warnings,
                "progress": result.progress,
                "execution_time_ms": elapsed,
                "metadata": result.metadata,
            }
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return {"success": False, "message": str(e), "error": str(e), "execution_time_ms": elapsed}

    # ================================================================
    # Goal Parsing
    # ================================================================

    def _parse_goal(self, goal: Any, context: Any) -> ProjectBuildRequest:
        goal_text = getattr(goal, "text", "") or ""
        if not goal_text and isinstance(goal, str):
            goal_text = goal
        request = ProjectBuildRequest(description=goal_text)

        goal_lower = goal_text.lower()
        request.mode = "new"

        if any(kw in goal_lower.split() for kw in ("continue", "resume", "proceed")):
            request.mode = "continue"
        elif any(kw in goal_lower.split() for kw in ("fix", "debug", "repair")):
            request.mode = "debug"
        elif goal_lower.startswith("run test") or goal_lower.startswith("test the"):
            request.mode = "test"
        elif any(kw in goal_lower.split() for kw in ("document", "readme", "docs")):
            request.mode = "document"

        match = re.search(r'(?:project|app|website|application|tool)\s+(?:called|named)\s+([^\s,.;]+)', goal_text, re.IGNORECASE)
        if match:
            request.project_name = match.group(1)
        if not request.project_name:
            match = re.search(r'(?:build|create|make|start)\s+([^\s,.;]+)\s+(?:project|app|application)', goal_text, re.IGNORECASE)
            if match:
                request.project_name = match.group(1)
        if not request.project_name:
            match = re.search(r'(?:build|create|make|start)\s+(?:a\s+)?([^\s,.;]+)\s+(?:called|named)\s+([^\s,.;]+)', goal_text, re.IGNORECASE)
            if match:
                request.project_name = match.group(2)
        if not request.project_name:
            match = re.search(r'^([^\s,.;]+)\s+(?:project|app)', goal_text, re.IGNORECASE)
            if match:
                request.project_name = match.group(1)
        if not request.project_name:
            request.project_name = f"project_{int(time.time())}"

        request.project_type = self._infer_project_type(request.project_name, goal_text)

        if "with" in goal_text.lower():
            parts = goal_text.lower().split("with", 1)
            if len(parts) > 1:
                for sep in ["and", ",", ";"]:
                    if sep in parts[1]:
                        request.requirements = [r.strip() for r in parts[1].split(sep) if r.strip()]
                        break
                if not request.requirements:
                    request.requirements = [parts[1].strip()]

        return request

    def _infer_project_type(self, name: str, description: str) -> str:
        text = (name + " " + description).lower()
        if any(k in text for k in ["python", "django", "flask", "fastapi", "pip"]):
            return "python"
        if any(k in text for k in ["web", "website", "html", "css", "react", "vue", "angular", "next"]):
            return "web"
        if any(k in text for k in ["api", "rest", "graphql"]):
            return "api"
        if any(k in text for k in ["data", "analysis", "ml", "machine learning", "pandas", "numpy"]):
            return "data_science"
        if any(k in text for k in ["mobile", "android", "ios"]):
            return "mobile"
        return "python"

    # ================================================================
    # Build Handler
    # ================================================================

    def _handle_project_build(self, request: ProjectBuildRequest) -> ProjectBuildResult:
        if request.mode == "continue":
            return self._handle_continue(request)
        if request.mode == "debug":
            return self._handle_debug(request)
        if request.mode == "test":
            return self._handle_test(request)
        if request.mode == "document":
            return self._handle_document(request)
        return self._handle_new_project(request)

    # ================================================================
    # New Project
    # ================================================================

    def _handle_new_project(self, request: ProjectBuildRequest) -> ProjectBuildResult:
        result = ProjectBuildResult()
        project_path = request.root_path or (self._projects_dir / request.project_name)

        if project_path.exists():
            result.warnings.append(f"Directory already exists: {project_path}")
            result.project_path = project_path
            existing = self.project_manager.find_project_by_path(str(project_path))
            if existing:
                result.project_state = existing
                result.progress = self.project_manager.progress_report(existing.project_id)
                result.message = f"Project '{request.project_name}' already exists. Use 'continue' mode."
                result.success = True
                return result
            result.message = f"Directory exists but no project state found. Use 'continue' mode."
            result.success = False
            return result

        state = self.project_manager.create_project(
            name=request.project_name,
            description=request.description,
            project_type=request.project_type,
            root_path=str(project_path),
            tech_stack=request.tech_stack,
            requirements=request.requirements,
            constraints=request.constraints,
        )

        self._create_milestones(state, request)
        self._create_tasks(state, request)

        scaffold_result = self._scaffold_project(project_path, request)
        if not scaffold_result.success:
            result.success = False
            result.message = scaffold_result.message
            result.errors.extend(scaffold_result.errors)
            return result

        result.created_files.extend(scaffold_result.created_files)
        result.project_path = project_path
        state.root_path = str(project_path)
        state.files_created = [str(f) for f in scaffold_result.created_files]

        self._init_git(project_path)

        verify = self._verify_project(project_path, request)
        if not verify.success:
            result.warnings.extend(verify.errors)
        else:
            scaffold_task = state.task_graph.get_task("scaffold")
            if scaffold_task:
                self.project_manager.update_task(
                    state.project_id, "scaffold",
                    status=TaskStatus.COMPLETED,
                    result_summary=f"Created {len(scaffold_result.created_files)} files",
                    files_changed=[str(f) for f in scaffold_result.created_files],
                )

        self.project_manager.write_project_memory(state.project_id)
        cp = self.project_manager.create_checkpoint(
            state.project_id, next_action="Implement source code"
        )

        result.success = True
        result.message = f"Project '{request.project_name}' created at {project_path}"
        result.project_state = state
        result.progress = self.project_manager.progress_report(state.project_id)
        result.metadata["checkpoint"] = cp.checkpoint_id if cp else None
        return result

    # ================================================================
    # Continue Existing Project
    # ================================================================

    def _handle_continue(self, request: ProjectBuildRequest) -> ProjectBuildResult:
        result = ProjectBuildResult()
        state = self.project_manager.get_project_by_name(request.project_name)
        if not state:
            result.message = f"No active project found with name '{request.project_name}'. Start a new project first."
            result.success = False
            return result

        project_path = Path(state.root_path)
        if not project_path.exists():
            result.message = f"Project directory missing: {project_path}"
            result.success = False
            return result

        git_state = self._inspect_git(project_path)
        checkpoint = self.project_manager.get_latest_checkpoint(state.project_id)

        next_tasks = state.task_graph.next_ready_tasks()
        active = state.task_graph.active_tasks()

        result.success = True
        result.project_path = project_path
        result.project_state = state
        result.progress = self.project_manager.progress_report(state.project_id)
        result.metadata["git_state"] = git_state
        result.metadata["checkpoint"] = checkpoint.to_dict() if checkpoint else None
        result.metadata["next_tasks"] = [t.title for t in next_tasks]
        result.metadata["active_tasks"] = [t.title for t in active]
        result.message = (
            f"Project '{state.name}' at {project_path}. "
            f"Progress: {state.task_graph.progress_pct()}%. "
            f"Next: {', '.join(t.title for t in next_tasks[:3]) or 'all tasks completed'}."
        )
        return result

    # ================================================================
    # Debug
    # ================================================================

    def _handle_debug(self, request: ProjectBuildRequest) -> ProjectBuildResult:
        result = ProjectBuildResult()
        state = self.project_manager.get_project_by_name(request.project_name)
        if not state:
            result.message = f"No active project '{request.project_name}'."
            result.success = False
            return result

        project_path = Path(state.root_path)
        failed = state.task_graph.failed_tasks()

        if not failed:
            result.success = True
            result.message = f"No failing tasks in project '{state.name}'."
            result.project_state = state
            result.progress = self.project_manager.progress_report(state.project_id)
            return result

        for task in failed:
            self.project_manager.update_task(
                state.project_id, task.id, status=TaskStatus.ACTIVE,
            )

        result.success = True
        result.project_path = project_path
        result.project_state = state
        result.progress = self.project_manager.progress_report(state.project_id)
        result.message = f"Found {len(failed)} failing tasks. Ready to debug."
        return result

    # ================================================================
    # Test
    # ================================================================

    def _handle_test(self, request: ProjectBuildRequest) -> ProjectBuildResult:
        result = ProjectBuildResult()
        state = self.project_manager.get_project_by_name(request.project_name)
        if not state:
            result.message = f"No active project '{request.project_name}'."
            result.success = False
            return result

        project_path = Path(state.root_path)
        test_result = self._run_tests(project_path, state.project_type)
        state.last_test_results = test_result

        result.success = test_result.get("exit_code", 1) == 0
        result.project_path = project_path
        result.project_state = state
        result.progress = self.project_manager.progress_report(state.project_id)
        result.metadata["test_results"] = test_result
        result.message = test_result.get("summary", "Tests completed")
        return result

    # ================================================================
    # Document
    # ================================================================

    def _handle_document(self, request: ProjectBuildRequest) -> ProjectBuildResult:
        result = ProjectBuildResult()
        state = self.project_manager.get_project_by_name(request.project_name)
        if not state:
            result.message = f"No active project '{request.project_name}'."
            result.success = False
            return result

        project_path = Path(state.root_path)
        readme = self._generate_readme(state)
        readme_path = project_path / "README.md"
        readme_path.write_text(readme, encoding="utf-8")

        doc_task_id = "document"
        existing = state.task_graph.get_task(doc_task_id)
        if existing:
            self.project_manager.update_task(
                state.project_id, doc_task_id,
                status=TaskStatus.COMPLETED,
                result_summary="README.md generated",
                files_changed=[str(readme_path)],
            )

        self.project_manager.write_project_memory(state.project_id)

        result.success = True
        result.project_path = project_path
        result.created_files.append(readme_path)
        result.project_state = state
        result.progress = self.project_manager.progress_report(state.project_id)
        result.message = f"Documentation updated for '{state.name}'."
        return result

    # ================================================================
    # Milestone & Task Creation
    # ================================================================

    def _create_milestones(self, state: ProjectState, request: ProjectBuildRequest) -> None:
        milestones = [
            ProjectMilestone(id="m1_scaffold", title="Scaffold", order=1),
            ProjectMilestone(id="m2_core", title="Core Implementation", order=2),
            ProjectMilestone(id="m3_tests", title="Tests", order=3),
            ProjectMilestone(id="m4_document", title="Documentation", order=4),
        ]
        for ms in milestones:
            self.project_manager.add_milestone_to_project(state.project_id, ms)

    def _create_tasks(self, state: ProjectState, request: ProjectBuildRequest) -> None:
        tasks = [
            ProjectTask(id="scaffold", title="Project scaffolding", milestone="m1_scaffold"),
            ProjectTask(id="core_files", title="Create core source files", milestone="m2_core"),
            ProjectTask(id="implement", title="Implement main logic", depends_on=["core_files"], milestone="m2_core"),
            ProjectTask(id="tests", title="Write tests", depends_on=["implement"], milestone="m3_tests"),
            ProjectTask(id="test_run", title="Run tests and fix failures", depends_on=["tests"], milestone="m3_tests"),
            ProjectTask(id="document", title="Generate documentation", depends_on=["implement"], milestone="m4_document"),
        ]
        for t in tasks:
            self.project_manager.add_task_to_project(state.project_id, t)

    # ================================================================
    # Scaffolding (uses existing filesystem, no second system)
    # ================================================================

    def _scaffold_project(self, project_path: Path, request: ProjectBuildRequest) -> ProjectBuildResult:
        result = ProjectBuildResult()
        try:
            project_path.mkdir(parents=True, exist_ok=True)
            result.created_files.append(project_path)

            structure = self._get_structure(request.project_type)
            dirs_to_create = [d for d in structure if "." not in d]
            files_to_create = [f for f in structure if "." in f]

            for d in dirs_to_create:
                dp = project_path / d
                dp.mkdir(parents=True, exist_ok=True)
                result.created_files.append(dp)

            for f in files_to_create:
                fp = project_path / f
                content = self._get_file_content(f, request)
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(content, encoding="utf-8")
                result.created_files.append(fp)

            src_dir = project_path / "src"
            if src_dir.exists():
                main_content = self._get_main_content(request)
                main_file = src_dir / self._get_main_filename(request.project_type)
                main_file.write_text(main_content, encoding="utf-8")
                result.created_files.append(main_file)

                init_file = src_dir / "__init__.py"
                init_file.write_text("", encoding="utf-8")
                result.created_files.append(init_file)

            tests_dir = project_path / "tests"
            if tests_dir.exists():
                test_init = tests_dir / "__init__.py"
                test_init.write_text("", encoding="utf-8")
                result.created_files.append(test_init)

                test_file = tests_dir / "test_main.py"
                test_content = self._get_test_content(request)
                test_file.write_text(test_content, encoding="utf-8")
                result.created_files.append(test_file)

            result.success = True
            result.message = f"Scaffolded {request.project_type} project"
        except Exception as e:
            result.success = False
            result.message = f"Scaffolding failed: {e}"
            result.errors.append(str(e))
        return result

    def _get_structure(self, project_type: str) -> List[str]:
        structures = {
            "python": ["src", "tests", "docs", "requirements.txt", "README.md", ".gitignore", "setup.py"],
            "web": ["src", "src/components", "public", "tests", "docs", "package.json", "README.md", ".gitignore"],
            "api": ["src", "src/routes", "src/models", "tests", "docs", "requirements.txt", "README.md", ".gitignore"],
            "data_science": ["notebooks", "src", "data", "models", "tests", "docs", "requirements.txt", "README.md", ".gitignore"],
        }
        return structures.get(project_type, structures["python"])

    def _get_file_content(self, filename: str, request: ProjectBuildRequest) -> str:
        if filename == "requirements.txt":
            return "# Add project dependencies here\n"
        if filename == "setup.py":
            return (
                "from setuptools import setup, find_packages\n\n"
                "setup(\n"
                f'    name="{request.project_name}",\n'
                '    version="0.1.0",\n'
                f'    description="{request.description}",\n'
                "    packages=find_packages(),\n"
                "    python_requires='>=3.8',\n"
                ")\n"
            )
        if filename == "package.json":
            return json.dumps({
                "name": request.project_name,
                "version": "0.1.0",
                "description": request.description,
                "scripts": {"start": "echo 'start'", "test": "echo 'test'"},
            }, indent=2) + "\n"
        if filename == ".gitignore":
            return self._get_gitignore(request.project_type)
        if filename == "README.md":
            return self._get_readme_template(request)
        return ""

    def _get_main_filename(self, project_type: str) -> str:
        if project_type == "web":
            return "index.js"
        return "main.py"

    def _get_main_content(self, request: ProjectBuildRequest) -> str:
        if request.project_type == "web":
            return f"// {request.project_name} - {request.description}\nconsole.log('Hello from {request.project_name}!');\n"
        return (
            f'"""Main entry point for {request.project_name}."""\n\n\n'
            f'def main():\n'
            f'    """Main function."""\n'
            f'    print("Hello from {request.project_name}!")\n\n\n'
            f'if __name__ == "__main__":\n'
            f'    main()\n'
        )

    def _get_test_content(self, request: ProjectBuildRequest) -> str:
        main_mod = self._get_main_filename(request.project_type).replace(".py", "")
        return (
            f'"""Tests for {request.project_name}."""\n\n\n'
            f'def test_main_runs():\n'
            f'    """Verify main module loads without error."""\n'
            f'    from src import {main_mod}\n'
            f'    assert hasattr({main_mod}, "main")\n'
        )

    def _get_gitignore(self, project_type: str) -> str:
        base = "__pycache__/\n*.py[cod]\n*.egg-info/\ndist/\nbuild/\n.eggs/\n*.egg\n.env\n.venv\nvenv/\n.pytest_cache/\n.mypy_cache/\n"
        if project_type == "web":
            return "node_modules/\n/dist\n/build\n.env\n*.log\n"
        return base

    def _get_readme_template(self, request: ProjectBuildRequest) -> str:
        return (
            f"# {request.project_name}\n\n"
            f"{request.description}\n\n"
            f"## Type\n{request.project_type}\n\n"
            f"## Requirements\n"
            + "\n".join(f"- {r}" for r in request.requirements or ["None specified"])
            + "\n\n## Getting Started\nSee source code for details.\n"
        )

    # ================================================================
    # Git Integration
    # ================================================================

    def _init_git(self, project_path: Path) -> bool:
        try:
            subprocess.run(
                ["git", "init"], cwd=str(project_path),
                capture_output=True, text=True, timeout=15,
            )
            subprocess.run(
                ["git", "add", "."], cwd=str(project_path),
                capture_output=True, text=True, timeout=15,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit via MYRAA"],
                cwd=str(project_path), capture_output=True, text=True, timeout=15,
            )
            return True
        except Exception:
            return False

    def _inspect_git(self, project_path: Path) -> Dict[str, Any]:
        result: Dict[str, Any] = {"is_git": False}
        git_dir = project_path / ".git"
        if not git_dir.exists():
            return result
        result["is_git"] = True
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=str(project_path), capture_output=True, text=True, timeout=10,
            )
            result["status"] = status.stdout[:2000] if status.stdout else ""
        except Exception:
            pass
        try:
            log_out = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                cwd=str(project_path), capture_output=True, text=True, timeout=10,
            )
            result["last_commits"] = log_out.stdout[:1000] if log_out.stdout else ""
        except Exception:
            pass
        return result

    # ================================================================
    # Test Execution
    # ================================================================

    def _run_tests(self, project_path: Path, project_type: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"exit_code": 1, "stdout": "", "stderr": "", "summary": ""}
        if project_type == "web":
            result["summary"] = "Web project test runner not configured"
            return result
        test_dir = project_path / "tests"
        if not test_dir.exists():
            result["summary"] = "No tests directory found"
            return result
        try:
            proc = subprocess.run(
                ["python", "-m", "pytest", str(test_dir), "-v", "--tb=short"],
                cwd=str(project_path), capture_output=True, text=True, timeout=120,
            )
            result["exit_code"] = proc.returncode
            result["stdout"] = proc.stdout[:5000]
            result["stderr"] = proc.stderr[:3000]
            passed = proc.stdout.count("PASSED") if proc.stdout else 0
            failed = proc.stdout.count("FAILED") if proc.stdout else 0
            result["summary"] = f"Tests: {passed} passed, {failed} failed (exit {proc.returncode})"
        except subprocess.TimeoutExpired:
            result["summary"] = "Tests timed out after 120s"
        except Exception as e:
            result["summary"] = f"Test execution error: {e}"
        return result

    # ================================================================
    # Verification
    # ================================================================

    def _verify_project(self, project_path: Path, request: ProjectBuildRequest) -> ProjectBuildResult:
        result = ProjectBuildResult()
        if not project_path.exists():
            result.success = False
            result.message = f"Project directory missing: {project_path}"
            return result
        expected = ["README.md", ".gitignore"]
        missing = [f for f in expected if not (project_path / f).exists()]
        if missing:
            result.success = False
            result.errors.append(f"Missing: {', '.join(missing)}")
        else:
            result.success = True
            result.message = "Project verification passed"
        return result

    # ================================================================
    # Readme Generation
    # ================================================================

    def _generate_readme(self, state: ProjectState) -> str:
        lines = [f"# {state.name}\n", f"{state.description}\n"]
        lines.append(f"## Type\n{state.project_type}\n")
        if state.tech_stack:
            lines.append("## Tech Stack\n" + "\n".join(f"- {t}" for t in state.tech_stack) + "\n")
        if state.requirements:
            lines.append("## Requirements\n" + "\n".join(f"- {r}" for r in state.requirements) + "\n")
        tg = state.task_graph
        lines.append(f"## Progress\n{tg.progress_pct()}% complete\n")
        if state.completed_milestones:
            lines.append("## Completed Milestones\n" + "\n".join(f"- {m}" for m in state.completed_milestones) + "\n")
        lines.append("## Getting Started\nSee source code for details.\n")
        return "\n".join(lines)
