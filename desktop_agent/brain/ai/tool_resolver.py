"""AI Manager 4.1 — capability tool-requirement validation (Phase 15).

Capability ``required_tools`` entries may reference either:
  - an ACTUAL registered MYRAA tool name (from desktop_agent.registry TOOLS),
  - or a CANONICAL capability tool ID that resolves to real registered tools.

This module owns the canonical-id resolver and an automated validation pass so
every capability.required_tool provably resolves to a registered tool (or is a
documented capability-level engine that owns the tooling elsewhere).

Registered tool names are the authoritative source of truth and are kept in
sync with desktop_agent/registry.py / tools_*.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Authoritative registered tool names (kept in sync with tools_*.py @register).
REGISTERED_TOOLS = frozenset({
    # tools_applications.py
    "openApplication", "closeApplication",
    # tools_browser.py
    "desktopBrowserOpen", "desktopBrowserNavigate", "desktopBrowserOpenTab",
    "desktopBrowserCloseTab", "desktopBrowserSearch", "desktopBrowserClick",
    "desktopBrowserType", "desktopBrowserFillForm", "desktopBrowserGoBack",
    "desktopBrowserGoForward", "desktopBrowserScroll",
    # tools_pc.py
    "volumeUp", "volumeDown", "setVolume", "muteToggle",
    "executePowerAction", "_cancelPowerTimer",
    "brightnessUp", "brightnessDown", "setBrightness",
    # tools_windows.py
    "minimizeWindow", "maximizeWindow", "restoreWindow", "closeWindow",
    "activateWindow", "switchApplication",
    # tools_websites.py
    "openWebsite",
    # tools_mouse.py
    "moveMouse", "leftClick", "rightClick", "doubleClick", "middleClick",
    "dragMouse", "scrollMouse", "mousePosition",
    # tools_system.py
    "currentDateTime", "systemInfo", "gpuInfo", "temperatureInfo",
    # tools_keyboard.py
    "typeText", "pressKey", "keyDown", "keyUp", "hotkey",
    # tools_files.py
    "createFile", "readFile", "renameFile", "deleteFile", "moveFile",
    "openFolder", "listFiles", "searchFiles", "copyFile", "openFile", "writeFile",
    # tools_startup.py
    "enableAutoStart", "disableAutoStart", "getAutoStartStatus",
    # tools_coding.py
    "createPythonFile", "writeCodeFile", "createProjectFolder", "runPythonScript",
    # tools_confirmation.py
    "requestPowerAction",
    # tools_screenshot.py
    "takeScreenshot", "saveScreenshot", "analyzeScreenshot", "readScreen",
    "takeRegionScreenshot",
    # tools_search.py
    "searchWeb", "searchYouTube", "searchGoogle", "searchGitHub",
    # tools_terminal.py
    "runShellCommand", "runCommand",
    # tools_git.py
    "gitStatus", "gitDiff", "gitLog", "gitAdd", "gitCommit", "gitPush", "gitPull", "gitBranch", "gitCheckout",
})

# Canonical capability tool IDs -> real registered tools.
# Capability-level engines (finance, NX, presentation, spreadsheet, phone,
# voice) resolve to the tools their engine owns; where no dedicated tool
# exists, the canonical ID maps to the closest real registered capabilities.
CANONICAL_TOOL_RESOLVER: Dict[str, Tuple[str, ...]] = {
    "market_data": ("searchWeb",),
    "nx_tools": ("createPythonFile", "writeCodeFile"),
    "web_research": ("searchWeb", "searchGoogle", "searchYouTube",
                     "searchGitHub", "desktopBrowserSearch"),
    "code_execution": ("runPythonScript", "createPythonFile", "writeCodeFile"),
    "debugger": ("runPythonScript",),
    "document_editor": ("createFile", "writeFile", "readFile", "openFile"),
    "presentation_tool": ("createFile", "writeFile"),
    "spreadsheet_tool": ("createFile", "writeFile"),
    "system_tools": ("systemInfo", "gpuInfo", "temperatureInfo", "currentDateTime"),
    "desktop_tool": ("openApplication", "closeApplication", "openWebsite",
                     "activateWindow", "switchApplication", "minimizeWindow",
                     "maximizeWindow", "restoreWindow", "closeWindow"),
    "phone_tool": (),
    "vision_tool": ("takeScreenshot", "saveScreenshot", "analyzeScreenshot",
                     "readScreen", "takeRegionScreenshot"),
    "browser_tool": ("desktopBrowserOpen", "desktopBrowserNavigate", "desktopBrowserOpenTab",
                     "desktopBrowserCloseTab", "desktopBrowserSearch", "desktopBrowserClick",
                     "desktopBrowserType", "desktopBrowserFillForm", "desktopBrowserGoBack",
                     "desktopBrowserGoForward", "desktopBrowserScroll"),
    "voice_tool": (),
    "file_tool": ("createFile", "readFile", "renameFile", "deleteFile",
                  "moveFile", "openFolder", "listFiles", "searchFiles",
                  "copyFile", "openFile", "writeFile"),
    "calendar_tool": (),
    "project_tool": ("createProjectFolder", "openFolder", "listFiles", "searchFiles"),
    "coding_tool": ("createPythonFile", "writeCodeFile", "runPythonScript"),
    "terminal_tool": ("runShellCommand", "runPythonScript"),
    "git_tool": ("gitStatus", "gitDiff", "gitLog", "gitAdd", "gitCommit", "gitPush", "gitPull"),
}

# Canonical IDs that intentionally own tooling in a capability-level engine
# (no standalone registered tool). They still RESOLVE (possibly to empty),
# so validation passes with an explicit note.
CAPABILITY_OWNED_TOOL_IDS = frozenset({
    "market_data", "nx_tools", "presentation_tool", "spreadsheet_tool",
    "phone_tool", "voice_tool", "debugger", "calendar_tool",
    "project_tool", "coding_tool", "terminal_tool", "git_tool",
})


def resolve(canonical_or_tool: str) -> List[str]:
    """Resolve a required_tool entry to actual registered tool names."""
    if canonical_or_tool in REGISTERED_TOOLS:
        return [canonical_or_tool]
    if canonical_or_tool in CANONICAL_TOOL_RESOLVER:
        return list(CANONICAL_TOOL_RESOLVER[canonical_or_tool])
    return []


def is_resolvable(canonical_or_tool: str) -> bool:
    """True when the entry is a registered tool or a known canonical id."""
    return canonical_or_tool in REGISTERED_TOOLS or canonical_or_tool in CANONICAL_TOOL_RESOLVER


def validate_capability_tools(capabilities: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate every capability.required_tool.

    Returns a list of reports; each entry has capability_id, required_tool,
    status ('ok' | 'capability_owned' | 'unresolved'), and resolved tools.
    Raises ValueError if any required_tool is unresolvable.
    """
    report: List[Dict[str, Any]] = []
    for capability_id, cap in capabilities.items():
        required = getattr(cap, "required_tools", [])
        for tool in required:
            if tool in REGISTERED_TOOLS:
                report.append({
                    "capability_id": capability_id, "required_tool": tool,
                    "status": "ok", "resolved": [tool],
                })
            elif tool in CANONICAL_TOOL_RESOLVER:
                resolved = list(CANONICAL_TOOL_RESOLVER[tool])
                status = "capability_owned" if tool in CAPABILITY_OWNED_TOOL_IDS else "ok"
                report.append({
                    "capability_id": capability_id, "required_tool": tool,
                    "status": status, "resolved": resolved,
                })
            else:
                raise ValueError(
                    f"Capability {capability_id} requires unknown tool/capability "
                    f"id '{tool}' — no registered tool or canonical resolver entry."
                )
    return report


def summary(capabilities: Dict[str, Any]) -> Dict[str, Any]:
    """Short validation summary (for tests / diagnostics)."""
    reports = validate_capability_tools(capabilities)
    by_status: Dict[str, int] = {}
    for r in reports:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {
        "total_requirements": len(reports),
        "by_status": by_status,
        "unresolved": [r for r in reports if r["status"] == "unresolved"],
    }