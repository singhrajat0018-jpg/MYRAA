from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProjectContext:

    name: str
    root: str

    languages: List[str] = field(default_factory=list)

    frameworks: List[str] = field(default_factory=list)

    dependencies: List[str] = field(default_factory=list)

    entry_points: List[str] = field(default_factory=list)

    recent_files: List[str] = field(default_factory=list)

    important_files: List[str] = field(default_factory=list)

    package_managers: List[str] = field(default_factory=list)

    build_tools: List[str] = field(default_factory=list)

    git_branch: Optional[str] = None

    has_git: bool = False

    running: bool = False

    confidence: float = 0.0