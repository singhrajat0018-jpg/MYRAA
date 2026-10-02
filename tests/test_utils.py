"""
Test utilities for MYRAA test environment isolation.

Provides helper functions and fixtures to ensure tests are isolated
and do not affect the real system or external services.
"""

import os
import sys
from unittest.mock import MagicMock, patch

def isolate_external_apis():
    """
    Isolate external APIs by setting dummy environment variables.
    This should be called at the start of each test session or test.
    """
    # Set dummy API keys to prevent accidental calls to real services.
    # Direct assignment (not setdefault) so the dummy keys take precedence over
    # values pre-seeded by conftest.py's isolation (e.g. empty strings).
    os.environ["TAVILY_API_KEY"] = "test_tavily_key"
    os.environ["GEMINI_API_KEY"] = "test_gemini_key"
    # Add other API keys as needed

def mock_desktop_tools():
    """
    Mock desktop tools that interact with the real system.
    Returns a context manager that can be used in tests.
    """
    # This is a placeholder; in practice, we would mock specific tools
    # For example, we might return a patch for pyautogui, subprocess, etc.
    # We'll return a generic patch that does nothing, to be replaced by specific mocks
    return patch.dict('os.environ', {'MYRAA_TEST_MODE': 'true'})

def safe_desktop_test(func):
    """
    Decorator to mark a test as a safe desktop test that uses mocks
    and should not mutate the real desktop.
    """
    def wrapper(*args, **kwargs):
        # Ensure we are in test mode
        os.environ['MYRAA_TEST_MODE'] = 'true'
        try:
            return func(*args, **kwargs)
        finally:
            # Clean up test mode if desired
            pass
    return wrapper

def label_safe_live_test():
    """
    Returns a string label for manual safe live tests.
    """
    return "[SAFE LIVE TEST]"

def label_mocked_test():
    """
    Returns a string label for mocked tests.
    """
    return "[MOCKED TEST]"