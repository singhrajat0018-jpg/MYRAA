"""
Terminal/Shell execution tools for project building.

Provides safe shell command execution with:
- Working directory control
- Timeout support
- Output capture
- Exit code verification
- Environment isolation
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .registry import ToolError, register


def _resolve_working_dir(path: Optional[str]) -> Path:
    """Resolve working directory, defaulting to project root or cwd."""
    if not path:
        return Path.cwd()
    p = Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()
    return p


def _ensure_safe_command(cmd: str) -> None:
    """Block dangerous commands — defense-in-depth, not a sole gate."""
    import re
    dangerous_patterns = [
        r"rm\s+-rf\s+/",
        r"format\s+[cC]:",
        r"del\s+/[fs]",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bmkfs\b",
        r"dd\s+if=",
        r">\s*/dev/",
        r"\bdiskpart\b",
        r"\bbcdboot\b",
        r"\brobocopy\s.*/MIR",
        r"\bschtasks\b",
        r"\breg\s+delete\b",
        r"\bicacls\b.*(/T|/S)",
        r"Remove-Item.*-Recurse.*-Force",
        r"\bnet\s+user\b.*\b(add|delete)\b",
        r"\bcertutil\b.*-urlcache",
        r"\bwmic\b",
        r"\bGet-WmiObject\b",
        r"\bSet-Content\b.*-Value.*\bPATH\b",
        r"\b\$env:PATH\b.*=",
        r"PATH\s*=.*:",
        r"\b(sudo|RunAs)\b",
        r"\bWrite-Host\b.*-NoNewline.*\b>\s*[a-zA-Z]:",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, cmd, re.IGNORECASE):
            raise ToolError(f"Command blocked for safety: matches dangerous pattern '{pattern}'")


@register("runShellCommand")
def run_shell_command(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a shell command and return structured results.
    
    Args:
        command: Command to execute (string or list of args)
        cwd: Working directory (optional, defaults to current directory)
        timeout: Timeout in seconds (default: 60)
        env: Environment variables dict (optional)
        shell: Whether to run through shell (default: True for string commands)
        
    Returns:
        Dict with: ok, stdout, stderr, exit_code, command, duration_ms
    """
    command = args.get("command")
    if not command:
        raise ToolError("Parameter 'command' is required.")
    
    cwd = _resolve_working_dir(args.get("cwd"))
    timeout = int(args.get("timeout", 60))
    env = args.get("env")
    shell = args.get("shell", True)
    
    # Prepare environment — do NOT allow env var override of PATH/sensitive vars
    full_env = os.environ.copy()
    if env:
        _blocked_keys = {"PATH", "PYTHONPATH", "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "windir", "SYSTEMROOT", "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH"}
        for k, v in env.items():
            if k.upper() in _blocked_keys:
                raise ToolError(f"Environment variable '{k}' cannot be overridden for security.")
            full_env[k] = v
    
    # Safety check
    if isinstance(command, str):
        _ensure_safe_command(command)
    elif isinstance(command, list):
        for part in command:
            _ensure_safe_command(str(part))
    
    # Execute
    start_time = __import__("time").time()
    try:
        if isinstance(command, str) and shell:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=full_env,
            )
        else:
            if isinstance(command, str):
                cmd_list = shlex.split(command)
            else:
                cmd_list = command
            proc = subprocess.run(
                cmd_list,
                shell=False,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=full_env,
            )
    except subprocess.TimeoutExpired:
        duration = (__import__("time").time() - start_time) * 1000
        return {
            "ok": False,
            "error": f"Command timed out after {timeout}s",
            "command": command,
            "timeout": True,
            "duration_ms": duration,
        }
    except Exception as e:
        duration = (__import__("time").time() - start_time) * 1000
        raise ToolError(f"Command execution failed: {e}")
    
    duration = (__import__("time").time() - start_time) * 1000
    
    # Trim large outputs
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if len(stdout) > 10000:
        stdout = stdout[:10000] + "\n...[truncated]"
    if len(stderr) > 5000:
        stderr = stderr[:5000] + "\n...[truncated]"
    
    return {
        "ok": True,
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "duration_ms": duration,
        "cwd": str(cwd),
    }


@register("runCommand")
def run_command(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a command (alias for runShellCommand with shell=False by default).
    
    Args:
        command: Command to execute (list of args or string)
        cwd: Working directory
        timeout: Timeout in seconds
        env: Environment variables
        
    Returns:
        Same as runShellCommand
    """
    # Default to shell=False for explicit command lists
    if "shell" not in args:
        args["shell"] = False
    return run_shell_command(args)


__all__ = ["run_shell_command", "run_command"]