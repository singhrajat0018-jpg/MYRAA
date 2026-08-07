"""
Base Observer

All background observers must inherit from this class.

Responsibilities
----------------
- Observe external systems.
- Produce ObserverEvent objects.
- Never execute actions directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..event import ObserverEvent


class BaseObserver(ABC):

    def __init__(self, name: str) -> None:

        self.name = name

        self.enabled = True

    # ------------------------------------------------------

    def start(self) -> None:
        """Called when the observer starts."""
        pass

    # ------------------------------------------------------

    def stop(self) -> None:
        """Called when the observer stops."""
        pass

    # ------------------------------------------------------

    @abstractmethod
    def poll(self) -> list[ObserverEvent]:
        """
        Observe the current system state.

        Returns
        -------
        list[ObserverEvent]
            Zero or more events.
        """
        raise NotImplementedError

    # ------------------------------------------------------

    def __repr__(self) -> str:

        return f"{self.__class__.__name__}(name='{self.name}')"