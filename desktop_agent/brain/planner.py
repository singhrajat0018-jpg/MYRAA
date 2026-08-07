"""
MYRAA Brain - Planner

The Planner converts a BrainDecision into an executable task graph.

Decision Engine
        ↓
Planner
        ↓
Task Graph
        ↓
Orchestrator

The planner NEVER executes tools.
"""

from __future__ import annotations
from ..semantic.semantic_models import EntityType
import uuid
from typing import List

from .models import (
    BrainDecision,
    ToolAction,
)

from .task import (
    Task,
    TaskGraph,
)


class Planner:

    """
    Converts a user's goal into executable tasks.
    """

    def __init__(self):

        pass

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def build_plan(
        self,
        decision: BrainDecision,
    ) -> TaskGraph:

        planner = self._select_planner(
            decision.goal
        )

        return planner(decision)

    # ---------------------------------------------------------
    # Planner Selection
    # ---------------------------------------------------------

    def _select_planner(
        self,
        goal: str,
    ):

        text = goal.lower()

        if "organize" in text:

            return self._plan_organize

        if "prepare" in text:

            return self._plan_prepare

        if "open" in text:

            return self._plan_open

        if "search" in text:

            return self._plan_search

        if "create" in text:

            return self._plan_create

        return self._plan_generic

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _task(
        self,
        title: str,
        tool: str,
        args=None,
        depends=None,
    ) -> Task:

        if args is None:
            args = {}

        if depends is None:
            depends = []

        return Task(

            id=str(uuid.uuid4()),

            title=title,

            description=title,

            action=ToolAction(
                tool=tool,
                args=args,
            ),

            depends_on=depends,
        )

    # ---------------------------------------------------------
    # Generic Planner
    # ---------------------------------------------------------

    def _plan_generic(
        self,
        decision: BrainDecision,
    ) -> TaskGraph:

        graph = TaskGraph()

        graph.add(

            self._task(

                "Complete user request",

                "chat",

                {
                    "goal": decision.goal
                }

            )

        )

        return graph

        # ---------------------------------------------------------
    # Open Planner
    # ---------------------------------------------------------

    def _plan_open(
        self,
        decision: BrainDecision,
    ) -> TaskGraph:

        graph = TaskGraph()

        goal = decision.goal.lower()

        application = ""

        known_apps = [
            "chrome",
            "edge",
            "firefox",
            "notepad",
            "calculator",
            "spotify",
            "vscode",
            "visual studio code",
            "explorer",
            "discord",
            "steam",
        ]

        for app in known_apps:

            if app in goal:
                application = app
                break

        graph.add(

            self._task(

                title=f"Open {application}",

                tool="openApplication",

                args={
                    "application": application
                }

            )

        )

        return graph

    # ---------------------------------------------------------
    # Search Planner
    # ---------------------------------------------------------

    def _plan_search(
        self,
        decision: BrainDecision,
    ) -> TaskGraph:

        graph = TaskGraph()

        task = decision.task

        goal = (
            decision.goal
            or task.get_entity(EntityType.SEARCH_QUERY)
            or task.metadata.get("url")
            or task.raw_text
        )

        tool = "searchWeb"

        lower = goal.lower()

        skill = task.metadata.get("skill")

        # -------------------------------------------------
        # Skill-aware routing
        # -------------------------------------------------

        if skill == "news":

            tool = "searchWeb"

            goal = "latest news today"

        elif skill == "weather":

            tool = "searchWeb"

        elif skill == "trading":

            tool = "searchWeb"

        # -------------------------------------------------
        # Explicit platform routing
        # -------------------------------------------------

        elif "youtube" in lower:

            tool = "searchYouTube"

        elif "google" in lower:

            tool = "searchGoogle"

        elif "github" in lower:

            tool = "searchGitHub"

        graph.add(

            self._task(

                title="Perform Search",

                tool=tool,

                args={
                    "query": goal
                }

            )

        )

        return graph

    # ---------------------------------------------------------
    # Create Planner
    # ---------------------------------------------------------

    def _plan_create(
        self,
        decision: BrainDecision,
    ) -> TaskGraph:

        graph = TaskGraph()

        goal = decision.goal.lower()

        if "python" in goal:

            graph.add(

                self._task(

                    "Create Python File",

                    "createPythonFile",

                    {
                        "prompt": decision.goal
                    }

                )

            )

            return graph

        if "project" in goal:

            graph.add(

                self._task(

                    "Create Project Folder",

                    "createProjectFolder",

                    {
                        "name": decision.goal
                    }

                )

            )

            return graph

        graph.add(

            self._task(

                "Create File",

                "createFile",

                {
                    "name": decision.goal
                }

            )

        )

        return graph

        # ---------------------------------------------------------
    # Organize Planner
    # ---------------------------------------------------------

    def _plan_organize(
        self,
        decision: BrainDecision,
    ) -> TaskGraph:

        graph = TaskGraph()

        scan = self._task(
            title="Scan Target Folder",
            tool="listFiles",
            args={}
        )

        graph.add(scan)

        create = self._task(
            title="Create Category Folders",
            tool="createFolder",
            args={},
            depends=[scan.id],
        )

        graph.add(create)

        move = self._task(
            title="Move Files",
            tool="moveFile",
            args={},
            depends=[create.id],
        )

        graph.add(move)

        verify = self._task(
            title="Verify Organization",
            tool="verifyFolder",
            args={},
            depends=[move.id],
        )

        graph.add(verify)

        return graph

    # ---------------------------------------------------------
    # Prepare Planner
    # ---------------------------------------------------------

    def _plan_prepare(
        self,
        decision: BrainDecision,
    ) -> TaskGraph:

        graph = TaskGraph()

        goal = decision.goal.lower()

        #
        # Prepare for coding
        #

        if "coding" in goal or "code" in goal:

            vscode = self._task(
                "Open VS Code",
                "openApplication",
                {
                    "application": "vscode"
                }
            )

            graph.add(vscode)

            chrome = self._task(
                "Open Browser",
                "openApplication",
                {
                    "application": "chrome"
                },
                depends=[vscode.id]
            )

            graph.add(chrome)

            github = self._task(
                "Open GitHub",
                "openWebsite",
                {
                    "url": "https://github.com"
                },
                depends=[chrome.id]
            )

            graph.add(github)

            return graph

        #
        # Prepare for meeting
        #

        if "meeting" in goal:

            outlook = self._task(
                "Open Outlook",
                "openApplication",
                {
                    "application": "outlook"
                }
            )

            graph.add(outlook)

            teams = self._task(
                "Open Teams",
                "openApplication",
                {
                    "application": "teams"
                },
                depends=[outlook.id]
            )

            graph.add(teams)

            return graph

        #
        # Default prepare sequence
        #

        graph.add(

            self._task(

                "Prepare Workspace",

                "systemInfo",

                {}

            )

        )

        return graph

    # ---------------------------------------------------------
    # Verification Planner
    # ---------------------------------------------------------

    def append_verification(
        self,
        graph: TaskGraph,
    ) -> TaskGraph:

        if len(graph.tasks) == 0:
            return graph

        last = graph.tasks[-1]

        verify = self._task(

            title="Verify Execution",

            tool="verifyExecution",

            args={},

            depends=[last.id]

        )

        graph.add(verify)

        return graph

    # ---------------------------------------------------------
    # Planner Optimization
    # ---------------------------------------------------------

    def optimize(
        self,
        graph: TaskGraph,
    ) -> TaskGraph:

        unique = []

        seen = set()

        for task in graph.tasks:

            key = (
                task.action.tool,
                tuple(task.action.args.items())
            )

            if key in seen:
                continue

            seen.add(key)

            unique.append(task)

        graph.tasks = unique

        return graph

        # ---------------------------------------------------------
    # Dependency Validation
    # ---------------------------------------------------------

    def validate(
        self,
        graph: TaskGraph,
    ) -> bool:
        """
        Ensure every dependency references an existing task.
        """

        task_ids = {
            task.id
            for task in graph.tasks
        }

        for task in graph.tasks:

            for dependency in task.depends_on:

                if dependency not in task_ids:
                    return False

        return True

    # ---------------------------------------------------------
    # Ready Tasks
    # ---------------------------------------------------------

    def ready_tasks(
        self,
        graph: TaskGraph,
    ) -> List[Task]:
        """
        Return all tasks that can be executed immediately.
        """

        completed = {
            task.id
            for task in graph.tasks
            if task.status.name == "COMPLETED"
        }

        ready = []

        for task in graph.tasks:

            if task.status.name != "PENDING":
                continue

            if all(dep in completed for dep in task.depends_on):
                ready.append(task)

        return ready

    # ---------------------------------------------------------
    # Failed Tasks
    # ---------------------------------------------------------

    def failed_tasks(
        self,
        graph: TaskGraph,
    ) -> List[Task]:

        return [
            task
            for task in graph.tasks
            if task.status.name == "FAILED"
        ]

    # ---------------------------------------------------------
    # Retry Planning
    # ---------------------------------------------------------

    def retry_failed(
        self,
        graph: TaskGraph,
        max_retries: int = 2,
    ) -> TaskGraph:

        for task in graph.tasks:

            if task.status.name != "FAILED":
                continue

            if task.retries >= max_retries:
                continue

            task.retries += 1
            task.status = task.status.PENDING

        return graph

    # ---------------------------------------------------------
    # Completion Check
    # ---------------------------------------------------------

    def completed(
        self,
        graph: TaskGraph,
    ) -> bool:

        return all(
            task.status.name == "COMPLETED"
            for task in graph.tasks
        )

    # ---------------------------------------------------------
    # Planning Summary
    # ---------------------------------------------------------

    def summary(
        self,
        graph: TaskGraph,
    ) -> dict:

        total = len(graph.tasks)

        completed = len([
            t for t in graph.tasks
            if t.status.name == "COMPLETED"
        ])

        failed = len([
            t for t in graph.tasks
            if t.status.name == "FAILED"
        ])

        pending = len([
            t for t in graph.tasks
            if t.status.name == "PENDING"
        ])

        running = len([
            t for t in graph.tasks
            if t.status.name == "RUNNING"
        ])

        return {
            "total": total,
            "completed": completed,
            "running": running,
            "pending": pending,
            "failed": failed,
        }

    # ---------------------------------------------------------
    # Debug Print
    # ---------------------------------------------------------

    def print_plan(
        self,
        graph: TaskGraph,
    ) -> None:

        print()

        print("=" * 60)

        print("MYRAA EXECUTION PLAN")

        print("=" * 60)

        for i, task in enumerate(graph.tasks, start=1):

            print(f"{i}. {task.title}")

            print(f"   Tool : {task.action.tool}")

            print(f"   Args : {task.action.args}")

            print(f"   Depends : {task.depends_on}")

            print()

        print("=" * 60)

    def build_action_plan(
        self,
        action: str,
        parameters: dict,
    ):
        graph = TaskGraph()

        graph.add(
            self._task(
                title=action,
                tool=action,
                args=parameters,
            )
        )

        return graph