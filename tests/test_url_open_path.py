"""Regression tests: "MYRAA, open YouTube" must open the Windows default browser.

Covers the fixed URL-opening path end to end:

  1. youtube / 2. google alias resolution   3. https URLs allowed
  4. dangerous schemes rejected             5. tool schema == executor
  6. PermissionManager allows the action    7. launcher success reported
  8. launcher failure reported              9. no shell injection
 10. no hardcoded browser executable       11. Playwright NOT required
 12. existing computer tools unaffected

The root conftest forces MYRAA_TEST_MODE=true, so no test opens a real browser
unless it explicitly exercises the launcher (and then monkeypatches it).
"""

from __future__ import annotations

import inspect
import logging
import pathlib
import re

import pytest

from desktop_agent.config.permissions import OR_REQUIRED_ARGS
from desktop_agent.registry import (
    TOOLS,
    PermissionManager,
    ToolError,
    ValidationLayer,
    load_all,
)
from desktop_agent.tools_applications import _resolve_app, open_application
from desktop_agent.tools_browser import browser_navigate, browser_open
from desktop_agent.tools_websites import (
    SITE_URLS,
    _normalize_url,
    _validate_browser_url,
    is_known_site,
    normalize_open_args,
    open_url,
    resolve_site,
)

load_all()

OPEN_TOOLS = ("openWebsite", "desktopBrowserOpen", "desktopBrowserNavigate")

# The exact commands from the bug report and their required destination.
CANONICAL_COMMANDS = {
    "Open YouTube": "https://www.youtube.com",
    "Open Google": "https://www.google.com",
    "Open Gmail": "https://mail.google.com",
    "Open GitHub": "https://github.com",
    "Open https://www.youtube.com": "https://www.youtube.com",
    "Go to YouTube": "https://www.youtube.com",
    "Open YouTube in my browser": "https://www.youtube.com",
}


# ---------------------------------------------------------------------------
# 1 + 2. Alias resolution (youtube, google, gmail, github, chatgpt)
# ---------------------------------------------------------------------------


def test_youtube_alias_resolves_correctly():
    assert resolve_site("youtube") == "https://www.youtube.com"
    assert resolve_site("YouTube") == "https://www.youtube.com"
    assert resolve_site("youtube.com") == "https://www.youtube.com"
    assert resolve_site("www.youtube.com") == "https://www.youtube.com"
    assert is_known_site("youtube")


def test_google_alias_resolves_correctly():
    assert resolve_site("google") == "https://www.google.com"
    assert SITE_URLS["google"] == "https://www.google.com"


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("gmail", "https://mail.google.com"),
        ("github", "https://github.com"),
        ("chatgpt", "https://chatgpt.com"),
    ],
)
def test_other_required_aliases_resolve(alias, expected):
    assert resolve_site(alias) == expected
    assert SITE_URLS[alias] == expected
    # open_url is URL-only by design: it never guesses an alias.
    assert open_url(expected) == expected


def test_alias_table_is_the_single_authority():
    """The resolver is the only site table; brain layers must not keep copies."""
    from desktop_agent.brain.performance import fast_path as perf
    from desktop_agent.brain.router import command_patterns as patterns
    from desktop_agent.brain.router import task_router

    for module in (perf, patterns, task_router):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8", errors="ignore")
        assert "https://www.youtube.com" not in source, module.__file__
        assert "https://mail.google.com" not in source, module.__file__


# ---------------------------------------------------------------------------
# 3. http/https URLs are allowed; 4. dangerous schemes are rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    ["https://www.youtube.com", "http://example.com/", "https://github.com/a/b?c=1"],
)
def test_https_and_http_urls_allowed(url):
    assert open_url(url) == url
    _validate_browser_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
        "vbscript:msgbox(1)",
        "file:///C:/Windows/System32/cmd.exe",
        "shell:startup",
        "powershell://x",
        "cmd://calc",
        "ms-settings:display",
    ],
)
def test_dangerous_schemes_rejected_by_resolver_and_launcher(url):
    with pytest.raises(ToolError):
        open_url(url)
    with pytest.raises(ToolError):
        _normalize_url(url)
    # The resolver must never hand a dangerous scheme to the brain as a site.
    assert resolve_site(url) is None


# ---------------------------------------------------------------------------
# 5. Tool schema matches the executor (declaration -> validation -> handler)
# ---------------------------------------------------------------------------


def test_declared_open_tool_args_match_the_executor():
    from desktop_agent.speech.gemini_live import GEMINI_TOOL_ALLOWLIST

    for tool in OPEN_TOOLS:
        _, props, _ = GEMINI_TOOL_ALLOWLIST[tool]
        assert props, f"{tool} declares no arguments"
        for prop in props:
            # Every declared argument must survive validation (no
            # url-vs-website style schema mismatch) and reach the handler.
            validated = ValidationLayer.validate({prop: "youtube"}, None, tool_name=tool)
            assert prop in validated

    for tool in OPEN_TOOLS:
        assert set(OR_REQUIRED_ARGS[tool]) >= {"name", "url", "website", "target", "site"}


def test_open_tool_aliases_fold_onto_canonical_keys():
    for args in ({"website": "youtube"}, {"target": "youtube"}, {"site": "youtube"},
                 {"link": "youtube"}, {"name": "youtube"}):
        folded = normalize_open_args(args)
        assert "url" in folded or "name" in folded


def test_empty_open_args_still_rejected():
    for tool in OPEN_TOOLS:
        with pytest.raises(ToolError, match="requires one of"):
            ValidationLayer.validate({}, None, tool_name=tool)


def test_every_canonical_command_reaches_the_url_opener():
    """Spoken command -> brain action -> openWebsite(url) for the canonical URL."""
    from desktop_agent.brain.semantic.semantic_parser import SemanticParser

    parser = SemanticParser()
    for command, expected in CANONICAL_COMMANDS.items():
        task = parser.parse(command)
        assert task.metadata.get("action") == "openWebsite", command
        assert task.metadata["parameters"]["url"] == expected, command


def test_executor_opens_the_resolved_url_for_every_open_tool():
    for tool in OPEN_TOOLS:
        handler = getattr(TOOLS[tool], "__raw_handler__", TOOLS[tool])
        out = handler({"name": "youtube"})
        assert out["url"] == "https://www.youtube.com"
        assert out["application"] == "default_browser"


def test_website_named_command_never_goes_to_the_app_launcher():
    """'Open YouTube' must not be routed as an application launch."""
    from desktop_agent.brain.performance.fast_path import FastPath
    from desktop_agent.brain.router.task_router import TaskRouter

    fp = FastPath()
    for command in ("open youtube", "open google", "open gmail", "open github",
                    "open youtube in my browser"):
        result = fp.match(command)
        assert result.matched
        assert result.tool_name == "openWebsite", command
        assert result.args["url"].startswith("https://"), command

    # Applications are still applications.
    assert fp.match("open notepad").tool_name == "openApplication"

    router = TaskRouter()
    for command in ("Open YouTube", "Open Gmail", "Open GitHub"):
        decision = router.route(command)
        assert decision.task_type.name == "BROWSER_ACTION", command
        assert "openApplication" not in decision.tool_names, command
    # ...while a real application still routes as a desktop action.
    notepad = router.route("Open Notepad")
    assert notepad.task_type.name == "DESKTOP_ACTION"
    assert "openApplication" in notepad.tool_names


# ---------------------------------------------------------------------------
# 6. PermissionManager allows the correct action
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool", OPEN_TOOLS)
def test_permission_manager_allows_url_opening(tool):
    decision = PermissionManager.check(tool, {"name": "youtube"})
    assert decision.allowed is True
    assert decision.decision == "allow"
    assert decision.category == "INTERACT"


def test_permission_denial_still_enforced_for_unknown_tool():
    """The permission model is untouched: unknown tools fail closed."""
    assert PermissionManager.check("totallyUnknownTool", {}).allowed is False


# ---------------------------------------------------------------------------
# 7. Successful launcher returns success  8. Failure returns failure
# ---------------------------------------------------------------------------


def test_successful_launch_returns_success(monkeypatch, caplog):
    from desktop_agent import tools_websites

    monkeypatch.delenv("MYRAA_TEST_MODE", raising=False)
    launched = []
    monkeypatch.setattr(tools_websites, "_launch_default_browser",
                        lambda url: (launched.append(url), True)[1])

    with caplog.at_level(logging.INFO, logger="myraa.desktop.core"):
        resolved = open_url(SITE_URLS["youtube"], request_id="REQ-SUCCESS",
                            tool="openWebsite")

    assert resolved == "https://www.youtube.com"
    assert launched == ["https://www.youtube.com"]
    events = caplog.text
    for event in ("URL_OPEN_REQUEST", "URL_RESOLVED", "URL_VALIDATED",
                  "URL_LAUNCH_STARTED", "URL_LAUNCH_SUCCESS"):
        assert event in events
    assert "REQ-SUCCESS" in events
    assert "URL_LAUNCH_FAILED" not in events


def test_failed_launch_returns_failure(monkeypatch, caplog):
    from desktop_agent import tools_websites

    monkeypatch.delenv("MYRAA_TEST_MODE", raising=False)
    monkeypatch.setattr(tools_websites, "_launch_default_browser", lambda url: False)

    with caplog.at_level(logging.INFO, logger="myraa.desktop.core"):
        with pytest.raises(ToolError) as err:
            open_url("https://www.youtube.com", request_id="REQ-FAIL")

    assert "Browser open failed" in str(err.value)
    assert "Windows could not launch the default browser" in str(err.value)
    assert "URL_LAUNCH_FAILED" in caplog.text
    assert "URL_LAUNCH_SUCCESS" not in caplog.text


def test_tool_reports_failure_truthfully(monkeypatch):
    """The handler must not claim success when the OS launch fails."""
    from desktop_agent import tools_websites

    monkeypatch.delenv("MYRAA_TEST_MODE", raising=False)
    monkeypatch.setattr(tools_websites, "_launch_default_browser", lambda url: False)
    with pytest.raises(ToolError):
        tools_websites.open_website({"name": "youtube"})


def test_test_mode_guard_never_opens_a_browser(monkeypatch):
    from desktop_agent import tools_websites

    monkeypatch.setenv("MYRAA_TEST_MODE", "true")

    def _boom(url):  # pragma: no cover - must never run
        raise AssertionError("a real browser launch was attempted in test mode")

    monkeypatch.setattr(tools_websites, "_launch_default_browser", _boom)
    assert open_url(SITE_URLS["youtube"]) == SITE_URLS["youtube"]


# ---------------------------------------------------------------------------
# 9. No shell injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/?a=1&b=$(calc)",
        "https://example.com/`calc`",
        "https://example.com/;calc",
        "https://example.com/|calc",
        "https://example.com/&calc&",
        "https://example.com/$(powershell -c calc)",
        "https://example.com/%0acalc",
    ],
)
def test_url_is_passed_verbatim_and_never_through_a_shell(monkeypatch, url):
    from desktop_agent import tools_websites

    monkeypatch.delenv("MYRAA_TEST_MODE", raising=False)
    seen = {}

    monkeypatch.setattr(tools_websites.os, "startfile",
                        lambda target: seen.setdefault("startfile", target), raising=False)
    monkeypatch.setattr(tools_websites.webbrowser, "open",
                        lambda target, new=0: (seen.setdefault("webbrowser", target),
                                               True)[1])

    def _no_shell(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("a shell/subprocess was used to open a URL")

    monkeypatch.setattr(tools_websites.os, "system", _no_shell, raising=False)
    import subprocess

    monkeypatch.setattr(subprocess, "run", _no_shell)
    monkeypatch.setattr(subprocess, "Popen", _no_shell)

    resolved = open_url(url)
    assert resolved == url
    # Verbatim handoff: no shell metacharacter was interpreted or rewritten.
    assert seen.get("startfile") == url


def test_launcher_uses_no_shell_execution_primitives():
    source = pathlib.Path("desktop_agent/tools_websites.py").read_text(encoding="utf-8")
    for forbidden in ("os.system", "shell=True", "subprocess.Popen", "subprocess.run",
                      "os.popen"):
        assert forbidden not in source, f"forbidden shell primitive: {forbidden}"


# ---------------------------------------------------------------------------
# 10. Default browser executable is NOT hardcoded
# ---------------------------------------------------------------------------


def test_no_browser_executable_is_hardcoded():
    source = pathlib.Path("desktop_agent/tools_websites.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for executable in ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
                       "opera.exe", "vivaldi.exe"):
        assert executable not in lowered
    # The launcher delegates to the OS association only.
    assert "os.startfile" in source
    assert "webbrowser.open" in source


def test_launcher_prefers_os_url_association(monkeypatch):
    from desktop_agent import tools_websites

    monkeypatch.delenv("MYRAA_TEST_MODE", raising=False)
    calls = []
    monkeypatch.setattr(tools_websites.os, "startfile",
                        lambda url: calls.append(url), raising=False)

    def _unexpected(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("webbrowser.open used although os.startfile succeeded")

    monkeypatch.setattr(tools_websites.webbrowser, "open", _unexpected)
    assert open_url(SITE_URLS["youtube"]) == "https://www.youtube.com"
    assert calls == ["https://www.youtube.com"]


def test_open_url_takes_no_browser_argument():
    assert list(inspect.signature(open_url).parameters) == ["url", "request_id", "tool"]


# ---------------------------------------------------------------------------
# 11. Playwright is NOT required
# ---------------------------------------------------------------------------


def test_browser_automation_dependencies_absent():
    root = pathlib.Path(".")
    package_json = (root / "package.json").read_text(encoding="utf-8").lower()
    for banned in ("playwright", "puppeteer", "selenium", "webdriver"):
        assert banned not in package_json, f"{banned} must not be a dependency"

    import_pattern = re.compile(
        r"^\s*(?:import|from)\s+(playwright|selenium|pyppeteer|seleniumbase)\b",
        re.MULTILINE,
    )
    for folder in ("desktop_agent", "src", "server", "services"):
        for path in (root / folder).rglob("*.py"):
            source = path.read_text(encoding="utf-8", errors="ignore")
            assert not import_pattern.search(source), f"browser automation import in {path}"


def test_open_path_uses_webbrowser_only():
    source = pathlib.Path("desktop_agent/tools_websites.py").read_text(encoding="utf-8")
    assert "webbrowser" in source
    for banned in ("playwright", "puppeteer", "selenium"):
        assert banned not in source.lower()


# ---------------------------------------------------------------------------
# 12. Existing computer tools remain unaffected
# ---------------------------------------------------------------------------


def test_application_launch_unchanged_for_real_apps():
    assert _resolve_app("notepad")["label"] == "Notepad"
    assert _resolve_app("chrome")["label"] == "Google Chrome"
    assert resolve_site("notepad") is None
    with pytest.raises(ToolError):
        open_application({"name": "definitely-not-an-app-and-not-a-site"})


def test_application_tool_delegates_only_known_sites(monkeypatch):
    """'open youtube' via openApplication opens the site; real apps unaffected."""
    from desktop_agent import tools_websites

    opened = []
    monkeypatch.setattr(tools_websites, "open_url",
                        lambda url, **kw: (opened.append(url), url)[1])
    out = open_application({"name": "youtube"})
    assert out["url"] == "https://www.youtube.com"
    assert out["application"] == "default_browser"
    assert opened == ["https://www.youtube.com"]


def test_unrelated_desktop_tools_still_execute():
    for tool in ("systemInfo", "currentDateTime"):
        assert tool in TOOLS
        assert isinstance(TOOLS[tool]({}), dict)


def test_desktop_browser_tools_share_the_single_resolver():
    assert browser_open({"name": "youtube"})["url"] == "https://www.youtube.com"
    assert browser_navigate({"name": "google"})["url"] == "https://www.google.com"
    with pytest.raises(ToolError):
        browser_open({"url": "javascript:alert(1)"})


def test_no_site_table_duplicated_outside_tools_websites():
    """Requirement: do not scatter website mappings across multiple files."""
    offenders = []
    for path in pathlib.Path("desktop_agent").rglob("*.py"):
        if path.name == "tools_websites.py":
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r'''["']youtube["']\s*:\s*["']https?://''', source):
            offenders.append(str(path))
    assert not offenders, f"duplicate website alias tables found in: {offenders}"



