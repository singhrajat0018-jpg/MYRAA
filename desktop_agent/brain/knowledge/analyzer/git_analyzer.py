from pathlib import Path


class GitAnalyzer:

    def analyze(
        self,
        folder: Path,
    ) -> bool:

        return (folder / ".git").exists()