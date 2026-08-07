from pathlib import Path

from ..analyzer.project_analyzer import ProjectAnalyzer


class ProjectIndexer:

    PROJECT_MARKERS = {
        ".git",
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "*.sln",
    }

    def __init__(self, db):

        self.db = db
        self.analyzer = ProjectAnalyzer()

    # ---------------------------------------------------------

    def is_project(self, folder: Path):

        IGNORE_DIRS = {
            "__pycache__",
            "node_modules",
            ".git",
            ".pytest_cache",
            "venv",
            ".venv",
            "dist",
            "build",
            ".cache",
            ".idea",
            ".vscode",
        }

        if not folder.is_dir():
            return False

        if folder.name in IGNORE_DIRS:
            return False

        # If this folder is the MYRAA workspace
        if (folder / "package.json").exists():
            return True

        for child in folder.iterdir():
            if child.name in self.PROJECT_MARKERS:

                # If parent is already the workspace, don't treat this folder as a project
                if (folder.parent / "package.json").exists():
                    return False

                return True

            if child.suffix == ".sln":
                return True

        return False

    # ---------------------------------------------------------

    def index(self, folder: Path):

        if not self.is_project(folder):
            return

        info = self.analyzer.analyze(folder)

        cursor = self.db.conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO projects
            (
                root,
                name,
                languages,
                frameworks,
                has_git,
                confidence
            )
            VALUES
            (?, ?, ?, ?, ?, ?)
            """,
            (
                info.root,
                info.name,
                ",".join(info.languages),
                ",".join(info.frameworks),
                int(info.has_git),
                info.confidence,
            ),
        )

        self.db.conn.commit()

        print(f"[ProjectIndexer] Indexed project: {info.name}")