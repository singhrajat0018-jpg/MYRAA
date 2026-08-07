from __future__ import annotations


class VerificationManager:
    """
    Verifies execution results.
    """

    def verify(self, result):

        if result is None:
            raise RuntimeError("Execution returned no result.")

        return True