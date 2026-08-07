from dataclasses import dataclass, field


@dataclass(slots=True)
class SymbolInfo:

    workspace: str

    module: str

    file: str

    name: str

    symbol_type: str

    language: str

    line: int

    end_line: int

    parent: str | None = None

    signature: str = ""

    decorators: list[str] = field(default_factory=list)

    imports: list[str] = field(default_factory=list)

    exported: bool = False

    confidence: float = 1.0