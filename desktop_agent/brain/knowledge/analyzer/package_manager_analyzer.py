from pathlib import Path


class PackageManagerAnalyzer:

    def analyze(self, folder: Path) -> list[str]:

        managers = []

        if (folder / "package-lock.json").exists() or (folder / "package.json").exists():
            managers.append("npm")

        if (folder / "yarn.lock").exists():
            managers.append("yarn")

        if (folder / "pnpm-lock.yaml").exists():
            managers.append("pnpm")

        return managers