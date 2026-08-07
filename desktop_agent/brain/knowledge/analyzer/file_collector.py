from pathlib import Path


class FileCollector:

    IGNORE = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".idea",
        ".vscode",
        "dist",
        "build",
    }

    def collect(
        self,
        root: Path,
        depth: int = 3,
    ) -> set[str]:

        files = set()

        self._walk(
            root,
            files,
            depth,
        )

        return files

    # --------------------------------------------

    def _walk(
        self,
        folder: Path,
        files: set[str],
        depth: int,
    ):

        if depth < 0:
            return

        try:

            for item in folder.iterdir():

                if item.name in self.IGNORE:
                    continue

                if item.is_file():

                    files.add(item.name)

                elif item.is_dir():

                    self._walk(
                        item,
                        files,
                        depth - 1,
                    )

        except PermissionError:

            pass