"""Browser default-architecture + UniversalController integration tests.

MYRAA owns NO browser: the Windows OS default browser is opened via
tools_websites.open_url, and in-page interaction goes through the ONE
vision-based engine (UniversalController, shared via registry.STATE and
executing through the registry dispatcher -> PermissionManager).

These tests verify BEHAVIOR:
  - click/type/scroll actually perform (or honestly refuse) via the UC path
  - no-UC / no-target / refused-focus paths return structured ok:False
  - close-tab is gated by a real browser-focus check
  - the unsupported actions stay honestly unsupported (ok:False, never faked)
  - no browser engine exists; module imports fine without playwright
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import desktop_agent.tools_browser as tb
import desktop_agent.registry as registry
from desktop_agent.registry import TOOLS, State, ToolError
from desktop_agent.universal_control.ui_element import InteractiveRole


def _elem(label="Search", role=InteractiveRole.PRIMARY_ACTION, x=500, y=300):
    return SimpleNamespace(label=label, role=role, center_x=x, center_y=y)


class FakeDiscovery:
    def __init__(self, elements):
        self.elements = elements


class FakeUC:
    """Minimal UniversalController surface used by the browser tools."""

    def __init__(self, elements=None):
        self._elements = elements or []

    def find_element(self, hint):
        for e in self._elements:
            if hint.lower() in (e.label or "").lower():
                return e
        return None

    def discover_elements(self):
        return FakeDiscovery(list(self._elements))


class Recorder:
    """Replaces tools_browser._dispatch_tool: records, answers per tool."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def __call__(self, tool, args):
        self.calls.append((tool, args))
        if tool in self.responses:
            r = self.responses[tool]
            if isinstance(r, Exception):
                raise r
            return r
        return {"ok": True, "result": f"{tool} ok"}


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """No container in unit tests: UC slot empty unless a test installs one."""
    monkeypatch.setattr(registry.STATE, "universal_controller", None, raising=False)
    yield
    monkeypatch.setattr(registry.STATE, "universal_controller", None, raising=False)


# ---------------------------------------------------------------------------
# No UniversalController available â€” honest structured refusal
# ---------------------------------------------------------------------------


def test_click_without_uc_refuses_honestly():
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_click({"target": "search box"})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is False
    assert out["limitation"] == "universal_control_unavailable"
    assert rec.calls == []  # never dispatched a real click


def test_type_without_uc_refuses_honestly():
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_type({"text": "hello"})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is False
    assert out["limitation"] == "universal_control_unavailable"


def test_type_empty_text_rejected():
    with pytest.raises(ToolError):
        tb.browser_type({"text": ""})


# ---------------------------------------------------------------------------
# Click via UC (vision discovery -> leftClick through the dispatcher)
# ---------------------------------------------------------------------------


def test_click_with_uc_clicks_found_target():
    registry.STATE.universal_controller = FakeUC(
        elements=[_elem("Search", InteractiveRole.INPUT, x=512, y=311)]
    )
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_click({"target": "search"})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is True
    assert rec.calls == [("leftClick", {"x": 512, "y": 311})]
    assert out["clicked"]["target"] == "Search"


def test_click_with_uc_no_target_is_honest():
    registry.STATE.universal_controller = FakeUC(elements=[])
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_click({"target": "nonexistent_xyz"})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is False
    assert out["limitation"] == "target_not_found"
    assert rec.calls == []  # no blind click was performed


def test_click_with_explicit_coordinates_skips_uc():
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_click({"x": 100, "y": 200})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is True
    assert rec.calls == [("leftClick", {"x": 100, "y": 200})]


# ---------------------------------------------------------------------------
# Type via UC (focus click + typeText, verbatim)
# ---------------------------------------------------------------------------


def test_type_with_uc_clicks_field_then_types_verbatim():
    registry.STATE.universal_controller = FakeUC(
        elements=[_elem("Search", InteractiveRole.INPUT, x=480, y=120)]
    )
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_type({"text": "hello world", "target": "search"})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is True
    assert rec.calls == [
        ("leftClick", {"x": 480, "y": 120}),
        ("typeText", {"text": "hello world"}),  # verbatim, unmodified
    ]


def test_type_target_not_found_never_types():
    registry.STATE.universal_controller = FakeUC(
        elements=[_elem("OK", InteractiveRole.PRIMARY_ACTION)]
    )
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_type({"text": "secret", "target": "email"})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is False
    assert out["limitation"] == "target_not_found"
    assert rec.calls == []  # no field focused -> nothing typed


def test_type_falls_back_to_first_visible_input():
    registry.STATE.universal_controller = FakeUC(elements=[
        _elem("Submit", InteractiveRole.PRIMARY_ACTION, x=1, y=1),
        _elem("Email", InteractiveRole.INPUT, x=42, y=84),
    ])
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_type({"text": "a@b.c"})  # no target hint
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is True
    assert rec.calls[0] == ("leftClick", {"x": 42, "y": 84})
    assert rec.calls[1][0] == "typeText"


# ---------------------------------------------------------------------------
# Scroll (cursor-anchored wheel via existing mouse tool)
# ---------------------------------------------------------------------------


def test_scroll_down_dispatches_positive_clicks():
    rec = Recorder(responses={"mousePosition": {"ok": True, "x": 1, "y": 1}})
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_scroll({"direction": "down"})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is True
    assert rec.calls[-1] == ("scrollMouse", {"clicks": 3})


def test_scroll_up_dispatches_negative_clicks():
    rec = Recorder(responses={"mousePosition": {"ok": True, "x": 1, "y": 1}})
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_scroll({"direction": "up", "clicks": 5})
    finally:
        tb._dispatch_tool = original
    assert rec.calls[-1] == ("scrollMouse", {"clicks": -5})


def test_scroll_clicks_bounded():
    rec = Recorder(responses={"mousePosition": {"ok": True}})
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        tb.browser_scroll({"clicks": 999})
    finally:
        tb._dispatch_tool = original
    assert rec.calls[-1][1]["clicks"] == 10


def test_scroll_when_dispatch_raises_refuses_honestly(monkeypatch):
    # Patch the registry dispatcher itself; the REAL _dispatch_tool must catch
    # the failure and turn it into a structured ok:False (never leak, never fake).
    def boom(tool, args):
        raise ToolError("Unknown tool")

    monkeypatch.setattr(registry, "dispatch", boom)
    # Without a UC the vision-anchor fallback honestly reports unavailability.
    out = tb.browser_scroll({})
    assert out["ok"] is False
    assert out["limitation"] == "universal_control_unavailable"

    # With a UC but no visual state, the vision fallback refuses too.
    registry.STATE.universal_controller = FakeUC(elements=[])
    out2 = tb.browser_scroll({})
    assert out2["ok"] is False
    assert out2["limitation"] == "vision_unavailable"


# ---------------------------------------------------------------------------
# Close-tab: focus-verified Ctrl+W, refuses on non-browser focus
# ---------------------------------------------------------------------------


def test_close_tab_refuses_when_not_browser_focused(monkeypatch):
    monkeypatch.setattr(
        tb, "_browser_focus_status",
        lambda: {"is_browser": False, "window_title": "Notepad", "permission": True},
    )
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_close_tab({})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is False
    assert out["limitation"] == "browser_not_focused"
    assert rec.calls == []  # Ctrl+W must NOT be sent at unverified focus


def test_close_tab_sends_ctrlw_when_browser_focused(monkeypatch):
    monkeypatch.setattr(
        tb, "_browser_focus_status",
        lambda: {"is_browser": True, "window_title": "Example â€” Google Chrome", "permission": True},
    )
    rec = Recorder()
    original = tb._dispatch_tool
    tb._dispatch_tool = rec
    try:
        out = tb.browser_close_tab({})
    finally:
        tb._dispatch_tool = original
    assert out["ok"] is True
    assert rec.calls == [("pressKey", {"key": "ctrl+w"})]
    assert out["verification"]["browser_focused"] is True


# ---------------------------------------------------------------------------
# Honest unsupported actions + registry + architecture invariants
# ---------------------------------------------------------------------------


def test_unsupported_actions_stay_honestly_unsupported():
    assert tb.browser_fill_form_stub({})["ok"] is False
    assert tb.browser_go_back_stub({})["ok"] is False
    assert tb.browser_go_forward_stub({})["ok"] is False
    for out in (
        tb.browser_fill_form_stub({}),
        tb.browser_go_back_stub({}),
        tb.browser_go_forward_stub({}),
    ):
        assert out.get("limitation") == "browser_agnostic_control"


def test_all_desktop_browser_tools_registered():
    expected = {
        "desktopBrowserOpen", "desktopBrowserNavigate", "desktopBrowserOpenTab",
        "desktopBrowserCloseTab", "desktopBrowserSearch", "desktopBrowserClick",
        "desktopBrowserType", "desktopBrowserFillForm", "desktopBrowserGoBack",
        "desktopBrowserGoForward", "desktopBrowserScroll",
    }
    assert expected.issubset(set(TOOLS))
    for name in expected:
        assert callable(TOOLS[name])


def test_no_local_weak_url_normalizer():
    # The weak unguarded _normalize_url duplicate was removed from
    # tools_browser; ALL URL normalization is tools_websites' guarded version.
    assert not hasattr(tb, "_normalize_url")


def test_state_has_universal_controller_slot_default_none():
    s = State()
    assert s.universal_controller is None


def test_container_wires_state_universal_controller():
    # Architecture invariant: the composition root shares the ONE UC with tool
    # handlers via STATE (grep-checked like the registry sync tests).
    from pathlib import Path
    src = (
        Path(__file__).resolve().parent.parent
        / "desktop_agent" / "core" / "application_container.py"
    ).read_text(encoding="utf-8")
    assert "STATE.universal_controller = self.universal_controller" in src


def test_module_imports_without_playwright():
    # Behavior, not strings: importing the browser module must succeed with
    # no browser engine installed, and must not pull playwright in.
    import importlib
    importlib.reload(tb)
    assert "playwright" not in sys.modules
