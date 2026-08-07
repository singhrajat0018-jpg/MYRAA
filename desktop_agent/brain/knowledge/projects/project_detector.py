"""
MYRAA Project Detector
"""

from pathlib import Path

from .project_types import PROJECT_SIGNATURES


class ProjectDetector:

    def detect(self, folder: Path):

        if not folder.is_dir():
            return None

        names = {item.name for item in folder.iterdir()}

        for project_type, signatures in PROJECT_SIGNATURES.items():

            for signature in signatures:

                if "*" in signature:
                    for item in folder.iterdir():
                        if item.match(signature):
                            return project_type

                elif signature in names:
                    return project_type

        return None