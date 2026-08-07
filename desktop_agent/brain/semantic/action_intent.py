from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ActionIntent:
    """
    Generic desktop action.

    Examples
    --------
    openFolder {"name":"downloads"}

    becomes

    ActionIntent(
        name="openFolder",
        parameters={"name":"downloads"},
    )
    """

    name: str

    parameters: dict[str, Any] = field(default_factory=dict)

    confidence: float = 1.0