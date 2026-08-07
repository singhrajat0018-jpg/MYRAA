"""
Application control: launch and close common Windows applications.

Launch strategy is layered for robustness:
  1. Try a known executable / shell verb (fastest, most reliable).
  2. Fall back to the Windows "where"/App Paths lookup via `start`.

Closing uses taskkill on the matching process image name, with a graceful
grace period so apps can save work.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any, Dict
import ctypes
from ctypes import wintypes
from .desktop.windows.application_locator import ApplicationLocator
from .registry import ToolError, register
from .desktop.windows.process_manager import ProcessManager
from .desktop.windows.window_manager import WindowManager

# Canonical app key -> (launch_command, kind)
#   kind == "exe"   : launch_command is the executable name (resolved via PATH/App Paths)
#   kind == "shell" : launch_command is a shell builtin verb run with cmd /c
#   kind == "uwp"   : launch_command is an apps-family activation string
APP_COMMANDS: Dict[str, Dict[str, str]] = {
    "notepad": {"exe": "notepad.exe", "image": "notepad.exe", "label": "Notepad"},
    "chrome": {"exe": "chrome.exe", "image": "chrome.exe", "label": "Google Chrome"},
    "edge": {"exe": "msedge.exe", "image": "msedge.exe", "label": "Microsoft Edge"},
    "vscode": {"exe": "code.cmd", "image": "Code.exe", "label": "Visual Studio Code"},
    "calculator": {"shell": "calc", "image": "CalculatorApp.exe", "label": "Calculator"},
    "calc": {"shell": "calc", "image": "CalculatorApp.exe", "label": "Calculator"},
    "file explorer": {"shell": "explorer", "image": "explorer.exe", "label": "File Explorer"},
    "explorer": {"shell": "explorer", "image": "explorer.exe", "label": "File Explorer"},
    "task manager": {"shell": "taskmgr", "image": "Taskmgr.exe", "label": "Task Manager"},
    "taskmanager": {"shell": "taskmgr", "image": "Taskmgr.exe", "label": "Task Manager"},
    "settings": {"uwp": "ms-settings:", "image": "SystemSettings.exe", "label": "Settings"},
    "command prompt": {"exe": "cmd.exe", "image": "cmd.exe", "label": "Command Prompt"},
    "cmd": {"exe": "cmd.exe", "image": "cmd.exe", "label": "Command Prompt"},
    "powershell": {"exe": "powershell.exe", "image": "powershell.exe", "label": "PowerShell"},
    "wordpad": {"shell": "write", "image": "wordpad.exe", "label": "WordPad"},
    "paint": {"shell": "mspaint", "image": "mspaint.exe", "label": "Paint"},
    "snipping tool": {"uwp": "ms-screenclip:", "image": "ScreenClippingHost.exe", "label": "Snipping Tool"},
}


def _resolve_app(key: str) -> Dict[str, str]:
    norm = (key or "").strip().lower()
    if norm in APP_COMMANDS:
        return APP_COMMANDS[norm]
    # Allow loose aliases (e.g. "code", "visual studio code").
    aliases = {
        "code": "vscode",
        "visual studio code": "vscode",
        "vs code": "vscode",
        "google chrome": "chrome",
        "microsoft edge": "edge",
        "calc": "calculator",
        "settings app": "settings",
        "file explorer": "file explorer",
        "windows explorer": "file explorer",
    }
    if norm in aliases and aliases[norm] in APP_COMMANDS:
        return APP_COMMANDS[aliases[norm]]
    raise ToolError(
        f"Unrecognized application '{key}'. Supported: "
        f"{', '.join(sorted({v['label'] for v in APP_COMMANDS.values()}))}."
    )


def _launch(spec):

   
    def find_executable(exe: str):
        # PATH
        path = shutil.which(exe)
        if path:
            return path

        local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

        common = {
            "chrome.exe": [
                os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
            ],
            "msedge.exe": [
                os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
            ],
            "code.cmd": [
                os.path.join(local, "Programs", "Microsoft VS Code", "bin", "code.cmd"),
            ],
        }

        for candidate in common.get(exe.lower(), []):
            if os.path.exists(candidate):
                return candidate

        return None

    try:

        if "exe" in spec:

            exe = spec["exe"]

            resolved = find_executable(exe)

            if resolved:

                subprocess.Popen(
                    [resolved],
                    shell=False,
                    close_fds=True,
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )

            else:

                subprocess.Popen(
                    f'start "" "{exe}"',
                    shell=True,
                    close_fds=True,
                )

        elif "shell" in spec:

            subprocess.Popen(
                f'start "" {spec["shell"]}',
                shell=True,
                close_fds=True,
            )

        elif "uwp" in spec:

            subprocess.Popen(
                f'start "" {spec["uwp"]}',
                shell=True,
                close_fds=True,
            )

        else:

            raise ToolError(f"App spec for {spec.get('label')} is incomplete.")

    except Exception as e:

        raise ToolError(
            f"Could not launch {spec.get('label')}: {e}"
        ) from e


@register("openApplication")
def open_application(args: Dict[str, Any]) -> Dict[str, Any]:


    print("STEP 1: open_application started")

    # launch se pehle
    print("STEP 2: launching application")

    # subprocess ya launcher ke turant baad
    print("STEP 3: application launched")

    # agar wait/focus logic hai
    print("STEP 4: waiting for window")

    # return se pehle
    print("STEP 5: returning success")

    name = args.get("name") or args.get("application")

    if not name:
        raise ToolError("Parameter 'name' (application name) is required.")

    spec = _resolve_app(str(name))

    # -------- Desktop V3 --------

    locator = ApplicationLocator()

    locator = ApplicationLocator()

    info = locator.locate(str(name))

    # Already running
    if info.running:
        locator.focus(str(name))
        return {
            "result": f"{spec['label']} is already running. Focused existing window."
        }

    # Launch
    _launch(spec)

    # Wait until detected
    for _ in range(20):

        time.sleep(0.25)

        info = locator.locate(str(name))

        if info.running:

            locator.focus(str(name))

            return {
                "result": f"{spec['label']} opened and focused."
            }

    raise ToolError(
        f"Failed to detect '{spec['label']}' after launch."
    )

def _is_process_running(image: str) -> bool:
    result = subprocess.run(
        f'tasklist /FI "IMAGENAME eq {image}"',
        shell=True,
        capture_output=True,
        text=True,
    )

    return image.lower() in result.stdout.lower()

@register("closeApplication")
def close_application(args: Dict[str, Any]) -> Dict[str, Any]:

    name = args.get("name") or args.get("application")

    if not name:
        raise ToolError("Parameter 'name' (application name) is required.")

    spec = _resolve_app(str(name))
    image = spec["image"]
    process_manager = ProcessManager()

    try:

        if image.lower() == "explorer.exe":
            WindowManager.close_explorer_windows()

        else:

            result = subprocess.run(
                f'taskkill /IM "{image}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:

                raise ToolError(
                    result.stderr.strip()
                    or result.stdout.strip()
                )

        time.sleep(0.5)

        # Explorer is the Windows shell.
        # Closing Explorer windows must never terminate explorer.exe.
        if image.lower() != "explorer.exe":

            if process_manager.is_running(image):

                print(f"{image} still running... killing process.")

                if not process_manager.kill_process(image):
                    raise ToolError(
                        f"Failed to kill {spec['label']}."
                    )

                time.sleep(0.5)

                if process_manager.is_running(image):
                    raise ToolError(
                        f"Failed to close {spec['label']}."
                    )

        return {
            "result": f"Closed {spec['label']}."
        }

    except Exception as e:
        raise ToolError(
            f"Could not close {spec['label']}: {e}"
        ) from e