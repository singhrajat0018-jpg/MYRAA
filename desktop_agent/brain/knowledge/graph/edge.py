from dataclasses import dataclass


@dataclass(slots=True)
class GraphEdge:

    source: str

    relation: str

    target: str