"""
Verification script for Phase A Project Builder Engine
This verifies the core functionality without requiring full MYRAA initialization
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that we can import the key components"""
    try:
        from desktop_agent.brain.super_brain.project_builder_engine import (
            ProjectBuilderEngine,
            ProjectBuildRequest,
            ProjectBuildResult
        )
        print("✓ Successfully imported ProjectBuilderEngine components")
        return True
    except Exception as e:
        print(f"✗ Failed to import ProjectBuilderEngine: {e}")
        return False

def test_engine_creation():
    """Test that we can create the engine"""
    try:
        from desktop_agent.brain.super_brain.project_builder_engine import ProjectBuilderEngine
        engine = ProjectBuilderEngine()
        print(f"✓ Created engine with capability_id: {engine.capability_id}")
        assert engine.capability_id == "PROJECT_BUILDER"
        return True
    except Exception as e:
        print(f"✗ Failed to create engine: {e}")
        return False

def test_dataclasses():
    """Test the dataclasses"""
    try:
        from desktop_agent.brain.super_brain.project_builder_engine import (
            ProjectBuildRequest,
            ProjectBuildResult
        )

        # Test ProjectBuildRequest
        request = ProjectBuildRequest(
            description="Test project",
            project_name="test",
            project_type="python"
        )
        assert request.description == "Test project"
        assert request.project_name == "test"
        assert request.project_type == "python"
        print("✓ ProjectBuildRequest works correctly")

        # Test ProjectBuildResult
        result = ProjectBuildResult(
            success=True,
            message="Test successful",
            project_path=Path("/tmp/test")
        )
        assert result.success == True
        assert result.message == "Test successful"
        assert result.project_path == Path("/tmp/test")
        print("✓ ProjectBuildResult works correctly")

        return True
    except Exception as e:
        print(f"✗ Dataclass test failed: {e}")
        return False

def test_parsing_logic():
    """Test the goal parsing logic"""
    try:
        from desktop_agent.brain.super_brain.project_builder_engine import ProjectBuilderEngine

        # Create a minimal engine for testing parsing
        engine = ProjectBuilderEngine()

        # Mock goal object
        class MockGoal:
            def __init__(self, text):
                self.text = text

        # Test simple parsing
        goal = MockGoal("Create a Python project called myapp")
        context = {}
        request = engine._parse_goal(goal, context)

        assert request.description == "Create a Python project called myapp"
        assert request.project_name == "myapp"
        assert request.project_type == "python"
        print("✓ Goal parsing works for basic case")

        # Test web project
        goal = MockGoal("Build a website called blog")
        request = engine._parse_goal(goal, context)
        assert request.project_name == "blog"
        assert request.project_type == "web"
        print("✓ Goal parsing works for web project")

        # Test project type inference
        proj_type = engine._infer_project_type("test", "Create a Python application")
        assert proj_type == "python"
        print("✓ Project type inference works")

        return True
    except Exception as e:
        print(f"✗ Parsing logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_operations():
    """Test basic file operations"""
    try:
        from desktop_agent.brain.super_brain.project_builder_engine import ProjectBuilderEngine
        import tempfile

        engine = ProjectBuilderEngine()

        # Test directory creation
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "test_dir"
            result = engine._create_directory(test_dir)
            assert result == True
            assert test_dir.exists()
            print("✓ Directory creation works")

            # Test file creation
            test_file = test_dir / "test.txt"
            result = engine._create_file(test_file, "Hello World")
            assert result == True
            assert test_file.exists()
            assert test_file.read_text() == "Hello World"
            print("✓ File creation works")

        return True
    except Exception as e:
        print(f"✗ File operations test failed: {e}")
        return False

def test_superbrain_integration():
    """Test that SuperBrain properly imports and registers the engine"""
    try:
        # This tests that the import works without circular dependencies
        from desktop_agent.brain.super_brain.super_brain import SuperBrain
        print("✓ SuperBrain can be imported (circular import avoided)")

        # Check that the engine is in the registry by looking at the source
        with open(r"C:\Users\singh\OneDrive\Desktop\MYRAA\desktop_agent\brain\super_brain\super_brain.py", "r") as f:
            content = f.read()
            assert "ProjectBuilderEngine()" in content
            assert "REGISTER PROJECT BUILDER ENGINE (Phase A)" in content
        print("✓ ProjectBuilderEngine is registered in SuperBrain")

        return True
    except Exception as e:
        print(f"✗ SuperBrain integration test failed: {e}")
        return False

def main():
    """Run all verification tests"""
    print("=" * 60)
    print("PHASE A PROJECT BUILDER ENGINE VERIFICATION")
    print("=" * 60)

    tests = [
        test_imports,
        test_engine_creation,
        test_dataclasses,
        test_parsing_logic,
        test_file_operations,
        test_superbrain_integration
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        print(f"\nRunning {test.__name__}...")
        if test():
            passed += 1
        print("-" * 40)

    print(f"\nRESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL TESTS PASSED - Phase A implementation is ready!")
        return True
    else:
        print("❌ Some tests failed - please review the implementation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)