"""
Observer Registry

Stores all registered background observers.

The manager discovers observers only through this registry.
"""

from __future__ import annotations

from typing import Dict, Iterable


class ObserverRegistry:

    def __init__(self) -> None:

        self._observers: Dict[str, object] = {}

    # ------------------------------------------------------

    def register(
        self,
        name: str,
        observer: object,
    ) -> None:

        if name in self._observers:
            raise ValueError(
                f"Observer '{name}' is already registered."
            )

        self._observers[name] = observer

    # ------------------------------------------------------

    def unregister(
        self,
        name: str,
    ) -> None:

        self._observers.pop(name, None)

    # ------------------------------------------------------

    def get(
        self,
        name: str,
    ) -> object | None:

        return self._observers.get(name)

    # ------------------------------------------------------

    def all(self) -> Iterable[object]:

        return self._observers.values()

    # ------------------------------------------------------

    def names(self) -> list[str]:

        return list(self._observers.keys())

    # ------------------------------------------------------

    def clear(self) -> None:

        self._observers.clear()

    # ------------------------------------------------------

    def __contains__(
        self,
        name: str,
    ) -> bool:

        return name in self._observers

    # ------------------------------------------------------

    def __len__(self) -> int:

        return len(self._observers)