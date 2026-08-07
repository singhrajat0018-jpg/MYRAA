from pathlib import Path


class BuildToolAnalyzer:

    def analyze(self, folder: Path) -> list[str]:

        tools = []

        if (folder / "vite.config.ts").exists():
            tools.append("Vite")

        if (folder / "electron-builder.yml").exists():
            tools.append("Electron Builder")

        if (folder / "tsconfig.json").exists():
            tools.append("TypeScript")

        return tools