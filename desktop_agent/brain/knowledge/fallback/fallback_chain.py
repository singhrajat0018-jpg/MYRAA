from dataclasses import dataclass


@dataclass(slots=True)
class FallbackChain:

    primary: str

    alternatives: list[str]