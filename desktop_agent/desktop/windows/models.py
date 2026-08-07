from dataclasses import dataclass
from typing import Optional

@dataclass
class WindowInfo:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int
    is_active: bool


@dataclass
class ProcessInfo:
    pid: int
    name: str
    exe: str
    status: str


@dataclass
class ApplicationInfo:
    name: str
    installed: bool
    running: bool

    pid: Optional[int] = None
    process_name: Optional[str] = None
    exe: Optional[str] = None
    status: Optional[str] = None

    hwnd: Optional[int] = None
    title: Optional[str] = None