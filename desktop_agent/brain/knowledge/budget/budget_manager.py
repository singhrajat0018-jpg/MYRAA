from .provider_budget import ProviderBudget
from .budget_policy import BudgetPolicy

class BudgetManager:

    def __init__(self):

        self._budgets = {}

        self.policy = BudgetPolicy()

    def register(
        self,
        provider: str,
        monthly_limit: int,
    ):

        self._budgets[provider] = ProviderBudget(
            provider=provider,
            monthly_limit=monthly_limit,
        )

    def consume(
        self,
        provider: str,
        credits: int = 1,
    ):

        budget = self._budgets.get(provider)

        if budget:

            budget.used += credits

    def remaining(
        self,
        provider: str,
    ) -> int:

        budget = self._budgets.get(provider)

        if budget is None:
            return 0

        return budget.remaining

    def can_use(
        self,
        provider: str,
    ) -> bool:

        budget = self._budgets.get(provider)

        if budget is None:
            return True

        return budget.remaining > 0

    def decision(
        self,
        provider: str,
    ):

        budget = self._budgets.get(provider)

        if budget is None:
            return None

        return self.policy.evaluate(budget)


    def should_use(
        self,
        provider: str,
    ) -> bool:

        budget = self._budgets.get(provider)

        if budget is None:
            return True

        return self.policy.should_use(budget)


    def should_fallback(
        self,
        provider: str,
    ) -> bool:

        budget = self._budgets.get(provider)

        if budget is None:
            return False

        return self.policy.should_fallback(budget)