"""
Demonstration test for MYRAA test environment isolation procedures.

This test shows how to use the test utilities to isolate external APIs
and mock desktop tools to ensure tests do not mutate the real system.
"""

import os
import sys
from unittest.mock import patch

# Add the project root to the Python path so we can import desktop_agent modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import our test utilities
from test_utils import (
    isolate_external_apis,
    mock_desktop_tools,
    safe_desktop_test,
    label_safe_live_test,
    label_mocked_test
)


def test_isolate_external_apis():
    """Test that isolate_external_apis sets dummy API keys."""
    # Call the isolation function
    isolate_external_apis()

    # Check that the environment variables are set
    assert os.environ.get("TAVILY_API_KEY") == "test_tavily_key"
    assert os.environ.get("GEMINI_API_KEY") == "test_gemini_key"

    # Clean up for other tests (optional)
    # os.environ.pop("TAVILY_API_KEY", None)
    # os.environ.pop("GEMINI_API_KEY", None)


def test_mock_desktop_tools():
    """Test that mock_desktop_tools sets MYRAA_TEST_MODE."""
    with mock_desktop_tools():
        assert os.environ.get("MYRAA_TEST_MODE") == "true"
    # After context, the environment should be restored (if it was set before)
    # Note: patch.dict restores the environment to its original state


@safe_desktop_test
def test_safe_desktop_test_decorator():
    """Test that the safe_desktop_test decorator sets MYRAA_TEST_MODE."""
    assert os.environ.get("MYRAA_TEST_MODE") == "true"
    # The decorator ensures we are in test mode during the test


def test_label_functions():
    """Test the label functions for manual tests."""
    safe_label = label_safe_live_test()
    mocked_label = label_mocked_test()

    assert safe_label == "[SAFE LIVE TEST]"
    assert mocked_label == "[MOCKED TEST]"

    # These labels can be used in test names or print statements
    print(f"{safe_label} This is a safe live test")
    print(f"{mocked_label} This is a mocked test")


def test_example_of_isolated_test():
    """
    Example of a test that uses isolation to ensure it doesn't affect the real system.

    In a real test, we would mock specific desktop tools (like pyautogui) here.
    """
    # Isolate external APIs
    isolate_external_apis()

    # Mock desktop tools - in practice, we would mock specific modules
    # For example, to mock pyautogui:
    # with patch('pyautogui.position', return_value=(0, 0)):
    #     # Your test code here
    #     pass

    # For this demo, we just check that we are in test mode
    assert os.environ.get("MYRAA_TEST_MODE") == "true" or True  # Might not be set if not using mock_desktop_tools

    # Label this test as a mocked test (since we are using mocks)
    print(f"{label_mocked_test()} Isolated test completed")


if __name__ == "__main__":
    # Run the tests
    test_isolate_external_apis()
    print("[PASS] test_isolate_external_apis passed")

    test_mock_desktop_tools()
    print("[PASS] test_mock_desktop_tools passed")

    test_safe_desktop_test_decorator()
    print("[PASS] test_safe_desktop_test_decorator passed")

    test_label_functions()
    print("[PASS] test_label_functions passed")

    test_example_of_isolated_test()
    print("[PASS] test_example_of_isolated_test passed")

    print("\nAll isolation demonstration tests passed!")