"""
F2 dispatch tests: Node <-> Python tool bridge contract.

Verifies:
- The response shape returned by the Python agent for simple tools
  ({ok:true, result, tool, meta}) is what server.ts accepts as success.
- request_id is threaded through the dispatch path and echoed back in meta.
- DESKTOP_TOOLS (server.ts) stays in sync with the Python tool registry.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from desktop_agent.registry import TOOLS, DESKTOP_TOOL_NAMES, load_all

# Ensure all tool modules are loaded before tests run
load_all()

ROOT = Path(__file__).resolve().parent.parent
SERVER_TS = ROOT / "server.ts"


class MockExecuteRequest:
    def __init__(self, tool: str, args: dict | None = None, request_id: str | None = None):
        self.tool = tool
        self.args = args or {}
        self.request_id = request_id


def test_request_id_echoed_in_meta():
    """request_id sent by Node must come back in meta for traceability."""
    from desktop_agent.main import CommandDispatcher, ExecuteResponse
    req = MockExecuteRequest("currentDateTime", {}, request_id="test-req-123")
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)
    assert resp.ok is True
    assert resp.meta.get("request_id") == "test-req-123"


def test_simple_tool_success_shape_matches_node_contract():
    """server.ts treats `ok === true || success === true` as success.

    Simple tools must return ok=True (this is the shape the Node bridge
    accepts), otherwise every successful tool looked like a desktop error.
    """
    from desktop_agent.main import CommandDispatcher, ExecuteResponse
    req = MockExecuteRequest("currentDateTime", {})
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)
    assert resp.ok is True
    assert resp.error is None
    assert resp.tool == "currentDateTime"
    assert resp.result is not None


def test_simple_tool_error_shape():
    """A failing simple tool returns ok=False + error (Node surfaces this)."""
    from desktop_agent.main import CommandDispatcher, ExecuteResponse
    req = MockExecuteRequest("executePowerAction", {"action": "shutdown"})
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)
    assert resp.ok is False
    assert resp.error is not None


def test_unknown_tool_error_shape():
    from desktop_agent.main import CommandDispatcher, ExecuteResponse
    req = MockExecuteRequest("__no_such_tool__", {})
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)
    assert resp.ok is False
    assert "Unknown tool" in resp.error


def _parse_desktop_tools_from_server_ts() -> set[str]:
    text = SERVER_TS.read_text(encoding="utf-8")
    m = re.search(r"const DESKTOP_TOOLS: ReadonlySet<string> = new Set\(\[(.*?)\]\)", text, re.S)
    assert m, "Could not find DESKTOP_TOOLS in server.ts"
    body = m.group(1)
    return set(re.findall(r'"([A-Za-z0-9_]+)"', body))


def test_desktop_tools_in_sync_with_python_registry():
    """DESKTOP_TOOLS (server.ts) must cover every Python-routed tool.

    The Python side routes DESKTOP_TOOL_NAMES plus any registered tools not in
    that list (e.g. currentDateTime). Node must not silently swallow them.
    """
    node_tools = _parse_desktop_tools_from_server_ts()
    py_routed = set(DESKTOP_TOOL_NAMES) | {t for t in TOOLS if t not in DESKTOP_TOOL_NAMES}
    # Underscore-prefixed names are internal helpers, never exposed to Gemini.
    py_routed = {t for t in py_routed if not t.startswith("_")}
    missing = py_routed - node_tools
    assert not missing, (
        f"server.ts DESKTOP_TOOLS is missing tools routed by Python: {sorted(missing)}"
    )


def test_all_node_desktop_tools_exist_in_python():
    """Every tool listed in server.ts DESKTOP_TOOLS must be a registered Python tool."""
    node_tools = _parse_desktop_tools_from_server_ts()
    unknown = node_tools - set(TOOLS)
    assert not unknown, f"server.ts routes tools that do not exist in Python: {sorted(unknown)}"


def test_desktop_tool_names_sync_registered_tools():
    """DESKTOP_TOOL_NAMES should not contain stale names that were never registered."""
    stale = set(DESKTOP_TOOL_NAMES) - set(TOOLS)
    assert not stale, f"registry.DESKTOP_TOOL_NAMES contains unregistered tools: {sorted(stale)}"


# ---------------------------------------------------------------------------
# F2 scenario coverage: the Node bridge dispatches to Python and the response
# shape is {ok, result, error, tool, meta.request_id}. Tool internals have
# their own tests; here we verify the dispatch contract end-to-end.
# ---------------------------------------------------------------------------

def _dispatch(tool: str, args: dict, request_id: str = "f2-scenario"):
    from desktop_agent.main import CommandDispatcher
    return CommandDispatcher.dispatch(
        MockExecuteRequest(tool, args, request_id=request_id)
    )


def test_open_application_dispatch_contract(monkeypatch):
    """'Open Notepad' routed through the dispatcher returns the success shape."""
    calls = {}

    def fake_open_app(args):
        calls["args"] = args
        return {"result": "Notepad opened and focused."}

    monkeypatch.setitem(TOOLS, "openApplication", fake_open_app)
    resp = _dispatch("openApplication", {"application": "notepad"})
    assert resp.ok is True
    assert resp.error is None
    assert resp.tool == "openApplication"
    assert "Notepad" in resp.result.get("result", "")
    assert resp.meta.get("request_id") == "f2-scenario"
    assert calls["args"]["application"] == "notepad"


def test_create_and_read_file_dispatch_contract():
    """'Create a file' then 'Read this file' via the dispatcher (real tools).

    createFile is a MODIFY tool: it requires an explicit confirmation token,
    mirroring the real desktop flow (request -> token -> execute). The token
    comes from the tool's normal result; re-dispatching with it executes.
    """
    import tempfile

    work = Path(tempfile.mkdtemp(prefix="myraa_f2_", dir=str(ROOT)))
    target = work / "myraa_f2_note.txt"
    try:
        first = _dispatch(
            "createFile", {"path": str(target), "content": "hello from f2", "overwrite": True}
        )
        assert first.ok is True
        assert first.result.get("requires_confirmation") is True
        token = first.result.get("token")
        assert token is not None
        assert not target.exists()

        create = _dispatch(
            "createFile",
            {"path": str(target), "content": "hello from f2", "overwrite": True},
            request_id="f2-create-2",
        )
        # Without the token it must still refuse (fail closed).
        assert create.result.get("requires_confirmation") is True

        create = _dispatch(
            "createFile",
            {
                "path": str(target),
                "content": "hello from f2",
                "overwrite": True,
                "confirmation_token": token,
            },
            request_id="f2-create-3",
        )
        assert create.ok is True
        assert create.result.get("requires_confirmation") is not True
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "hello from f2"

        read = _dispatch("readFile", {"path": str(target)})
        assert read.ok is True
        assert "hello from f2" in read.result.get("result", "")
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def test_system_query_dispatch_contract():
    """'System info' is a read-only tool that must succeed through dispatch."""
    resp = _dispatch("systemInfo", {})
    assert resp.ok is True
    assert resp.error is None
    assert resp.tool == "systemInfo"
    assert isinstance(resp.result, dict)
    assert resp.meta.get("request_id") == "f2-scenario"


def test_tool_failure_surfaces_real_error_not_fake_success():
    """A failing tool must return ok=False + error — never a fake success."""
    from desktop_agent import tools_files

    resp = _dispatch("readFile", {"path": "C:/__myraa_no_such_file__.txt"})
    assert resp.ok is False
    assert resp.error is not None
    assert "does not exist" in resp.error.lower() or "not exist" in resp.error.lower()
    assert resp.result is None


def test_browser_action_dispatch_contract(monkeypatch):
    """'Open a browser page' routes through dispatch with a real shape."""
    def fake_browser_open(args):
        return {"result": f"Opened browser to {args.get('url', '')}"}

    monkeypatch.setitem(TOOLS, "desktopBrowserOpen", fake_browser_open)
    resp = _dispatch("desktopBrowserOpen", {"url": "https://example.com"})
    assert resp.ok is True
    assert "example.com" in resp.result.get("result", "")
    assert resp.meta.get("request_id") == "f2-scenario"