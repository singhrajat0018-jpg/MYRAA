from __future__ import annotations

from enum import Enum, auto

from .provider_budget import ProviderBudget


class BudgetDecision(Enum):
    """
    Decision returned by the budget policy.
    """

    ALLOW = auto()

    WARN = auto()

    FALLBACK = auto()

    BLOCK = auto()


class BudgetPolicy:
    """
    Decides whether a provider can be used
    based on its remaining monthly budget.
    """

    def evaluate(
        self,
        budget: ProviderBudget,
    ) -> BudgetDecision:

        # No credits left
        if budget.remaining <= 0:
            return BudgetDecision.BLOCK

        # Critical usage
        if budget.critical:
            return BudgetDecision.FALLBACK

        # Warning threshold reached
        if budget.warning:
            return BudgetDecision.WARN

        # Safe to use
        return BudgetDecision.ALLOW

    def should_use(
        self,
        budget: ProviderBudget,
    ) -> bool:

        decision = self.evaluate(budget)

        return decision in (
            BudgetDecision.ALLOW,
            BudgetDecision.WARN,
        )

    def should_fallback(
        self,
        budget: ProviderBudget,
    ) -> bool:

        return (
            self.evaluate(budget)
            == BudgetDecision.FALLBACK
        )

    def is_blocked(
        self,
        budget: ProviderBudget,
    ) -> bool:

        return (
            self.evaluate(budget)
            == BudgetDecision.BLOCK
        )