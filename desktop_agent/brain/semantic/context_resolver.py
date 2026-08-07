"""
MYRAA Cognitive Engine
Context Resolver

Responsibility
--------------

Resolve ambiguous references using
the current world state.

Examples

Close it
↓

Chrome

Open that project

↓

MYRAA

Continue coding

↓

Previous coding session

This module NEVER executes anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models import BrainContext
from .semantic_models import SemanticContext


class ContextResolver:
    """
    Resolves contextual references.
    """

    def __init__(self):

        pass

    # ---------------------------------------------------------

    def build_context(
        self,
        brain_context: Optional[BrainContext],
    ) -> SemanticContext:
        """
        Convert BrainContext into SemanticContext.
        """

        if brain_context is None:

            return SemanticContext()

        return SemanticContext(

            active_app=brain_context.active_app,

            active_window=brain_context.active_window,

            metadata=brain_context.metadata.copy(),
        )

    # ---------------------------------------------------------

    def resolve_pronoun(
        self,
        pronoun: str,
        context: SemanticContext,
    ) -> Optional[str]:
        """
        Resolve pronouns such as

        it

        this

        that
        """

        pronoun = pronoun.lower()

        if pronoun in ("it", "this", "that"):

            if context.active_app:

                return context.active_app

        return None

    # ---------------------------------------------------------

    def resolve_application(
        self,
        application: Optional[str],
        context: SemanticContext,
    ) -> Optional[str]:

        if application:

            return application

        return context.active_app

    # ---------------------------------------------------------

    def resolve_window(
        self,
        window: Optional[str],
        context: SemanticContext,
    ) -> Optional[str]:

        if window:

            return window

        return context.active_window