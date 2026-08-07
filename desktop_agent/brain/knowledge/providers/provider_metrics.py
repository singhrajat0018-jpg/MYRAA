import time


class ProviderMetrics:

    def __init__(self):

        self.calls = 0

        self.failures = 0

        self.total_latency = 0.0

    def begin(self):

        return time.perf_counter()

    def end(
        self,
        started,
        success=True,
    ):

        self.calls += 1

        self.total_latency += (
            time.perf_counter()
            - started
        )

        if not success:
            self.failures += 1

    @property
    def average_latency(self):

        if self.calls == 0:
            return 0.0

        return self.total_latency / self.calls