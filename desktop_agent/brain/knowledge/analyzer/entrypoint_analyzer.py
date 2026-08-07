from pathlib import Path

from .signatures import ENTRY_POINTS


class EntryPointAnalyzer:

    def analyze(
        self,
        files: set[str],
    ) -> list[str]:

        entry_points = []

        for file in files:

            if file in ENTRY_POINTS:

                entry_points.append(file)

        return entry_points