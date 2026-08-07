from dataclasses import dataclass


@dataclass(slots=True)
class ProviderBudget:

    provider: str

    monthly_limit: int

    used: int = 0

    warning_threshold: float = 0.80

    critical_threshold: float = 0.95

    @property
    def remaining(self) -> int:

        return max(
            self.monthly_limit - self.used,
            0,
        )

    @property
    def usage_ratio(self) -> float:

        if self.monthly_limit == 0:
            return 1.0

        return self.used / self.monthly_limit

    @property
    def warning(self) -> bool:

        return (
            self.usage_ratio
            >= self.warning_threshold
        )

    @property
    def critical(self) -> bool:

        return (
            self.usage_ratio
            >= self.critical_threshold
        )