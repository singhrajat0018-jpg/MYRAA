from dataclasses import dataclass, field


@dataclass(slots=True)
class ProjectInfo:

    # Basic
    name: str
    root: str

    # Technologies
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)

    # Project Metadata
    package_managers: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)

    # Important Files
    entry_points: list[str] = field(default_factory=list)

    # Dependencies
    dependencies: list[str] = field(default_factory=list)

    # Version Control
    has_git: bool = False

    # Future
    confidence: float = 1.0