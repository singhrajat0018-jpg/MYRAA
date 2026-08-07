from dataclasses import dataclass, field


@dataclass(slots=True)
class GraphNode:

    id: str

    type: str

    name: str

    metadata: dict = field(default_factory=dict)