from dataclasses import dataclass


@dataclass(slots=True)

class TickResult:

    observed: bool

    planned: bool

    executed: bool

    learned: bool

    duration: float