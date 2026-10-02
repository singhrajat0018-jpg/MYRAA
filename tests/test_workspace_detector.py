from pathlib import Path

from desktop_agent.brain.knowledge.projects.workspace_module_detector import (
    WorkspaceModuleDetector,
)


def test_workspace_module_detector_finds_expected_modules(tmp_path: Path):
    workspace = tmp_path / "workspace"
    expected = ["desktop_agent", "backend", "electron", "src"]
    ignored = ["tests", "node_modules", "docs"]

    for name in expected + ignored:
        (workspace / name).mkdir(parents=True)

    detector = WorkspaceModuleDetector()

    assert [module.name for module in detector.discover(workspace)] == expected
