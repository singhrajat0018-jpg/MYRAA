"""
Simple tests for Project Builder Engine that don't require full MYRAA initialization
"""
import sys
import os
from pathlib import Path

# Add the project root to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from desktop_agent.brain.super_brain.project_builder_engine import (
        ProjectBuilderEngine,
        ProjectBuildRequest,
        ProjectBuildResult
    )
    print("Successfully imported ProjectBuilderEngine")

    # Test basic instantiation
    engine = ProjectBuilderEngine()
    print(f"Engine capability_id: {engine.capability_id}")

    # Test parsing a simple goal
    class MockGoal:
        def __init__(self, text):
            self.text = text

    goal = MockGoal("Create a Python project called test")
    context = {}
    request = engine._parse_goal(goal, context)
    print(f"Parsed goal - project_name: {request.project_name}, project_type: {request.project_type}")

    # Test project type inference
    proj_type = engine._infer_project_type("test", "Create a Python application")
    print(f"Inferred project type: {proj_type}")

    # Test directory creation
    import tempfile
    temp_dir = tempfile.mkdtemp()
    test_dir = Path(temp_dir) / "test_dir"
    result = engine._create_directory(test_dir)
    print(f"Directory creation result: {result}")
    print(f"Directory exists: {test_dir.exists()}")

    # Clean up
    import shutil
    shutil.rmtree(temp_dir)

    print("All simple tests passed!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()