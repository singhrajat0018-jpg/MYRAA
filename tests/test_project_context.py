from desktop_agent.brain.knowledge.services.project_context import ProjectContext
from desktop_agent.brain.knowledge.services.project_brain import ProjectBrain


class FakeProjectContextService:
    def __init__(self, context):
        self.context = context

    def get_project(self, project_name: str):
        if project_name == self.context.name:
            return self.context
        return None


def test_project_brain_surfaces_project_context():
    context = ProjectContext(
        name="MYRAA",
        root="desktop_agent",
        languages=["Python"],
        frameworks=["FastAPI"],
        entry_points=["main.py"],
    )
    brain = ProjectBrain(FakeProjectContextService(context))

    assert brain.describe("MYRAA") is not None
    assert brain.languages("MYRAA") == ["Python"]
    assert brain.frameworks("MYRAA") == ["FastAPI"]
    assert brain.entry_points("MYRAA") == ["main.py"]
    assert brain.languages("missing") == []
    assert brain.frameworks("missing") == []
    assert brain.entry_points("missing") == []
