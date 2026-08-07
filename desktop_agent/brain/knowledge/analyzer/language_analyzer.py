from pathlib import Path

from .signatures import LANGUAGE_SIGNATURES

class LanguageAnalyzer:

    def analyze(self, files: set[str]) -> list[str]:

        languages = set()

        for file in files:

            for language, signatures in LANGUAGE_SIGNATURES.items():

                if any(file.endswith(sig) for sig in signatures):

                    languages.add(language)
                    break

        return sorted(languages)