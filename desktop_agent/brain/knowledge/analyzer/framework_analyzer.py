from pathlib import Path

from .signatures import FRAMEWORK_SIGNATURES


class FrameworkAnalyzer:

    def analyze(
        self,
        files: set[str],
    ) -> list[str]:

        frameworks = []

        for framework, signatures in FRAMEWORK_SIGNATURES.items():

            if any(sig in files for sig in signatures):

                frameworks.append(framework)

        return frameworks