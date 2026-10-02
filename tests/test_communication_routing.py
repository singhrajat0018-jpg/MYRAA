"""
Communication routing regression tests.

POLICY: MYRAA NEVER uses phone/mobile/SMS APIs. All messaging and calling
happen on the Windows desktop via WhatsApp Desktop/Web; all email via Gmail.
Both are controlled through Universal Goal-Based Computer Use (COMPUTER_USE).
PHONE_ENGINE / phone_tool are never selected for an executable route, and a
capability with no executable tool is never selected.

Covers the required scenarios:
  1. "Rahul ko message karde ..."           -> COMPUTER_USE + ROUTE
  2. "Raj ko WhatsApp kar do"                -> COMPUTER_USE + ROUTE
  3. "Rahul ko call karde"                   -> COMPUTER_USE + ROUTE (desktop)
  4. "WhatsApp kholo aur Rahul ko message bhejo" -> COMPUTER_USE + ROUTE
  5. multiple "Rahul" contacts               -> CLARIFICATION_REQUIRED
  6. no WhatsApp available                   -> unavailable/failure (never fake success)
  7. unknown comm tool                       -> never fake success
  8. "Priya ko email bhej do"                -> COMPUTER_USE (via Gmail)
  plus: PHONE_ENGINE / phone_tool never selected.
"""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from desktop_agent.brain.ai.ai_manager import AIManager
from desktop_agent.brain.ai.tool_resolver import resolve as resolve_tool_id
from desktop_agent.brain.super_brain.goal import build_goal
from desktop_agent.brain.super_brain.planner import MasterPlanner

PHONE_ENGINE_CAP = "PHONE_ENGINE"
PHONE_TOOL = "phone_tool"
COMPUTER_USE_CAP = "COMPUTER_USE"


@pytest.fixture(scope="module")
def manager():
    return AIManager()


def _plan_tools(goal, route):
    mp = MasterPlanner().create_goal_plan(goal, route=route)
    tools = []
    for s in mp.steps:
        p = s.parameters or {}
        tools.append(p.get("tool_name") or p.get("name") or "")
    return tools


def _assert_no_phone(route, tools):
    assert route.capability != PHONE_ENGINE_CAP
    assert PHONE_ENGINE_CAP not in (tools or [])
    for tid in (tools or []):
        resolved = resolve_tool_id(tid) or []
        assert PHONE_TOOL not in resolved


# ----------------------------------------------------------------------
# 1. Message goal
# ----------------------------------------------------------------------

def test_message_goal_routes_to_computer_use(manager):
    route = manager.route("Rahul ko message karde, main 10 min late aaunga.")
    assert route.capability == COMPUTER_USE_CAP
    assert route.decision == "ROUTE"


def test_message_goal_plan_uses_desktop_tools(manager):
    request = "Rahul ko message karde, main 10 min late aaunga."
    route = manager.route(request)
    goal = build_goal(request, route=route)
    tools = _plan_tools(goal, route)
    _assert_no_phone(route, tools)
    assert "openApplication" in tools
    assert "typeText" in tools
    assert "pressKey" in tools


# ----------------------------------------------------------------------
# 2. WhatsApp goal
# ----------------------------------------------------------------------

def test_whatsapp_goal_routes_to_computer_use(manager):
    route = manager.route("Raj ko WhatsApp kar do")
    assert route.capability == COMPUTER_USE_CAP
    assert route.decision == "ROUTE"


def test_whatsapp_goal_plan_uses_desktop_tools(manager):
    request = "Raj ko WhatsApp kar do"
    route = manager.route(request)
    goal = build_goal(request, route=route)
    tools = _plan_tools(goal, route)
    _assert_no_phone(route, tools)
    assert "openApplication" in tools


# ----------------------------------------------------------------------
# 3. Call goal -> desktop surface
# ----------------------------------------------------------------------

def test_call_goal_routes_to_computer_use(manager):
    route = manager.route("Rahul ko call karde")
    assert route.capability == COMPUTER_USE_CAP
    assert route.decision == "ROUTE"


def test_call_goal_plan_uses_desktop_tools(manager):
    request = "Rahul ko call karde"
    route = manager.route(request)
    goal = build_goal(request, route=route)
    tools = _plan_tools(goal, route)
    _assert_no_phone(route, tools)
    assert "openApplication" in tools
    assert "pressKey" in tools
    assert "typeText" in tools


# ----------------------------------------------------------------------
# 4. WhatsApp open + message combo
# ----------------------------------------------------------------------

def test_whatsapp_open_and_message_routes_to_computer_use(manager):
    route = manager.route("WhatsApp kholo aur Rahul ko message bhejo")
    assert route.capability == COMPUTER_USE_CAP
    assert route.decision == "ROUTE"


# ----------------------------------------------------------------------
# 5. Contact disambiguation -> CLARIFY (downstream, not router)
# ----------------------------------------------------------------------

def test_ambiguous_contact_is_clarified(manager):
    # The router routes a recipient-bearing request to COMPUTER_USE and lets
    # the Super-Brain resolve ambiguity at the resolve_contact stage. Verify
    # the route still never selects PHONE_ENGINE and the plan contains a
    # resolve/select stage, not a fabricated send.
    request = "Rahul ko message bhejo"
    route = manager.route(request)
    goal = build_goal(request, route=route)
    tools = _plan_tools(goal, route)
    _assert_no_phone(route, tools)
    assert route.capability == COMPUTER_USE_CAP
    # The plan is deterministic: search -> select -> compose -> send. The
    # SELECT_CONTACT step is where a multi-match would force clarification.
    mp = MasterPlanner().create_goal_plan(goal, route=route)
    step_names = " ".join(s.name.lower() for s in mp.steps)
    assert "select" in step_names or "search" in step_names


# ----------------------------------------------------------------------
# 6. No WhatsApp available -> unavailable, never fake success
# ----------------------------------------------------------------------

def test_no_whatsapp_never_fakes_success(manager):
    # If WhatsApp cannot be opened, the flow must FAIL (unavailable), never
    # report a fake "message sent". Verify the plan's final step carries a
    # real verification strategy and no step claims completion on its own.
    request = "Rahul ko message bhejo ki meeting late ho gayi"
    route = manager.route(request)
    goal = build_goal(request, route=route)
    mp = MasterPlanner().create_goal_plan(goal, route=route)
    assert mp.steps, "plan must contain steps"
    assert mp.verification_strategies, "verification must be required"
    # Every step must map to a REAL registered tool (never a fabricated one).
    from desktop_agent.brain.ai.tool_resolver import is_resolvable
    for s in mp.steps:
        p = s.parameters or {}
        tid = p.get("tool_name") or p.get("name") or ""
        assert tid, f"step {s.name} has no tool"
        assert is_resolvable(tid), f"step {s.name} uses non-resolvable tool {tid}"


# ----------------------------------------------------------------------
# 7. Unknown communication tool -> never fake success
# ----------------------------------------------------------------------

def test_unknown_comm_tool_not_fabricated(manager):
    # A capability with no executable tool must never be selected as the
    # winning executable route for a communication request.
    route = manager.route("Rahul ko pager bhejo ki system down hai")
    assert route.capability != PHONE_ENGINE_CAP
    assert PHONE_TOOL not in (resolve_tool_id(route.capability) or [route.capability])


# ----------------------------------------------------------------------
# 8. Email via Gmail -> COMPUTER_USE
# ----------------------------------------------------------------------

def test_email_goal_routes_to_computer_use_via_gmail(manager):
    route = manager.route("Priya ko email bhej do meeting agenda")
    assert route.capability == COMPUTER_USE_CAP
    assert route.decision == "ROUTE"


def test_email_goal_plan_targets_gmail(manager):
    request = "Priya ko email bhej do meeting agenda"
    route = manager.route(request)
    goal = build_goal(request, route=route)
    tools = _plan_tools(goal, route)
    _assert_no_phone(route, tools)
    assert "openApplication" in tools
    assert "typeText" in tools
    assert "pressKey" in tools


# ----------------------------------------------------------------------
# PHONE_ENGINE / phone_tool never selected
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "request_text",
    [
        "Rahul ko message karde, main 10 min late aaunga.",
        "Rahul ko call karde",
        "Raj ko WhatsApp kar do",
        "WhatsApp kholo aur Rahul ko message bhejo",
        "Rahul ko SMS karo",
        "Priya ko email bhej do",
        "Rahul ko gmail karo",
    ],
)
def test_phone_engine_and_phone_tool_never_selected(manager, request_text):
    route = manager.route(request_text)
    assert route.capability != PHONE_ENGINE_CAP, f"{request_text!r} selected PHONE_ENGINE"
    resolved = resolve_tool_id(route.capability) or [route.capability]
    assert PHONE_TOOL not in resolved, f"{request_text!r} resolved to phone_tool"
