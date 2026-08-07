from dataclasses import dataclass

from .query_type import QueryType


@dataclass(slots=True)
class RoutingResult:

    query_type: QueryType

    providers: list[str]

    use_local: bool

    use_external: bool

    priority: int = 50