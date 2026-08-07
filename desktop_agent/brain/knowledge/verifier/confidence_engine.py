class ConfidenceEngine:

    """
    Calculates confidence
    for knowledge responses.
    """

    def calculate(
        self,
        scores: list[float],
    ) -> float:

        if not scores:
            return 0.0

        return sum(scores) / len(scores)