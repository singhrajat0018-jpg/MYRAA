from pathlib import Path

class WorkspaceModuleDetector:

    IGNORE = {
        ".git",
        ".idea",
        ".vscode",
        "__pycache__",
        "node_modules",
        "node_modules - Copy",
        ".pytest_cache",
        "dist",
        "build",
        "logs",
        "screenshots",
        "ocr_test_output",
        "assets",
        "docs",
        "data",
        "Desktop",
        "agent_build",
        "src - Copy",
        "myraa",
        "tests",
    }

    MODULE_MARKERS = {
        "desktop_agent": [
            "main.py",
            "requirements.txt",
        ],
        "backend": [
            "main.py",
            "launcher.py",
            "requirements.txt",
        ],
        "electron": [
            "package.json",
            "electron-builder.yml",
        ],
        "src": [
            "package.json",
            "vite.config.ts",
        ],
    }


    def discover(self, workspace: Path):

        modules = []

        expected_modules = [
            "desktop_agent",
            "backend",
            "electron",
            "src",
        ]

        for name in expected_modules:

            folder = workspace / name

            if folder.exists() and folder.is_dir():
                modules.append(folder)

        return modules