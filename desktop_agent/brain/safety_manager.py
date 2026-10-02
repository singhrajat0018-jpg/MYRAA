from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dangerous tool patterns — tools that touch system state or execute code.
# These are BLOCKED in autonomous mode unless explicitly confirmed.
# ---------------------------------------------------------------------------

_TOOLS_DENY_IN_AUTONOMY = frozenset({
    "runPythonScript",
    "requestPowerAction",
    "executePowerAction",
})

_TOOLS_CONFIRM = frozenset({
    "deleteFile",
    "moveFile",
    "renameFile",
    "closeApplication",
    "closeWindow",
    "writeFile",
    "writeCodeFile",
    "createPythonFile",
    "desktopBrowserFillForm",
    "enableAutoStart",
    "disableAutoStart",
    "setVolume",
    "setBrightness",
})

_DANGEROUS_ARG_PATTERNS = [
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\brestart\b", re.IGNORECASE),
    re.compile(r"\btaskkill\b", re.IGNORECASE),
    re.compile(r"\breg\s+delete\b", re.IGNORECASE),
    re.compile(r"\bcd\s+[/\\]", re.IGNORECASE),
]

_DANGEROUS_PATHS = (
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/root",
)


class SafetyManager:
    """Real execution safety layer.

    Evaluates every tool call against:
      - A deny list (autonomous mode only — blocks dangerous tools)
      - A confirm list (tools that modify system state)
      - Arg-level pattern checks (dangerous shell commands)
      - Path protection (protected OS directories)

    Returns True if safe, False if blocked.
    Logs all decisions for audit.
    """

    def check(self, tool: str, args: dict[str, Any], *, autonomous: bool = False) -> bool:
        """Evaluate whether *tool* with *args* is safe to execute.

        Parameters
        ----------
        tool : str
            Tool name (e.g. ``deleteFile``).
        args : dict
            Tool arguments.
        autonomous : bool
            If True, stricter rules apply (deny list enforced).
        """
        # 1. Deny in autonomous mode
        if autonomous and tool in _TOOLS_DENY_IN_AUTONOMY:
            log.warning("[Safety] BLOCKED in autonomous mode: tool=%s", tool)
            return False

        # 2. Arg-level dangerous patterns (always check)
        for value in args.values():
            if isinstance(value, str):
                for pattern in _DANGEROUS_ARG_PATTERNS:
                    if pattern.search(value):
                        log.warning(
                            "[Safety] BLOCKED dangerous arg pattern: tool=%s value=%s",
                            tool,
                            value,
                        )
                        return False

        # 3. Path protection (always check — applies to ALL tools)
        path_args = args.get("path", "") or args.get("destination", "") or ""
        if isinstance(path_args, str) and path_args:
            lower = path_args.lower().replace("\\", "/")
            for protected in _DANGEROUS_PATHS:
                protected_lower = protected.lower().replace("\\", "/")
                if lower.startswith(protected_lower):
                    log.warning(
                        "[Safety] BLOCKED protected path: tool=%s path=%s",
                        tool,
                        path_args,
                    )
                    return False

        # 4. Confirm-listed tools (after safety checks pass)
        if tool in _TOOLS_CONFIRM:
            log.info("[Safety] Confirm required: tool=%s", tool)
            # Still returns True so the confirmation token flow can gate it;
            # callers that support confirmation will prompt, others will allow.
            return True

        return True
