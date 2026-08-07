from enum import Enum, auto


class QueryType(Enum):
    """
    High-level categories used for routing.
    """

    LOCAL = auto()

    GENERAL = auto()

    RESEARCH = auto()

    NEWS = auto()

    WEATHER = auto()

    FINANCE = auto()

    PROGRAMMING = auto()

    GITHUB = auto()

    WIKIPEDIA = auto()

    DOCUMENT = auto()

    UNKNOWN = auto()