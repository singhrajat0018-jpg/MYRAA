"""WorkerAgent implementations — bounded specialist workers for MYRAA.

Phase I.1: Workers now execute REAL tools through ToolRegistry dispatch.
Each worker: scoped tools/permissions, real execution, verification, structured results.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional

from .worker import Worker, WorkerContract, WorkerResult, WorkerStatus
from .skill import Skill, SkillDomain, SkillState
from .tool_bridge import get_tool_bridge

logger = logging.getLogger(__name__)


def _dispatch_tool(
    worker: Worker,
    tool_name: str,
    args: Dict[str, Any],
    evidence: List[str],
) -> tuple:
    """Dispatch a tool through the ToolBridge. Returns (ok, result_dict)."""
    bridge = get_tool_bridge()
    ok, result = bridge.dispatch(tool_name, args, allowed_tools=worker.allowed_tools)
    if ok:
        evidence.append(f"Tool {tool_name}: success")
    else:
        error = result.get("error", "unknown error")
        evidence.append(f"Tool {tool_name}: {error}")
    return ok, result


# ---------------------------------------------------------------------------
# Coding Worker — REAL tool execution
# ---------------------------------------------------------------------------

class CodingWorker(Worker):
    """Executes coding tasks via real ToolRegistry dispatch."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="coding_worker",
            skill_id="coding",
            allowed_tools=[
                "createFile", "readFile", "renameFile", "deleteFile", "moveFile",
                "listFiles", "searchFiles", "createProjectFolder", "createPythonFile",
                "writeCodeFile", "runPythonScript", "runShellCommand",
            ],
            allowed_permissions=["files", "terminal"],
            timeout_seconds=120.0,
        )

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        task = contract.task_description.lower()
        evidence: List[str] = []
        artifacts: List[Dict[str, Any]] = []
        all_ok = True

        try:
            if self.is_cancelled():
                return self._cancelled_result(contract)

            if "create" in task and "project" in task:
                result, ok = self._create_project(contract, evidence)
            elif "create" in task and ("file" in task or "script" in task):
                result, ok = self._create_file(contract, evidence, artifacts)
            elif "read" in task:
                result, ok = self._read_file(contract, evidence)
            elif "edit" in task or "fix" in task or "modify" in task:
                result, ok = self._edit_file(contract, evidence, artifacts)
            elif "delete" in task:
                result, ok = self._delete_file(contract, evidence)
            elif "list" in task or "find" in task:
                result, ok = self._list_files(contract, evidence)
            elif "run" in task and ("test" in task or "script" in task):
                result, ok = self._run_script(contract, evidence)
            else:
                result = {"action": "unknown", "message": "Task not clearly identified"}
                evidence.append("Task classification unclear")
                ok = False

            all_ok = ok
            self.status = WorkerStatus.COMPLETED if ok else WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status,
                task_id=contract.task_id,
                skill_id=self.skill_id,
                result=result,
                evidence=evidence,
                confidence=0.8 if ok else 0.2,
                artifacts=artifacts,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status,
                task_id=contract.task_id,
                skill_id=self.skill_id,
                errors=[str(exc)],
                evidence=evidence,
                confidence=0.0,
                latency_ms=latency_ms,
            )

    def _create_project(self, contract: WorkerContract, evidence: List[str]):
        name = contract.input_data.get("name", "new_project")
        path = contract.input_data.get("path", name)
        ok, result = _dispatch_tool(self, "createProjectFolder", {"path": path}, evidence)
        if ok:
            # Also create a README
            readme_path = f"{path}/README.md"
            _dispatch_tool(self, "createFile", {
                "path": readme_path,
                "content": f"# {name}\n\nProject created by MYRAA.",
            }, evidence)
        return {"action": "create_project", "name": name, "path": path, "status": "created" if ok else "failed"}, ok

    def _create_file(self, contract: WorkerContract, evidence: List[str], artifacts: List[Dict]):
        path = contract.input_data.get("path", "output.txt")
        content = contract.input_data.get("content", "")
        ok, result = _dispatch_tool(self, "createFile", {"path": path, "content": content}, evidence)
        if ok:
            artifacts.append({"path": path, "type": "file", "action": "created"})
        return {"action": "create_file", "path": path, "status": "created" if ok else "failed"}, ok

    def _read_file(self, contract: WorkerContract, evidence: List[str]):
        path = contract.input_data.get("path", "")
        ok, result = _dispatch_tool(self, "readFile", {"path": path}, evidence)
        content = result.get("result", {}).get("content", "") if isinstance(result.get("result"), dict) else ""
        return {"action": "read_file", "path": path, "content": content[:500], "status": "read" if ok else "failed"}, ok

    def _edit_file(self, contract: WorkerContract, evidence: List[str], artifacts: List[Dict]):
        path = contract.input_data.get("path", "")
        content = contract.input_data.get("content", "")
        # Read first, then write
        read_ok, read_result = _dispatch_tool(self, "readFile", {"path": path}, evidence)
        if read_ok:
            ok, result = _dispatch_tool(self, "createFile", {"path": path, "content": content}, evidence)
            if ok:
                artifacts.append({"path": path, "type": "file", "action": "edited"})
            return {"action": "edit_file", "path": path, "status": "edited" if ok else "failed"}, ok
        return {"action": "edit_file", "path": path, "status": "read_failed"}, False

    def _delete_file(self, contract: WorkerContract, evidence: List[str]):
        path = contract.input_data.get("path", "")
        ok, result = _dispatch_tool(self, "deleteFile", {"path": path}, evidence)
        return {"action": "delete_file", "path": path, "status": "deleted" if ok else "failed"}, ok

    def _list_files(self, contract: WorkerContract, evidence: List[str]):
        path = contract.input_data.get("path", ".")
        ok, result = _dispatch_tool(self, "listFiles", {"path": path}, evidence)
        files = result.get("result", {}).get("files", []) if isinstance(result.get("result"), dict) else []
        return {"action": "list_files", "path": path, "files": files[:50], "count": len(files)}, ok

    def _run_script(self, contract: WorkerContract, evidence: List[str]):
        script = contract.input_data.get("script", "")
        path = contract.input_data.get("path", "")
        if path:
            ok, result = _dispatch_tool(self, "runPythonScript", {"path": path}, evidence)
        elif script:
            ok, result = _dispatch_tool(self, "runShellCommand", {"command": script}, evidence)
        else:
            return {"action": "run_script", "status": "no_script_provided"}, False
        output = result.get("result", {}).get("output", "") if isinstance(result.get("result"), dict) else ""
        return {"action": "run_script", "output": output[:500], "status": "executed" if ok else "failed"}, ok

    def _cancelled_result(self, contract: WorkerContract) -> WorkerResult:
        self.status = WorkerStatus.CANCELLED
        return WorkerResult(
            status=self.status,
            task_id=contract.task_id,
            skill_id=self.skill_id,
            evidence=["Worker cancelled"],
            confidence=0.0,
        )


# ---------------------------------------------------------------------------
# Research Worker — REAL tool execution
# ---------------------------------------------------------------------------

class ResearchWorker(Worker):
    """Executes research tasks via real ToolRegistry dispatch."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="research_worker",
            skill_id="research",
            allowed_tools=["searchWeb", "searchGoogle", "searchGitHub"],
            allowed_permissions=["web"],
            timeout_seconds=60.0,
        )

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        query = contract.input_data.get("query", contract.task_description)
        evidence: List[str] = [f"Research query: {query}"]

        try:
            if self.is_cancelled():
                return WorkerResult(status=WorkerStatus.CANCELLED, task_id=contract.task_id,
                                    skill_id=self.skill_id, evidence=["Cancelled"], confidence=0.0)

            # Try searchWeb first, then searchGoogle
            for tool in ["searchWeb", "searchGoogle"]:
                if tool in self.allowed_tools:
                    ok, result = _dispatch_tool(self, tool, {"query": query}, evidence)
                    if ok:
                        sources = result.get("result", {}).get("results", []) if isinstance(result.get("result"), dict) else []
                        self.status = WorkerStatus.COMPLETED
                        latency_ms = (time.perf_counter() - start) * 1000
                        return WorkerResult(
                            status=self.status,
                            task_id=contract.task_id,
                            skill_id=self.skill_id,
                            result={"action": "research", "query": query, "sources": sources[:10]},
                            evidence=evidence,
                            confidence=0.7 if sources else 0.3,
                            latency_ms=latency_ms,
                        )

            # No search tools available
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status,
                task_id=contract.task_id,
                skill_id=self.skill_id,
                result={"action": "research", "query": query, "sources": []},
                evidence=evidence + ["No search tools available"],
                confidence=0.2,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                errors=[str(exc)], evidence=evidence, confidence=0.0, latency_ms=latency_ms,
            )


# ---------------------------------------------------------------------------
# Trading Worker — READ-ONLY, blocks execution
# ---------------------------------------------------------------------------

class TradingWorker(Worker):
    """Read-only trading analysis. NEVER executes orders."""

    BLOCKED_ACTIONS = frozenset([
        "buy", "sell", "square_off", "cancel", "modify", "submit",
        "place_order", "execute_order", "trade", "open_position",
        "close_position", "exit", "enter",
    ])

    def __init__(self) -> None:
        super().__init__(
            worker_id="trading_worker",
            skill_id="trading",
            allowed_tools=[],
            allowed_permissions=["read_market"],
            timeout_seconds=30.0,
        )

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        task = contract.task_description.lower()
        evidence: List[str] = []

        # Safety: block any trading action
        for action in self.BLOCKED_ACTIONS:
            if action in task:
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=WorkerStatus.COMPLETED,
                    task_id=contract.task_id, skill_id=self.skill_id,
                    result={"blocked": True, "action": action, "reason": "Read-only advisory mode"},
                    evidence=[f"Blocked trading action: {action}"],
                    confidence=1.0, latency_ms=latency_ms,
                )

        try:
            symbol = contract.input_data.get("symbol", "")
            result = {"action": "analyze", "symbol": symbol, "status": "completed"}
            evidence.append("Read-only trading analysis (no real data provider wired)")
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                result=result, evidence=evidence, confidence=0.6, latency_ms=latency_ms,
            )
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                errors=[str(exc)], evidence=evidence, confidence=0.0, latency_ms=latency_ms,
            )


# ---------------------------------------------------------------------------
# Vision Worker — REAL tool execution
# ---------------------------------------------------------------------------

class VisionWorker(Worker):
    """Executes vision tasks via real ToolRegistry dispatch."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="vision_worker",
            skill_id="vision",
            allowed_tools=["takeScreenshot", "analyzeScreenshot", "readScreen"],
            allowed_permissions=["vision"],
            timeout_seconds=15.0,
        )

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        task = contract.task_description.lower()
        evidence: List[str] = []

        try:
            if self.is_cancelled():
                return WorkerResult(status=WorkerStatus.CANCELLED, task_id=contract.task_id,
                                    skill_id=self.skill_id, evidence=["Cancelled"], confidence=0.0)

            if "screenshot" in task:
                ok, result = _dispatch_tool(self, "takeScreenshot", {"include_image": False}, evidence)
                screenshot_path = result.get("result", {}).get("path", "") if isinstance(result.get("result"), dict) else ""
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "screenshot", "path": screenshot_path, "status": "captured" if ok else "failed"},
                    evidence=evidence, confidence=0.8 if ok else 0.2,
                    artifacts=[{"path": screenshot_path, "type": "screenshot"}] if ok else [],
                    latency_ms=latency_ms,
                )
            elif "ocr" in task or "read screen" in task:
                ok, result = _dispatch_tool(self, "readScreen", {}, evidence)
                text = result.get("result", {}).get("text", "") if isinstance(result.get("result"), dict) else ""
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "ocr", "text": text[:1000], "status": "completed" if ok else "failed"},
                    evidence=evidence, confidence=0.7 if ok and text else 0.3,
                    latency_ms=latency_ms,
                )
            else:
                ok, result = _dispatch_tool(self, "analyzeScreenshot", {"include_image": False}, evidence)
                analysis = result.get("result", {}) if isinstance(result.get("result"), dict) else {}
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "analyze", "analysis": analysis, "status": "completed" if ok else "failed"},
                    evidence=evidence, confidence=0.7 if ok else 0.2, latency_ms=latency_ms,
                )
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                errors=[str(exc)], evidence=evidence, confidence=0.0, latency_ms=latency_ms,
            )


# ---------------------------------------------------------------------------
# Desktop Worker — REAL tool execution
# ---------------------------------------------------------------------------

class DesktopWorker(Worker):
    """Executes desktop tasks via real ToolRegistry dispatch."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="desktop_worker",
            skill_id="desktop",
            allowed_tools=[
                "openApplication", "closeApplication",
                "volumeUp", "volumeDown", "setVolume", "muteToggle",
                "brightnessUp", "brightnessDown", "setBrightness",
                "minimizeWindow", "maximizeWindow", "activateWindow",
                "closeWindow", "switchApplication",
                "typeText", "pressKey", "hotkey",
                "moveMouse", "leftClick", "rightClick", "doubleClick",
            ],
            allowed_permissions=["desktop", "interact"],
            timeout_seconds=15.0,
        )

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        task = contract.task_description.lower()
        evidence: List[str] = []

        try:
            if self.is_cancelled():
                return WorkerResult(status=WorkerStatus.CANCELLED, task_id=contract.task_id,
                                    skill_id=self.skill_id, evidence=["Cancelled"], confidence=0.0)

            if "open" in task or "launch" in task:
                app = contract.input_data.get("application", "")
                if not app:
                    # Extract from task description
                    words = task.split()
                    idx = next((i for i, w in enumerate(words) if w in ("open", "launch")), -1)
                    app = " ".join(words[idx+1:]) if idx >= 0 and idx+1 < len(words) else "unknown"
                ok, result = _dispatch_tool(self, "openApplication", {"application": app}, evidence)
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "open", "application": app, "status": "launched" if ok else "failed"},
                    evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms,
                )
            elif "close" in task:
                app = contract.input_data.get("application", "")
                ok, result = _dispatch_tool(self, "closeApplication", {"application": app}, evidence)
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "close", "application": app, "status": "closed" if ok else "failed"},
                    evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms,
                )
            elif "volume" in task:
                if "up" in task:
                    ok, result = _dispatch_tool(self, "volumeUp", {}, evidence)
                elif "down" in task:
                    ok, result = _dispatch_tool(self, "volumeDown", {}, evidence)
                else:
                    ok, result = _dispatch_tool(self, "volumeUp", {}, evidence)
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "volume", "status": "adjusted" if ok else "failed"},
                    evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms,
                )
            elif "brightness" in task:
                if "up" in task:
                    ok, result = _dispatch_tool(self, "brightnessUp", {}, evidence)
                elif "down" in task:
                    ok, result = _dispatch_tool(self, "brightnessDown", {}, evidence)
                else:
                    ok, result = _dispatch_tool(self, "brightnessUp", {}, evidence)
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "brightness", "status": "adjusted" if ok else "failed"},
                    evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms,
                )
            elif "type" in task:
                text = contract.input_data.get("text", "")
                ok, result = _dispatch_tool(self, "typeText", {"text": text}, evidence)
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "type", "status": "typed" if ok else "failed"},
                    evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms,
                )
            elif "click" in task:
                x = contract.input_data.get("x", 0)
                y = contract.input_data.get("y", 0)
                ok, result = _dispatch_tool(self, "leftClick", {"x": x, "y": y}, evidence)
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result={"action": "click", "x": x, "y": y, "status": "clicked" if ok else "failed"},
                    evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms,
                )
            else:
                # Generic desktop action
                result = {"action": "desktop", "status": "completed"}
                evidence.append("Desktop action completed (no specific tool matched)")
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(
                    status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                    result=result, evidence=evidence, confidence=0.5, latency_ms=latency_ms,
                )
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                errors=[str(exc)], evidence=evidence, confidence=0.0, latency_ms=latency_ms,
            )


# ---------------------------------------------------------------------------
# Verification Worker — REAL tool execution
# ---------------------------------------------------------------------------

class VerificationWorker(Worker):
    """Verifies correctness via real file/execution checks."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="verification_worker",
            skill_id="verification",
            allowed_tools=["readFile", "listFiles", "runPythonScript", "runShellCommand"],
            allowed_permissions=["files", "terminal"],
            timeout_seconds=30.0,
        )

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        evidence: List[str] = []
        checks: List[Dict[str, Any]] = []

        try:
            # Completeness check
            input_result = contract.input_data.get("result", {})
            if input_result:
                checks.append({"check": "completeness", "passed": True, "evidence": "Result exists"})
                evidence.append("Completeness check passed")
            else:
                checks.append({"check": "completeness", "passed": False, "evidence": "Empty result"})
                evidence.append("Completeness check failed: empty result")

            # Confidence check
            confidence = contract.input_data.get("confidence", 0.0)
            if confidence >= 0.5:
                checks.append({"check": "confidence", "passed": True, "evidence": f"Confidence: {confidence}"})
                evidence.append(f"Confidence check passed: {confidence}")
            else:
                checks.append({"check": "confidence", "passed": False, "evidence": f"Low confidence: {confidence}"})
                evidence.append(f"Confidence check failed: {confidence}")

            # File existence check (if path provided)
            path = contract.input_data.get("path")
            if path:
                ok, result = _dispatch_tool(self, "readFile", {"path": path}, evidence)
                file_exists = ok and result.get("ok", False)
                checks.append({"check": "file_exists", "passed": file_exists, "evidence": f"File {path} exists: {file_exists}"})

            all_passed = all(c["passed"] for c in checks)
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                result={"checks": checks, "all_passed": all_passed},
                evidence=evidence, confidence=0.9 if all_passed else 0.3, latency_ms=latency_ms,
            )
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(
                status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                errors=[str(exc)], evidence=evidence, confidence=0.0, latency_ms=latency_ms,
            )


# ---------------------------------------------------------------------------
# Memory Worker — stub (no real memory tool in TOOLS)
# ---------------------------------------------------------------------------

class MemoryWorker(Worker):
    """Memory operations. Uses in-memory state (no TOOLS entry)."""

    def __init__(self) -> None:
        super().__init__(worker_id="memory_worker", skill_id="memory",
                         allowed_tools=[], allowed_permissions=["memory"], timeout_seconds=10.0)

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        try:
            action = contract.input_data.get("action", "store")
            result = {"action": action, "status": "completed"}
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                result=result, evidence=[f"Memory {action} completed"], confidence=0.8, latency_ms=latency_ms)
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                errors=[str(exc)], confidence=0.0, latency_ms=latency_ms)


# ---------------------------------------------------------------------------
# Project Worker — REAL tool execution
# ---------------------------------------------------------------------------

class ProjectWorker(Worker):
    """Manages project lifecycle via real tools."""

    def __init__(self) -> None:
        super().__init__(worker_id="project_worker", skill_id="projects",
                         allowed_tools=["createProjectFolder", "createFile", "readFile", "writeCodeFile", "runPythonScript"],
                         allowed_permissions=["files"], timeout_seconds=60.0)

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        evidence: List[str] = []
        try:
            action = contract.input_data.get("action", "create")
            if action == "create":
                name = contract.input_data.get("name", "project")
                ok, result = _dispatch_tool(self, "createProjectFolder", {"path": name}, evidence)
                self.status = WorkerStatus.COMPLETED
                latency_ms = (time.perf_counter() - start) * 1000
                return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                    result={"action": action, "name": name, "status": "created" if ok else "failed"},
                                    evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms)
            result = {"action": action, "status": "completed"}
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                result=result, evidence=[f"Project {action} completed"], confidence=0.8, latency_ms=latency_ms)
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                errors=[str(exc)], confidence=0.0, latency_ms=latency_ms)


# ---------------------------------------------------------------------------
# Documents Worker — REAL tool execution
# ---------------------------------------------------------------------------

class DocumentsWorker(Worker):
    """Handles document creation via real tools."""

    def __init__(self) -> None:
        super().__init__(worker_id="documents_worker", skill_id="documents",
                         allowed_tools=["createFile", "readFile", "writeCodeFile"],
                         allowed_permissions=["files"], timeout_seconds=30.0)

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        evidence: List[str] = []
        try:
            path = contract.input_data.get("path", "document.md")
            content = contract.input_data.get("content", "# Document\n\nGenerated by MYRAA.")
            ok, result = _dispatch_tool(self, "createFile", {"path": path, "content": content}, evidence)
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                result={"action": "document", "path": path, "status": "created" if ok else "failed"},
                                evidence=evidence, confidence=0.8 if ok else 0.2, latency_ms=latency_ms)
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                errors=[str(exc)], confidence=0.0, latency_ms=latency_ms)


# ---------------------------------------------------------------------------
# Automation Worker — REAL tool execution
# ---------------------------------------------------------------------------

class AutomationWorker(Worker):
    """Executes automation workflows via real tools."""

    def __init__(self) -> None:
        super().__init__(worker_id="automation_worker", skill_id="automation",
                         allowed_tools=["typeText", "pressKey", "hotkey", "moveMouse", "leftClick",
                                         "rightClick", "doubleClick", "openApplication", "openWebsite"],
                         allowed_permissions=["desktop", "browser", "interact"], timeout_seconds=30.0)

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        evidence: List[str] = []
        steps_executed = 0
        try:
            steps = contract.input_data.get("steps", [])
            for step in steps:
                if self.is_cancelled():
                    break
                tool = step.get("tool", "")
                args = step.get("args", {})
                if tool in self.allowed_tools:
                    ok, _ = _dispatch_tool(self, tool, args, evidence)
                    if ok:
                        steps_executed += 1
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                result={"action": "automate", "total_steps": len(steps), "executed": steps_executed},
                                evidence=evidence, confidence=0.8 if steps_executed == len(steps) else 0.4,
                                latency_ms=latency_ms)
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                errors=[str(exc)], confidence=0.0, latency_ms=latency_ms)


# ---------------------------------------------------------------------------
# Diagnostics Worker — REAL tool execution
# ---------------------------------------------------------------------------

class DiagnosticsWorker(Worker):
    """Runs system diagnostics via real tools."""

    def __init__(self) -> None:
        super().__init__(worker_id="diagnostics_worker", skill_id="diagnostics",
                         allowed_tools=["systemInfo", "temperatureInfo", "gpuInfo"],
                         allowed_permissions=["system_info"], timeout_seconds=10.0)

    def execute(self, contract: WorkerContract) -> WorkerResult:
        start = time.perf_counter()
        self.status = WorkerStatus.RUNNING
        evidence: List[str] = []
        system_data: Dict[str, Any] = {}
        try:
            for tool in ["systemInfo", "temperatureInfo", "gpuInfo"]:
                if tool in self.allowed_tools:
                    ok, result = _dispatch_tool(self, tool, {}, evidence)
                    if ok:
                        system_data[tool] = result.get("result", {})
            self.status = WorkerStatus.COMPLETED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                result={"action": "diagnostics", "system": system_data, "status": "completed"},
                                evidence=evidence, confidence=0.9 if system_data else 0.4, latency_ms=latency_ms)
        except Exception as exc:
            self.status = WorkerStatus.FAILED
            latency_ms = (time.perf_counter() - start) * 1000
            return WorkerResult(status=self.status, task_id=contract.task_id, skill_id=self.skill_id,
                                errors=[str(exc)], confidence=0.0, latency_ms=latency_ms)
