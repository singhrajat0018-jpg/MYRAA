from pathlib import Path

from .project_info import ProjectInfo
from .signatures import (
    LANGUAGE_SIGNATURES,
    FRAMEWORK_SIGNATURES,
    ENTRY_POINTS,
)


class TechnologyAnalyzer:

    def analyze(self, folder: Path) -> ProjectInfo:

        files = {f.name for f in folder.iterdir()}

        info = ProjectInfo(
            name=folder.name,
            root=str(folder),
        )

        # ----------------------------
        # Languages
        # ----------------------------

        for language, signatures in LANGUAGE_SIGNATURES.items():

            if any(sig in files for sig in signatures):

                info.languages.append(language)

        # ----------------------------
        # Frameworks
        # ----------------------------

        for framework, signatures in FRAMEWORK_SIGNATURES.items():

            if any(sig in files for sig in signatures):

                info.frameworks.append(framework)

        # ----------------------------
        # Entry Points
        # ----------------------------

        for file in files:

            if file in ENTRY_POINTS:

                info.entry_points.append(file)

        # ----------------------------
        # Git
        # ----------------------------

        if (folder / ".git").exists():

            info.has_git = True

        return info