"""
MYRAA Desktop Control V3
Process Manager

Responsibilities:
- List running processes
- Check if process is running
- Find process
- Kill process
- Get process info

No AI logic.
No Planner logic.
"""

from __future__ import annotations
from typing import List, Optional
from .models import ProcessInfo
import psutil

class ProcessManager:

    # -----------------------------
    # Query
    # -----------------------------

    def list_processes(self) -> List[ProcessInfo]:

        processes = []

        for proc in psutil.process_iter(
            ["pid", "name", "exe", "status"]
        ):

            try:
                processes.append(
                    ProcessInfo(
                        pid=proc.info["pid"],
                        name=proc.info["name"] or "",
                        exe=proc.info["exe"] or "",
                        status=proc.info["status"] or ""
                    )
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        return processes

    def is_running(self, process_name: str) -> bool:

        process_name = process_name.lower()

        for proc in psutil.process_iter(["name"]):

            try:

                name = proc.info["name"]

                if name and process_name in name.lower():
                    return True

            except Exception:
                continue

        return False

    def find_process(self, process_name: str) -> Optional[ProcessInfo]:

        process_name = process_name.lower()

        for proc in psutil.process_iter(
            ["pid", "name", "exe", "status"]
        ):

            try:

                name = proc.info["name"]

                if name and process_name in name.lower():

                    return ProcessInfo(
                        pid=proc.info["pid"],
                        name=name,
                        exe=proc.info["exe"] or "",
                        status=proc.info["status"] or ""
                    )

            except Exception:
                continue

        return None

    # -----------------------------
    # Actions
    # -----------------------------

    def kill_process(self, process_name: str) -> bool:

        process_name = process_name.lower()

        for proc in psutil.process_iter(["name"]):

            try:

                name = proc.info["name"]

                if name and process_name in name.lower():

                    proc.kill()

                    return True

            except Exception:
                continue

        return False

    # -----------------------------
    # Utilities
    # -----------------------------

    def get_process_info(self, process_name: str) -> Optional[dict]:

        process = self.find_process(process_name)

        if process is None:
            return None

        return process.to_dict()

    def force_terminate(self, process_name: str) -> bool:
        return self.kill_process(process_name)


    def wait_until_closed(self, process_name: str, timeout: float = 5.0) -> bool:
        import time

        end = time.time() + timeout

        while time.time() < end:
            if not self.is_running(process_name):
                return True
            time.sleep(0.2)

        return False