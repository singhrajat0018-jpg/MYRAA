"""
Tests for the permission system (EPIC-10B).
"""

from __future__ import annotations

import os
import pytest
from unittest import mock

from desktop_agent.config.permissions import (
    DEFAULT_POLICIES,
    TOOL_CATEGORIES,
    TOOL_OVERRIDES,
    READ,
    INTERACT,
    MODIFY,
    HIGH_RISK,
)
from desktop_agent.registry import PermissionManager, PermissionDecision, TOOLS, TOOL_SCHEMAS, STATE
from desktop_agent.main import CommandDispatcher, ExecuteResponse
from desktop_agent.registry import ValidationLayer, ToolError


# Helper to create a mock ExecuteRequest
class MockExecuteRequest:
    def __init__(self, tool: str, args: dict | None = None):
        self.tool = tool
        self.args = args or {}


def test_permission_manager_read_tool_allowed():
    """READ tool should be allowed by default."""
    # Pick a known READ tool from the registry
    read_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == READ:
            read_tool = tool
            break
    assert read_tool is not None, "No READ tool found in TOOL_CATEGORIES"

    decision = PermissionManager.check(read_tool, {})
    assert isinstance(decision, PermissionDecision)
    assert decision.allowed is True
    assert decision.decision == "allow"
    assert decision.tool == read_tool
    assert decision.category == READ


def test_permission_manager_interact_tool_allowed():
    """INTERACT tool should be allowed by default."""
    interact_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == INTERACT:
            interact_tool = tool
            break
    assert interact_tool is not None, "No INTERACT tool found in TOOL_CATEGORIES"

    decision = PermissionManager.check(interact_tool, {})
    assert decision.allowed is True
    assert decision.decision == "allow"
    assert decision.category == INTERACT


def test_permission_manager_modify_tool_requires_confirmation():
    """MODIFY tool should require confirmation by default."""
    modify_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == MODIFY:
            modify_tool = tool
            break
    assert modify_tool is not None, "No MODIFY tool found in TOOL_CATEGORIES"

    decision = PermissionManager.check(modify_tool, {})
    assert decision.allowed is False
    assert decision.decision == "confirm"
    assert decision.tool == modify_tool
    assert decision.category == MODIFY


def test_permission_manager_high_risk_tool_requires_confirmation():
    """HIGH_RISK tool should require confirmation by default."""
    high_risk_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == HIGH_RISK:
            high_risk_tool = tool
            break
    # If none found, we can skip or use a known one like executePowerAction?
    # Actually executePowerAction is categorized as SYSTEM_CRITICAL in our mapping,
    # but the override keeps its policy "allow" so the internal two-step
    # confirmation token flow remains the single gate.
    # So we need to ensure there is at least one HIGH_RISK tool. Let's check if any tool is mapped to HIGH_RISK.
    # If not, we'll create a temporary mapping for testing? Better to check the actual mapping.
    # We'll just assert that there is at least one HIGH_RISK tool; if not, the test will fail and we'll know to adjust the mapping.
    assert high_risk_tool is not None, "No HIGH_RISK tool found in TOOL_CATEGORIES. Please ensure mapping includes at least one HIGH_RISK tool."

    decision = PermissionManager.check(high_risk_tool, {})
    assert decision.allowed is False
    assert decision.decision == "confirm"
    assert decision.tool == high_risk_tool
    assert decision.category == HIGH_RISK


def test_permission_manager_tool_override_deny():
    """Tool-specific override to deny should work."""
    # Choose a tool that is currently allowed (e.g., a READ tool) and override it to deny.
    read_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == READ:
            read_tool = tool
            break
    assert read_tool is not None

    # Temporarily add an override
    original_override = TOOL_OVERRIDES.get(read_tool)
    TOOL_OVERRIDES[read_tool] = "deny"
    try:
        decision = PermissionManager.check(read_tool, {})
        assert decision.allowed is False
        assert decision.decision == "deny"
        assert decision.tool == read_tool
    finally:
        # Restore
        if original_override is None:
            del TOOL_OVERRIDES[read_tool]
        else:
            TOOL_OVERRIDES[read_tool] = original_override


def test_permission_manager_tool_override_allow():
    """Tool-specific override to allow should work."""
    # Choose a tool that is currently requiring confirmation (e.g., a MODIFY tool) and override to allow.
    modify_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == MODIFY:
            modify_tool = tool
            break
    assert modify_tool is not None

    original_override = TOOL_OVERRIDES.get(modify_tool)
    TOOL_OVERRIDES[modify_tool] = "allow"
    try:
        decision = PermissionManager.check(modify_tool, {})
        assert decision.allowed is True
        assert decision.decision == "allow"
        assert decision.tool == modify_tool
    finally:
        if original_override is None:
            del TOOL_OVERRIDES[modify_tool]
        else:
            TOOL_OVERRIDES[modify_tool] = original_override


def test_permission_manager_unknown_tool_defaults_to_high_risk():
    """Unknown tool should be treated as HIGH_RISK for safety (fail closed)."""
    # We cannot truly test an unknown tool because CommandDispatcher filters it out before calling PermissionManager.
    # But we can call PermissionManager directly with a tool not in TOOL_CATEGORIES.
    unknown_tool = "__unknown_tool_for_test__"
    # Ensure it's not in the categories
    assert unknown_tool not in TOOL_CATEGORIES

    decision = PermissionManager.check(unknown_tool, {})
    # Should be treated as HIGH_RISK (default policy confirm)
    assert decision.category == HIGH_RISK
    assert decision.decision == "confirm"  # default for HIGH_RISK is confirm
    assert decision.allowed is False


def test_command_dispatcher_allows_read_tool():
    """CommandDispatcher should allow a READ tool and execute its handler."""
    # We'll need to mock a handler for a READ tool.
    # Pick a REAL READ tool that we can safely mock, but we don't want to actually execute it.
    # Instead, we can temporarily replace the handler in TOOLS with a mock.
    read_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == READ:
            read_tool = tool
            break
    assert read_tool is not None

    # Backup original handler and schema
    original_handler = TOOLS.get(read_tool)
    original_schema = TOOL_SCHEMAS.get(read_tool)

    # Define a mock handler that returns a known result
    def mock_handler(args):
        return {"result": f"mock result for {read_tool}"}

    # No schema needed for simplicity
    mock_schema = None

    try:
        TOOLS[read_tool] = mock_handler
        TOOL_SCHEMAS[read_tool] = mock_schema

        req = MockExecuteRequest(read_tool, {})
        resp: ExecuteResponse = CommandDispatcher.dispatch(req)

        assert resp.ok is True
        assert resp.tool == read_tool
        assert resp.result == {"result": f"mock result for {read_tool}"}
        assert resp.error is None
    finally:
        # Restore
        if original_handler is None:
            del TOOLS[read_tool]
        else:
            TOOLS[read_tool] = original_handler
        if original_schema is None:
            del TOOL_SCHEMAS[read_tool]
        else:
            TOOL_SCHEMAS[read_tool] = original_schema


def test_command_dispatcher_denies_tool():
    """CommandDispatcher should deny a tool when policy is deny."""
    # Choose a tool and override its policy to deny.
    tool_to_test = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == READ:  # pick a READ tool so we know it's normally allowed
            tool_to_test = tool
            break
    assert tool_to_test is not None

    original_override = TOOL_OVERRIDES.get(tool_to_test)
    TOOL_OVERRIDES[tool_to_test] = "deny"

    # Backup handler and schema
    original_handler = TOOLS.get(tool_to_test)
    original_schema = TOOL_SCHEMAS.get(tool_to_test)

    # Mock handler (should not be called)
    def mock_handler(args):
        return {"result": "should not be called"}

    try:
        TOOLS[tool_to_test] = mock_handler
        TOOL_SCHEMAS[tool_to_test] = None

        req = MockExecuteRequest(tool_to_test, {})
        resp: ExecuteResponse = CommandDispatcher.dispatch(req)

        assert resp.ok is False
        assert resp.tool == tool_to_test
        assert resp.error is not None
        assert "Permission denied" in resp.error
        # Ensure handler was not called: we can't directly assert, but we can trust that if it returned an error, it didn't execute.
    finally:
        # Restore
        if original_override is None:
            del TOOL_OVERRIDES[tool_to_test]
        else:
            TOOL_OVERRIDES[tool_to_test] = original_override
        if original_handler is None:
            del TOOLS[tool_to_test]
        else:
            TOOLS[tool_to_test] = original_handler
        if original_schema is None:
            del TOOL_SCHEMAS[tool_to_test]
        else:
            TOOL_SCHEMAS[tool_to_test] = original_schema


def test_command_dispatcher_requires_confirmation():
    """CommandDispatcher should return confirmation-required result for a tool with policy confirm."""
    # Choose a tool that is MODIFY (default confirm)
    modify_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == MODIFY:
            modify_tool = tool
            break
    assert modify_tool is not None

    # Backup handler and schema
    original_handler = TOOLS.get(modify_tool)
    original_schema = TOOL_SCHEMAS.get(modify_tool)

    # Mock handler (should not be called)
    def mock_handler(args):
        return {"result": "should not be called"}

    try:
        TOOLS[modify_tool] = mock_handler
        TOOL_SCHEMAS[modify_tool] = None

        req = MockExecuteRequest(modify_tool, {"path": "C:/Users/singh/Desktop/confirmation_test.txt"})
        resp: ExecuteResponse = CommandDispatcher.dispatch(req)

        assert resp.ok is True  # confirmation-required is still a successful response from the dispatcher's perspective
        assert resp.tool == modify_tool
        assert resp.error is None
        assert isinstance(resp.result, dict)
        assert resp.result.get("requires_confirmation") is True
        assert "reason" in resp.result
        assert resp.result["tool"] == modify_tool
        # Ensure handler was not called
    finally:
        # Restore
        if original_handler is None:
            del TOOLS[modify_tool]
        else:
            TOOLS[modify_tool] = original_handler
        if original_schema is None:
            del TOOL_SCHEMAS[modify_tool]
        else:
            TOOL_SCHEMAS[modify_tool] = original_schema


def test_command_dispatcher_unknown_tool_denied():
    """CommandDispatcher should deny unknown tool (before permission check)."""
    unknown_tool = "__unknown_tool_test__"
    req = MockExecuteRequest(unknown_tool, {})
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)

    assert resp.ok is False
    assert resp.tool == unknown_tool
    assert resp.error is not None
    assert "Unknown tool" in resp.error


def test_command_dispatcher_handler_not_called_on_deny_or_confirm():
    """We already tested that handler is not called in the deny and confirm cases via the mock handler returning unexpected results.
    To be more explicit, we can use a mock that raises an exception if called."""
    # Test for deny
    tool_to_test = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == READ:
            tool_to_test = tool
            break
    assert tool_to_test is not None

    original_override = TOOL_OVERRIDES.get(tool_to_test)
    TOOL_OVERRIDES[tool_to_test] = "deny"

    original_handler = TOOLS.get(tool_to_test)
    original_schema = TOOL_SCHEMAS.get(tool_to_test)

    def failing_handler(args):
        raise RuntimeError("Handler should not be called")

    try:
        TOOLS[tool_to_test] = failing_handler
        TOOL_SCHEMAS[tool_to_test] = None

        req = MockExecuteRequest(tool_to_test, {})
        resp = CommandDispatcher.dispatch(req)

        assert resp.ok is False
        assert "Permission denied" in resp.error
        # If the handler had been called, we would have gotten a ToolError or similar, but we got a permission error.
    finally:
        if original_override is None:
            del TOOL_OVERRIDES[tool_to_test]
        else:
            TOOL_OVERRIDES[tool_to_test] = original_override
        if original_handler is None:
            del TOOLS[tool_to_test]
        else:
            TOOLS[tool_to_test] = original_handler
        if original_schema is None:
            del TOOL_SCHEMAS[tool_to_test]
        else:
            TOOL_SCHEMAS[tool_to_test] = original_schema

    # Test for confirm
    modify_tool = None
    for tool, cat in TOOL_CATEGORIES.items():
        if cat == MODIFY:
            modify_tool = tool
            break
    assert modify_tool is not None

    original_override_mod = TOOL_OVERRIDES.get(modify_tool)
    TOOL_OVERRIDES[modify_tool] = "confirm"  # already default, but be explicit

    original_handler_mod = TOOLS.get(modify_tool)
    original_schema_mod = TOOL_SCHEMAS.get(modify_tool)

    def failing_handler_mod(args):
        raise RuntimeError("Handler should not be called")

    try:
        TOOLS[modify_tool] = failing_handler_mod
        TOOL_SCHEMAS[modify_tool] = None

        req = MockExecuteRequest(modify_tool, {"path": "C:/Users/singh/Desktop/confirmation_test.txt"})
        resp = CommandDispatcher.dispatch(req)

        assert resp.ok is True
        assert resp.result.get("requires_confirmation") is True
        # Handler not called
    finally:
        if original_override_mod is None:
            del TOOL_OVERRIDES[modify_tool]
        else:
            TOOL_OVERRIDES[modify_tool] = original_override_mod
        if original_handler_mod is None:
            del TOOLS[modify_tool]
        else:
            TOOLS[modify_tool] = original_handler_mod
        if original_schema_mod is None:
            del TOOL_SCHEMAS[modify_tool]
        else:
            TOOL_SCHEMAS[modify_tool] = original_schema_mod


def test_permission_manager_exception_fails_safely():
    """If PermissionManager.check raises an exception, it should be treated as a denial."""
    # We'll monkey-patch PermissionManager.check to raise an exception.
    original_check = PermissionManager.check

    def raising_check(tool_name, args):
        raise ValueError("Intentional error in permission check")

    try:
        PermissionManager.check = raising_check  # type: ignore

        # Pick any tool that exists in TOOLS
        tool = None
        for t in TOOLS.keys():
            tool = t
            break
        assert tool is not None

        # Backup handler
        original_handler = TOOLS.get(tool)
        original_schema = TOOL_SCHEMAS.get(tool)

        def mock_handler(args):
            return {"result": "should not be called"}

        try:
            TOOLS[tool] = mock_handler
            TOOL_SCHEMAS[tool] = None

            req = MockExecuteRequest(tool, {})
            resp = CommandDispatcher.dispatch(req)

            # The exception should be caught and turned into an error response
            assert resp.ok is False
            assert resp.tool == tool
            assert resp.error is not None
            # The error message may contain the original exception
        finally:
            TOOLS[tool] = original_handler
            if original_schema is None:
                del TOOL_SCHEMAS[tool]
            else:
                TOOL_SCHEMAS[tool] = original_schema
    finally:
        PermissionManager.check = original_check


def test_power_action_confirmation_still_works():
    """Ensure that the existing power-action confirmation mechanism still works."""
    # We need to test that requestPowerAction and executePowerAction still function as before.
    # Since they rely on the internal confirmation token system, we can test that our permission
    # system does not interfere.
    # We'll test that requestPowerAction is allowed (our policy for it is allow) and that
    # executePowerAction is allowed (also allow) but note that executePowerAction has its own
    # internal token validation.

    # First, test requestPowerAction
    req = MockExecuteRequest("requestPowerAction", {"action": "shutdown"})
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)
    assert resp.ok is True
    assert resp.tool == "requestPowerAction"
    # The result should contain requires_confirmation from the tool itself, not from our permission system.
    # Our permission system should have allowed it, so the tool's normal result is returned.
    assert isinstance(resp.result, dict)
    # The tool's result should have a key "requires_confirmation": True (from tools_confirmation.py)
    assert resp.result.get("requires_confirmation") is True
    assert "token" in resp.result
    assert resp.result.get("action") == "shutdown"

    # Now test executePowerAction with a valid token (we need to get a token from requestPowerAction first)
    # Since we already have a token from the previous response, we can reuse it.
    token = resp.result.get("token")
    assert token is not None
    # SAFETY: subprocess.run/os.system are mocked so the real OS power command is
    # never executed. We only assert that the command WOULD have been requested.
    with mock.patch("desktop_agent.tools_pc.subprocess.run") as mock_run, \
         mock.patch("desktop_agent.tools_pc.os.system") as mock_os_system, \
         mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false", "MYRAA_ALLOW_POWER_ACTIONS": "1"}, clear=False):
        req2 = MockExecuteRequest("executePowerAction", {"action": "shutdown", "execute_token": token})
        resp2: ExecuteResponse = CommandDispatcher.dispatch(req2)
        assert resp2.ok is True
        assert resp2.tool == "executePowerAction"
        # The action should have been requested (not executed) and returned a result.
        assert resp2.error is None
        assert resp2.result.get("action") == "shutdown"
        mock_run.assert_called_once_with(["shutdown", "/s", "/t", "10"], check=False)
        mock_os_system.assert_not_called()

    # Also test that executePowerAction without token fails (as per the tool's internal logic)
    req3 = MockExecuteRequest("executePowerAction", {"action": "shutdown"})
    resp3: ExecuteResponse = CommandDispatcher.dispatch(req3)
    assert resp3.ok is False
    assert resp3.error is not None
    assert "confirmation token" in resp3.error.lower() or "token" in resp3.error.lower()


def test_permission_manager_audit_logging_called():
    """Verify that audit logging is invoked (we can't easily assert the log output, but we can ensure logging doesn't break)."""
    # We'll just call PermissionManager.check and ensure no exception is raised.
    tool = None
    for t in TOOLS.keys():
        tool = t
        break
    assert tool is not None

    # This should not raise
    decision = PermissionManager.check(tool, {})
    assert isinstance(decision, PermissionDecision)
    # If logging caused an exception, we would have seen it.


# ---------------------------------------------------------------------------
# F3 scenario coverage: argument-aware gates, risk classes, token lifecycle.
# ---------------------------------------------------------------------------

def test_financial_action_always_denied():
    """FINANCIAL tools must be hard-denied — no order/execution path exists."""
    from desktop_agent.config.permissions import FINANCIAL, DEFAULT_POLICIES
    assert DEFAULT_POLICIES[FINANCIAL] == "deny"
    # No FINANCIAL tool may be registered that bypasses the deny policy.
    financial_tools = [t for t, c in TOOL_CATEGORIES.items() if c == FINANCIAL]
    for tool in financial_tools:
        decision = PermissionManager.check(tool, {})
        assert decision.allowed is False
        assert decision.decision == "deny"
    # Unknown/hypothetical trading tools fail closed (never allowed).
    decision = PermissionManager.check("marketOrder", {})
    assert decision.allowed is False


def test_path_traversal_denied():
    """'..' traversal in file arguments must be hard-denied."""
    decision = PermissionManager.check("readFile", {"path": "../../../windows/system32/config/sam"})
    assert decision.allowed is False
    assert decision.decision == "deny"
    assert "traversal" in decision.reason.lower()


def test_protected_path_denied():
    """Files inside C:\\Windows must be denied through file tools."""
    decision = PermissionManager.check("deleteFile", {"path": "C:\\Windows\\System32\\evil.exe"})
    assert decision.allowed is False
    assert decision.decision == "deny"


def test_sensitive_filename_denied():
    """.env / secrets.json must never be read through generic file tools."""
    for name in (".env", "secrets.json", "id_rsa"):
        decision = PermissionManager.check("readFile", {"path": f"C:\\Users\\singh\\{name}"})
        assert decision.allowed is False, f"{name} should be blocked"
        assert decision.decision == "deny"


def test_run_python_script_is_system_critical():
    """Arbitrary code execution requires confirmation (SYSTEM_CRITICAL)."""
    from desktop_agent.config.permissions import SYSTEM_CRITICAL
    decision = PermissionManager.check("runPythonScript", {"path": "C:/Users/singh/script.py"})
    assert decision.allowed is False
    assert decision.decision == "confirm"
    assert decision.category == SYSTEM_CRITICAL


def test_confirmation_token_is_single_use():
    """A consumed token must not authorize a second execution."""
    from desktop_agent.registry import STATE
    tool = "deleteFile"
    args = {"path": "C:/Users/singh/Desktop/tmp_token_test.txt"}
    token = PermissionManager.mint_confirmation(tool, args)
    assert PermissionManager.validate_confirmation(tool, args, token) is True
    # Replay must fail (token was consumed on first use).
    assert PermissionManager.validate_confirmation(tool, args, token) is False


def test_confirmation_token_rejected_for_different_args():
    """A token minted for one arg set must not authorize a different arg set."""
    tool = "deleteFile"
    token = PermissionManager.mint_confirmation(tool, {"path": "C:/Users/singh/a.txt"})
    assert PermissionManager.validate_confirmation(tool, {"path": "C:/Users/singh/b.txt"}, token) is False


def test_confirmation_token_rejected_for_different_tool():
    """A token minted for one tool must not authorize a different tool."""
    token = PermissionManager.mint_confirmation("deleteFile", {"path": "C:/Users/singh/a.txt"})
    assert PermissionManager.validate_confirmation("moveFile", {"path": "C:/Users/singh/a.txt"}, token) is False


def test_confirmation_token_expired_is_rejected(monkeypatch):
    """An expired token must be rejected and purged."""
    from desktop_agent.registry import STATE
    import time
    token = PermissionManager.mint_confirmation("deleteFile", {"path": "C:/Users/singh/a.txt"})
    STATE.confirmations[token]["expires"] = time.time() - 5.0
    assert PermissionManager.validate_confirmation("deleteFile", {"path": "C:/Users/singh/a.txt"}, token) is False
    assert token not in STATE.confirmations


def test_missing_confirmation_token_refused():
    """A confirm-required tool without a token returns requires_confirmation."""
    from desktop_agent.config.permissions import MODIFY
    tool = None
    for t, c in TOOL_CATEGORIES.items():
        if c == MODIFY:
            tool = t
            break
    assert tool is not None
    req = MockExecuteRequest(tool, {"path": "C:/Users/singh/Desktop/x.txt"})
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)
    assert resp.ok is True
    assert resp.result.get("requires_confirmation") is True
    assert resp.result.get("token")


def test_destructive_delete_requires_confirmation_flow():
    """deleteFile (DESTRUCTIVE) must mint a token, then refuse reuse."""
    from desktop_agent.registry import STATE
    req = MockExecuteRequest("deleteFile", {"path": "C:/Users/singh/Desktop/nonexistent_f3.txt"})
    resp: ExecuteResponse = CommandDispatcher.dispatch(req)
    assert resp.ok is True
    token = resp.result.get("token")
    assert token is not None
    # Executing with the token would attempt a real delete of a nonexistent file;
    # the tool raises ToolError (file missing) → ok=False. That proves the token
    # unlocked execution (not the permission gate) without touching real files.
    req2 = MockExecuteRequest("deleteFile", {"path": "C:/Users/singh/Desktop/nonexistent_f3.txt", "confirmation_token": token})
    resp2: ExecuteResponse = CommandDispatcher.dispatch(req2)
    assert resp2.ok is False
    assert "does not exist" in (resp2.error or "").lower()


if __name__ == "__main__":
    # Allow running the test file directly for quick verification
    pytest.main([__file__, "-v"])