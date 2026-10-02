"""
Permission configuration for MYRAA desktop tools.

Defines:
- Tool-to-category mapping (READ, INTERACT, MODIFY, HIGH_RISK)
- Default permission policy per category
- Tool-specific overrides
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Tool categories
READ = "READ"
INTERACT = "INTERACT"
MODIFY = "MODIFY"
HIGH_RISK = "HIGH_RISK"
DESTRUCTIVE = "DESTRUCTIVE"
SYSTEM_CRITICAL = "SYSTEM_CRITICAL"
FINANCIAL = "FINANCIAL"
SENSITIVE = "SENSITIVE"

ALL_CATEGORIES = (
    READ,
    INTERACT,
    MODIFY,
    HIGH_RISK,
    DESTRUCTIVE,
    SYSTEM_CRITICAL,
    FINANCIAL,
    SENSITIVE,
)

# Default permission policies for each category
# Values: "allow", "deny", "confirm"
DEFAULT_POLICIES = {
    READ: "allow",
    INTERACT: "allow",
    MODIFY: "confirm",
    HIGH_RISK: "confirm",
    DESTRUCTIVE: "confirm",
    SYSTEM_CRITICAL: "confirm",
    FINANCIAL: "deny",  # advisory-only; nothing may auto-execute financially
    SENSITIVE: "confirm",  # reading secrets/clipboard requires explicit confirmation
}

# Tool-specific overrides: tool name -> permission decision
# Overrides take precedence over category defaults.
TOOL_OVERRIDES = {
    # Power actions: classified SYSTEM_CRITICAL but policy is left "allow" so
    # the two-step confirmation token flow (tools_confirmation) stays the single
    # gate. The hard execution guards in tools_pc._run_power (MYRAA_TEST_MODE,
    # MYRAA_ALLOW_POWER_ACTIONS) provide the defense-in-depth behind it.
    "requestPowerAction": "allow",
    "executePowerAction": "allow",
    # The two-step confirmation token flow already gates code execution;
    # keep the network/search surface usable.
    "searchWeb": "allow",
    "searchYouTube": "allow",
    "searchGoogle": "allow",
    "searchGitHub": "allow",
}

# Tool to category mapping.
# We will build this from the DESKTOP_TOOL_NAMES list in registry.py to avoid duplication.
# However, to avoid circular imports, we will not import registry here.
# Instead, we expect the PermissionManager to be provided with the mapping.
# Alternatively, we can define the mapping here and keep it in sync with registry.
# For simplicity, we define the mapping here and expect the registry to be the source of truth.
# We will duplicate the list but ensure consistency via tests.

# Note: This mapping must be kept in sync with desktop_agent/registry.py DESKTOP_TOOL_NAMES.
TOOL_CATEGORIES = {
    # applications / websites / search
    "openApplication": INTERACT,
    "closeApplication": HIGH_RISK,  # force-terminating apps can lose unsaved work
    "openWebsite": INTERACT,
    "searchWeb": READ,
    "searchYouTube": READ,
    "searchGoogle": READ,
    "searchGitHub": READ,
    # files
    "createFile": MODIFY,
    "readFile": READ,
    "renameFile": MODIFY,
    "deleteFile": DESTRUCTIVE,
    "moveFile": MODIFY,
    "copyFile": MODIFY,
    "openFile": INTERACT,
    "writeFile": MODIFY,
    "openFolder": INTERACT,
    "listFiles": READ,
    "searchFiles": READ,
    # pc control (volume + gated power)
    "volumeUp": INTERACT,
    "volumeDown": INTERACT,
    "muteToggle": INTERACT,
    "setVolume": INTERACT,
    "requestPowerAction": SYSTEM_CRITICAL,  # gated internally by the two-step token flow
    "executePowerAction": SYSTEM_CRITICAL,  # gated internally by the two-step token flow
    # windows
    "minimizeWindow": INTERACT,
    "maximizeWindow": INTERACT,
    "activateWindow": INTERACT,
    "restoreWindow": INTERACT,
    "closeWindow": INTERACT,
    "switchApplication": INTERACT,
    # clipboard
    "copySelected": INTERACT,
    "pasteClipboard": INTERACT,  # writing to clipboard is ephemeral
    "getClipboard": SENSITIVE,  # reading clipboard may expose secrets
    "clearClipboard": INTERACT,  # clearing clipboard is ephemeral
    # screenshot / screen reading
    "takeScreenshot": READ,
    "saveScreenshot": MODIFY,
    "analyzeScreenshot": READ,
    "readScreen": READ,
    "takeRegionScreenshot": READ,
    # browser (Windows default browser only — no engine owned; separate from dormant holographic UI)
    "desktopBrowserOpen": INTERACT,
    "desktopBrowserNavigate": INTERACT,
    "desktopBrowserOpenTab": INTERACT,
    "desktopBrowserCloseTab": INTERACT,
    "desktopBrowserSearch": READ,
    "desktopBrowserClick": INTERACT,
    "desktopBrowserType": INTERACT,
    "desktopBrowserFillForm": MODIFY,  # can lead to state changes via form submission
    "desktopBrowserGoBack": INTERACT,
    "desktopBrowserGoForward": INTERACT,
    "desktopBrowserScroll": INTERACT,
    # coding assistance
    "createPythonFile": MODIFY,
    "runPythonScript": SYSTEM_CRITICAL,  # executes arbitrary code
    "createProjectFolder": MODIFY,
    "writeCodeFile": MODIFY,
    # system information
    "systemInfo": READ,
    "gpuInfo": READ,
    "temperatureInfo": READ,
    # brightness control (V2)
    "brightnessUp": INTERACT,
    "brightnessDown": INTERACT,
    "setBrightness": INTERACT,
    # Windows auto-start management (V2)
    "enableAutoStart": MODIFY,
    "disableAutoStart": MODIFY,
    "getAutoStartStatus": READ,
    # misc system reads
    "currentDateTime": READ,
    # keyboard
    "typeText": INTERACT,
    "pressKey": INTERACT,
    "keyDown": INTERACT,
    "keyUp": INTERACT,
    "hotkey": INTERACT,
    # mouse
    "moveMouse": INTERACT,
    "leftClick": INTERACT,
    "rightClick": INTERACT,
    "doubleClick": INTERACT,
    "middleClick": INTERACT,
    "dragMouse": INTERACT,
    "scrollMouse": INTERACT,
    "mousePosition": READ,
}


# ---------------------------------------------------------------------------
# Arg-aware permission rules (defense-in-depth beyond the category gate).
#
# PermissionManager.check applies these AFTER resolving the category policy.
# A rule can escalate a decision to "deny" (hard block) or "confirm" (require
# an explicit confirmation token) regardless of the category default.
# ---------------------------------------------------------------------------

# Path arguments that point at file-system targets for each tool.
PATH_CHECK_TOOLS: dict[str, list[str]] = {
    "createFile": ["path"],
    "readFile": ["path"],
    "renameFile": ["path", "new_name"],
    "deleteFile": ["path"],
    "moveFile": ["path", "destination"],
    "copyFile": ["path", "destination"],
    "openFile": ["path"],
    "openFolder": ["path"],
    "listFiles": ["path"],
    "searchFiles": ["path"],
    "createPythonFile": ["path"],
    "writeCodeFile": ["path"],
    "createProjectFolder": ["path"],
    "runPythonScript": ["path"],
}

# Windows locations the agent must never touch through file tools.
PROTECTED_PATHS = (
    r"c:\windows",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\programdata",
    r"c:\boot",
    r"c:\windows.old",
    r"c:\system volume information",
    r"c:\$recycle.bin",
    r"c:\recovery",
)

# Files that may hold secrets/config and must never be read or overwritten
# through generic file tools (they are handled by their dedicated modules).
SENSITIVE_FILENAMES = {
    ".env",
    "secrets.json",
    "memories.json",
    "settings.json",
    ".gitconfig",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    ".netrc",
}

# Escalate to confirmation for risky operations even on otherwise-safe paths.
CONFIRM_ARG_TOOLS: dict[str, list[str]] = {
    "deleteFile": ["path"],
    "moveFile": ["path", "destination"],
    "renameFile": ["path", "new_name"],
}

# Lightweight structured tool-call schema (F4): the model's tool call must
# include these non-empty arguments, otherwise the call is rejected before the
# handler runs. Handlers still perform their own deeper validation — this is a
# cheap, centralized first line of defense for the most common tools.
TOOL_REQUIRED_ARGS: dict[str, list[str]] = {
    "openApplication": ["application", "name"],  # either is acceptable (or-combo)
    "closeApplication": ["application", "name"],  # either is acceptable (or-combo)
    "createFile": ["path"],
    "readFile": ["path"],
    "writeFile": ["path"],
    "deleteFile": ["path"],
    "renameFile": ["path", "new_name"],
    "moveFile": ["path", "destination"],
    "copyFile": ["path", "destination"],
    "openFile": ["path"],
    "typeText": ["text"],
    "pressKey": ["key"],
    "openWebsite": ["name", "url"],  # either is acceptable (or-combo)
    "desktopBrowserOpen": ["name", "url"],  # either is acceptable (or-combo)
    "desktopBrowserNavigate": ["name", "url"],  # either is acceptable (or-combo)
    "runPythonScript": ["path"],
    "setVolume": ["level"],
    "setBrightness": ["level"],
}

# Tools whose required args are alternatives (at least one must be present).
# The open tools accept documented aliases (website/target/site/link/address for
# the destination, app/name for the application) so a tool call that names the
# same information differently still validates instead of being rejected by a
# url-vs-website style schema mismatch. The handlers fold the aliases onto the
# canonical 'url'/'name' via tools_websites.normalize_open_args.
OR_REQUIRED_ARGS: dict[str, list[str]] = {
    "openApplication": ["application", "name", "app"],
    "closeApplication": ["application", "name", "app"],
    "openWebsite": ["name", "url", "website", "target", "site", "link", "address"],
    "desktopBrowserOpen": ["name", "url", "website", "target", "site", "link", "address"],
    "desktopBrowserNavigate": ["name", "url", "website", "target", "site", "link", "address"],
}


def _norm(value: str) -> str:
    """Expand env vars / ~ and normalize to lowercase forward slashes."""
    expanded = os.path.expandvars(os.path.expanduser(value))
    return expanded.replace("\\", "/").strip()


def path_safety_violation(value) -> str | None:
    """Return a reason string when ``value`` is an unsafe path, else None."""
    if not isinstance(value, str) or not value.strip():
        return None
    low = _norm(value)
    if not low:
        return None

    parts = low.split("/")
    if any(part == ".." for part in parts):
        return "path contains '..' (path traversal) and is blocked"

    # PROTECTED_PATHS are stored Windows-style ("c:\\windows"); normalize them to
    # the same forward-slash, lowercased form as `low` so the prefix check matches.
    low_lower = low.lower()
    for protected in PROTECTED_PATHS:
        protected_low = protected.replace("\\", "/").strip().lower()
        if low_lower == protected_low or low_lower.startswith(protected_low + "/"):
            return f"path is inside a protected system location ({protected})"

    name = parts[-1].lower() if parts else ""
    if name in SENSITIVE_FILENAMES:
        return f"path targets a protected file ({name}) and is blocked"
    if name.endswith((".pem", ".key")) and "private" in name:
        return f"path targets a private key file ({name}) and is blocked"

    return None


def apply_arg_policies(tool_name: str, args: dict) -> tuple[str | None, str | None]:
    """Return (override, reason) for arg-level rules, else (None, None)."""
    if not isinstance(args, dict):
        return None, None

    path_args = PATH_CHECK_TOOLS.get(tool_name, [])
    for arg_name in path_args:
        violation = path_safety_violation(args.get(arg_name))
        if violation:
            return "deny", f"Permission denied for {tool_name}: {violation}"

    confirm_args = CONFIRM_ARG_TOOLS.get(tool_name, [])
    if any(args.get(a) is not None for a in confirm_args):
        return "confirm", (
            f"Tool '{tool_name}' modifies or removes files and requires "
            f"explicit user confirmation."
        )

    return None, None