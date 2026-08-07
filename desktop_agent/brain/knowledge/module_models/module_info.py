from dataclasses import dataclass, field


@dataclass
class ModuleInfo:
    name: str
    workspace: str
    root: str

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)

    dependencies: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)

    package_managers: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)

    confidence: float = 1.0