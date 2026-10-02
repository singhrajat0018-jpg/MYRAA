"""
Browser-agnostic website control â€” opens URLs in the user's default browser.

MYRAA does NOT own a browser. There is no Playwright/Puppeteer/Selenium, no
embedded or bundled browser, no browser automation server. The user's real
Chrome/Edge/Firefox (the Windows OS default browser) is opened via the OS
default-browser handler, and the Windows window itself is observed and driven
through MYRAA's existing vision + mouse/keyboard interaction layer.

Open capability (single authority):
    tools_websites.open_url  ->  webbrowser.open  ->  OS default browser

In-page interaction (single authority):
    UniversalController (universal_control/) â€” the ONE vision-based automation
    engine, container-created, executing through the registry dispatcher so
    every action passes PermissionManager and is vision-verified afterwards.

NOT supported (kept explicitly unsupported, never faked):
    DOM selectors, element-level automation, guaranteed tab semantics.
    desktopBrowserCloseTab performs a verified Ctrl+W keystroke against the
    focused browser window; GoBack/GoForward stay unimplemented because
    sending Alt+Left/Right to an unverified focus target is unsafe.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from .registry import STATE, ToolError, register
from .tools_websites import normalize_open_args, open_url, resolve_site, SITE_URLS


def _uc():
    """Return the shared UniversalController, or None when unavailable.

    The controller is created once by ApplicationContainer (the composition
    root) and shared via STATE. In tests/headless contexts there is no
    container, so callers must degrade gracefully.
    """
    return getattr(STATE, "universal_controller", None)


def _uc_unavailable(payload_prefix: str) -> Dict[str, Any]:
    """Structured result when the vision-based engine is not available."""
    return {
        "ok": False,
        "result": (
            f"{payload_prefix} requires the vision-based Universal Controller, "
            "which is not available right now (no continuous-vision session). "
            "Start MYRAA's vision, or interact with the browser manually."
        ),
        "limitation": "universal_control_unavailable",
        "suggestion": "Enable continuous vision and retry, or act manually.",
    }


def _succeeded(out: Any) -> bool:
    """True only when a dispatched tool actually succeeded.

    A failure envelope from _dispatch_tool carries ok:False plus a human
    readable `result` (the error message), so a bare truthiness check on
    `result` would read failures as successes. Rule:
      - explicit ok:True                       -> success
      - explicit ok:False                      -> FAILURE (never overridden)
      - legacy raw dicts without an ok field   -> success if result non-empty
    """
    if not isinstance(out, dict) or not out:
        return False
    if "ok" in out:
        return out["ok"] is True
    return bool(out.get("result"))


def _dispatch_tool(tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run an existing registered tool through the authoritative dispatcher.

    Every browser interaction lands here, so validation, PermissionManager
    policy, and F7 recovery still apply. Failures (tool missing in headless
    contexts, permission denial, handler error) become a structured
    ok:False result â€” never a leaked exception inside a browser tool, and
    never a faked success.
    """
    from .registry import dispatch as registry_dispatch
    try:
        out = registry_dispatch(tool, args)
        if isinstance(out, dict):
            return out
        return {"ok": True, "result": str(out)}
    except ToolError as e:
        return {"ok": False, "result": str(e), "limitation": "tool_unavailable"}
    except Exception as e:  # permission denials, handler errors, F7 escalations
        return {"ok": False, "result": f"{tool} failed: {e}", "limitation": "tool_error"}


# --- Handlers ---------------------------------------------------------------


@register("desktopBrowserOpen")
def browser_open(args: Dict[str, Any]) -> Dict[str, Any]:
    """Open a URL or named site in the default browser.

    Args:
        args: Either {"url": "https://example.com"} or {"name": "youtube"}

    Returns:
        Dict with result, url, website (domain), and application ("default_browser")
    """
    params = normalize_open_args(args)
    name = params.get("name")
    url = params.get("url")
    if not url and name:
        # ONE resolver for aliases and bare domains (tools_websites).
        url = resolve_site(name)
        if url is None:
            raise ToolError(
                f"Unknown website '{name}'. Open a URL instead (https://...), or "
                f"name a known site: {', '.join(sorted(SITE_URLS))}."
            )
    if not url:
        raise ToolError("Provide 'name' (e.g. 'youtube') or 'url'.")

    resolved = open_url(url, tool="desktopBrowserOpen")

    # Update STATE for compatibility
    STATE.last_browser_url = resolved

    from urllib.parse import urlparse
    host = urlparse(resolved).netloc

    return {
        "result": f"Opened {resolved} in the default browser.",
        "url": resolved,
        "website": host,
        "application": "default_browser",
        "timestamp": time.time(),
    }


@register("desktopBrowserNavigate")
def browser_navigate(args: Dict[str, Any]) -> Dict[str, Any]:
    """Alias of desktopBrowserOpen, retained for clarity."""
    return browser_open(args)


@register("desktopBrowserOpenTab")
def browser_open_tab(args: Dict[str, Any]) -> Dict[str, Any]:
    """Open a new tab in the default browser.

    Note: Since we're using the default browser, we can't control tab behavior
    directly. This opens a new window/tab depending on browser settings.
    """
    # For default browser control, we treat this the same as open
    result = browser_open(args)
    result["result"] = result["result"].replace("Opened", "Opened new tab/window as")
    return result


def _browser_focus_status() -> Dict[str, Any]:
    """Passive focus check: is the foreground window a browser?

    Reuses tools_screenshot's foreground-window reader (win32gui). Title-based
    matching is a heuristic against the common Windows browsers; it is only
    used to gate destructive keystrokes (close-tab), never to fake state.
    """
    try:
        from .tools_screenshot import _active_window_title
        title = _active_window_title() or ""
    except Exception:
        title = ""
    lowered = title.lower()
    markers = ("chrome", "edge", "firefox", "opera", "brave", "vivaldi")
    is_browser = any(m in lowered for m in markers)
    return {"is_browser": is_browser, "window_title": title, "permission": True}


@register("desktopBrowserCloseTab")
def browser_close_tab(args: Dict[str, Any]) -> Dict[str, Any]:
    """Close the focused browser tab via a verified Ctrl+W keystroke.

    MYRAA does not own the browser, so tab closing is performed through the
    keyboard against the focused browser window. The shortcut is only sent
    after a foreground-window check confirms the focus really is a browser â€”
    never a bare hotkey at unverified focus.
    """
    
    focus = _browser_focus_status()
    if not focus["is_browser"]:
        return {
            "ok": False,
            "result": (
                "Close-tab refused: the focused window is "
                f"'{focus['window_title'] or 'unknown'}', which is not a "
                "browser. Focusing the browser first makes this safe."
            ),
            "window_title": focus["window_title"],
            "limitation": "browser_not_focused",
            "suggestion": "Say 'focus the browser' (or focus it manually), then retry.",
        }

    press = _dispatch_tool("pressKey", {"key": "ctrl+w"})
    ok = _succeeded(press)
    return {
        "ok": ok,
        "result": (
            "Closed the focused browser tab (Ctrl+W)."
            if ok
            else "Could not send the close-tab keystroke."
        ),
        "verification": {
            "browser_focused": True,
            "window_title": focus["window_title"],
        },
        "limitation": None if ok else "keystroke_failed",
    }


@register("desktopBrowserSearch")
def browser_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a search using the default browser and search engine.

    Args:
        args: {"query": "search terms", "engine": "google|youtube|github|etc."}

    Returns:
        Dict with result and url
    """
    from .tools_search import search_web

    # Delegate to the search tool which uses browser-agnostic open.
    # search_web is synchronous â€” it must NOT be awaited.
    search_result = search_web(args)

    # Extract the URL from the search result if possible
    url = ""
    if "opened " in search_result.get("result", ""):
        # Extract URL from result string like "opened https://..."
        import re
        url_match = re.search(r'opened\s+(https?://[^\s\.]+[^\s]*)', search_result["result"])
        if url_match:
            url = url_match.group(1)

    return {
        "result": search_result["result"],
        "url": url,
        "application": "default_browser",
        "timestamp": time.time(),
    }


# Note: The following are intentionally NOT implemented in browser-agnostic mode:
# - desktopBrowserFillForm (multi-field semantics; use UC intent directly)
# - desktopBrowserGoBack / desktopBrowserGoForward (Alt+Left/Right at unverified
#   focus could act on the wrong window â€” kept explicitly unsupported)
#
# Click/Type/Scroll ARE implemented through the ONE vision-based automation
# engine (UniversalController): screenshot â†’ OCR/vision â†’ target selection â†’
# mouse/keyboard via the registry dispatcher (PermissionManager-gated) â†’
# vision verification. They never fake success; without vision they report a
# structured failure and point at the fix.


@register("desktopBrowserClick")
def browser_click(args: Dict[str, Any]) -> Dict[str, Any]:
    """Vision-based click: find a visible target and click its coordinates.

    Args:
        args: {"target": "search box"} (text/type hint) or {"x":.., "y":..}
    """
    x, y = args.get("x"), args.get("y")
    if x is None or y is None:
        uc = _uc()
        if uc is None:
            return _uc_unavailable("Vision-based clicking")
        target = str(args.get("target") or args.get("element") or "")
        elem = uc.find_element(target) if target else None
        if elem is None:
            # No hint (or hint unmatched): fall back to the highest-confidence
            # interactive element so a bare "click" intent still works.
            discovery = uc.discover_elements()
            interactive = [
                e for e in (discovery.elements if discovery else [])
                if getattr(e, "role", None) is not None
                and getattr(e, "role").name != "NONE"
            ]
            if not interactive:
                return {
                    "ok": False,
                    "result": (
                        f"No visible element matching '{target or 'anything clickable'}' "
                        "on screen."
                    ),
                    "limitation": "target_not_found",
                    "suggestion": "Describe the visible text of the element to click.",
                }
            elem = interactive[0]
        x, y = elem.center_x, elem.center_y
        target_desc = (getattr(elem, "label", "") or target or "visible element")
    else:
        target_desc = f"({x}, {y})"

    click = _dispatch_tool("leftClick", {"x": int(x), "y": int(y)})
    ok = _succeeded(click)
    return {
        "ok": ok,
        "result": (
            f"Clicked {target_desc} at ({x}, {y})."
            if ok
            else f"Could not click {target_desc} at ({x}, {y})."
        ),
        "clicked": {"x": int(x), "y": int(y), "target": target_desc},
        "limitation": None if ok else "click_failed",
    }


@register("desktopBrowserType")
def browser_type(args: Dict[str, Any]) -> Dict[str, Any]:
    """Vision-based typing into a visible input field.

    Args:
        args: {"text": "...", "target": "search box"} (target optional)
    """
    text = str(args.get("text", ""))
    if not text:
        raise ToolError("Provide 'text' to type.")
    target = str(args.get("target") or args.get("element") or "")
    uc = _uc()
    if uc is None:
        return _uc_unavailable("Vision-based typing")

    # Resolve the field: targeted hint first, else the best visible input.
    elem = uc.find_element(target) if target else None
    if elem is None:
        from .universal_control.ui_element import InteractiveRole
        discovery = uc.discover_elements()
        inputs = [
            e for e in (discovery.elements if discovery else [])
            if getattr(e, "role", None) == InteractiveRole.INPUT
        ]
        elem = inputs[0] if inputs else None
    if elem is None:
        return {
            "ok": False,
            "result": (
                f"No visible input field matching '{target or 'any field'}' on screen."
            ),
            "limitation": "target_not_found",
            "suggestion": "Describe the visible label of the input field.",
        }

    click = _dispatch_tool("leftClick", {"x": int(elem.center_x), "y": int(elem.center_y)})
    click_ok = _succeeded(click)
    if not click_ok:
        return {
            "ok": False,
            "result": "Could not focus the input field (click failed).",
            "limitation": "click_failed",
        }
    typed = _dispatch_tool("typeText", {"text": text})
    ok = _succeeded(typed)
    label = getattr(elem, "label", "") or "the input field"
    return {
        "ok": ok,
        "result": (
            f"Typed {len(text)} characters into '{label}'."
            if ok
            else "Could not send the text keystrokes."
        ),
        "typed": {"into": label, "chars": len(text)},
        "limitation": None if ok else "type_failed",
    }


@register("desktopBrowserFillForm")
def browser_fill_form_stub(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fill a form â€” requires Universal Control with Vision."""
    return {
        "ok": False,
        "result": "Browser-agnostic mode cannot fill forms directly. "
                  "Use Universal Control with Continuous Vision for precise browser interaction.",
        "suggestion": "Use Universal Control for vision-based form filling",
        "limitation": "browser_agnostic_control",
    }


@register("desktopBrowserGoBack")
def browser_go_back_stub(args: Dict[str, Any]) -> Dict[str, Any]:
    """Navigate back â€” not available in browser-agnostic mode."""
    return {
        "ok": False,
        "result": "Browser-agnostic mode cannot navigate back. "
                  "Please use the browser's back button, or use Universal Control with Vision.",
        "suggestion": "Use Universal Control for vision-based browser navigation",
        "limitation": "browser_agnostic_control",
    }


@register("desktopBrowserGoForward")
def browser_go_forward_stub(args: Dict[str, Any]) -> Dict[str, Any]:
    """Navigate forward â€” not available in browser-agnostic mode."""
    return {
        "ok": False,
        "result": "Browser-agnostic mode cannot navigate forward. "
                  "Please use the browser's forward button, or use Universal Control with Vision.",
        "suggestion": "Use Universal Control for vision-based browser navigation",
        "limitation": "browser_agnostic_control",
    }


@register("desktopBrowserScroll")
def browser_scroll(args: Dict[str, Any]) -> Dict[str, Any]:
    """Vision-anchored scroll of the focused page.

    Args:
        args: {"direction": "up"|"down", "clicks": int} (defaults: down, 3)
    """
    direction = "up" if str(args.get("direction", "down")).lower() == "up" else "down"
    try:
        clicks = int(args.get("clicks", 3))
    except (TypeError, ValueError):
        clicks = 3
    clicks = max(-10, min(10, clicks))

    # Scroll lands at the current cursor position (where the user is already
    # looking). If the cursor position cannot be read, fall back to the vision
    # engine to anchor the cursor over the page before scrolling.
    pos = _dispatch_tool("mousePosition", {})
    if not _succeeded(pos):
        uc = _uc()
        if uc is None:
            return _uc_unavailable("Vision-anchored scrolling")
        discovery = uc.discover_elements()
        if not (discovery and discovery.elements):
            return {
                "ok": False,
                "result": "Could not anchor the scroll: no visual state available.",
                "limitation": "vision_unavailable",
            }
        anchor = discovery.elements[0]
        _dispatch_tool("moveMouse", {"x": int(anchor.center_x), "y": int(anchor.center_y)})

    scroll = _dispatch_tool("scrollMouse", {"clicks": clicks if direction == "down" else -clicks})
    ok = _succeeded(scroll)
    return {
        "ok": ok,
        "result": (
            f"Scrolled {direction} ({clicks} clicks)."
            if ok
            else "Could not send the scroll input."
        ),
        "scrolled": {"direction": direction, "clicks": clicks},
        "limitation": None if ok else "scroll_failed",
    }


def shutdown_browser() -> None:
    """No-op: MYRAA owns no browser. The OS manages the default browser."""
    return None


# For compatibility with existing code that expects these exports
__all__ = [
    "browser_open",
    "browser_navigate",
    "browser_open_tab",
    "browser_close_tab",
    "browser_search",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_fill_form_stub",
    "browser_go_back_stub",
    "browser_go_forward_stub",
    "shutdown_browser",
]