"""Browser-open security guard tests.

Confirms the default-browser architecture and the http/https-only protocol
allowlist in tools_websites.open_url / _normalize_url.

MYRAA MUST use the Windows default browser (no Playwright/Puppeteer/Selenium/
embedded browser). This suite verifies behavior, not just strings:
  - valid web URLs open (no-op under MYRAA_TEST_MODE)
  - dangerous schemes are rejected (no executable/handler protocol escapes)
  - internal/private/metadata hosts are rejected (SSRF-style)
  - URLs with embedded credentials are rejected
  - the canonical open tools all route through the single guarded open_url
"""

from __future__ import annotations

import os

import pytest

from desktop_agent.registry import ToolError
from desktop_agent.tools_websites import SITE_URLS, _normalize_url, _validate_browser_url, open_url


@pytest.fixture(autouse=True)
def _test_mode():
    # Every test: no real browser window is ever opened.
    os.environ["MYRAA_TEST_MODE"] = "true"
    yield
    os.environ.pop("MYRAA_TEST_MODE", None)


# ---------------------------------------------------------------------------
# Valid web URLs
# ---------------------------------------------------------------------------


def test_open_valid_https():
    assert open_url("https://www.youtube.com") == "https://www.youtube.com"


def test_open_valid_http():
    assert open_url("http://example.com/") == "http://example.com/"


def test_open_bare_domain_prefixed():
    assert open_url("youtube.com") == "https://youtube.com"
    assert open_url("example.org/path") == "https://example.org/path"


def test_named_site_shortcuts_allowed():
    # The model-facing SITE_URLS table must only contain http/https entries.
    for url in SITE_URLS.values():
        assert url.startswith(("http://", "https://")), url
    assert _normalize_url(SITE_URLS["youtube"]) == SITE_URLS["youtube"]


# ---------------------------------------------------------------------------
# Dangerous schemes rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "javascript:window.open('http://evil')",
        "data:text/html,<script>1</script>",
        "vbscript:msgbox(1)",
        "ms-settings:display",
        "shell:startup",
        "cmd://calc",
        "powershell://x",
        "file:///C:/Windows/System32/cmd.exe",
        "file:",
        "ftp://x.com",
        "ssh://host",
        "telnet://host",
        "smb://host",
        "gopher://host",
    ],
)
def test_dangerous_schemes_rejected(url):
    with pytest.raises(ToolError):
        open_url(url)
    with pytest.raises(ToolError):
        _normalize_url(url)


# ---------------------------------------------------------------------------
# Internal / private / metadata hosts rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost/x",
        "http://192.168.1.1/x",
        "http://10.0.0.5/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/",
    ],
)
def test_internal_hosts_rejected(url):
    with pytest.raises(ToolError):
        open_url(url)


# ---------------------------------------------------------------------------
# Embedded credentials rejected
# ---------------------------------------------------------------------------


def test_embedded_credentials_rejected():
    with pytest.raises(ToolError):
        open_url("https://user:pass@example.com/")
    with pytest.raises(ToolError):
        open_url("http://user@example.com/")


# ---------------------------------------------------------------------------
# Canonical open-capability: all open/search tools route through the guard
# ---------------------------------------------------------------------------


def test_open_website_routes_through_guard():
    from desktop_agent.tools_websites import open_website

    # A dangerous URL supplied via the tool must be rejected, not opened.
    with pytest.raises(ToolError):
        open_website({"url": "file:///C:/Windows/System32/cmd.exe"})
    # A valid one resolves.
    out = open_website({"url": "https://example.com"})
    assert out["url"] == "https://example.com"
    assert out["application"] == "default_browser"
    # A named site resolves.
    out2 = open_website({"name": "youtube"})
    assert out2["website"] == "www.youtube.com"


def test_desktop_browser_tools_share_guard():
    from desktop_agent.tools_browser import browser_open, browser_navigate
    from desktop_agent.registry import TOOLS

    # The browser-agnostic open tools are registered and delegate to open_url.
    assert "desktopBrowserOpen" in TOOLS
    assert "desktopBrowserNavigate" in TOOLS
    with pytest.raises(ToolError):
        browser_open({"url": "javascript:alert(1)"})
    assert browser_open({"name": "youtube"})["application"] == "default_browser"


def test_validate_browser_url_malformed():
    with pytest.raises(ToolError):
        _validate_browser_url("http://")  # missing host


# ---------------------------------------------------------------------------
# 172.16.0.0/12 private range blocked (SSRF parity with proxy.ts isUnsafeUrl)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://172.16.0.1/",
        "http://172.20.10.5/admin",
        "http://172.31.255.255/x",
    ],
)
def test_rfc1918_172_16_range_rejected(url):
    with pytest.raises(ToolError):
        open_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://172.15.0.1/",  # just below the private range
        "http://172.32.0.1/",  # just above the private range
    ],
)
def test_adjacent_172_addresses_not_blocked_by_range_guard(url):
    # The range guard itself must not over-block; full open_url still applies
    # the remaining guards (these hosts are public test addresses here).
    from desktop_agent.tools_websites import _is_rfc1918_172_16
    from urllib.parse import urlparse

    assert _is_rfc1918_172_16(urlparse(url).hostname or "") is False


def test_is_rfc1918_172_16_boundaries():
    from desktop_agent.tools_websites import _is_rfc1918_172_16

    assert _is_rfc1918_172_16("172.16.0.1") is True
    assert _is_rfc1918_172_16("172.31.255.255") is True
    assert _is_rfc1918_172_16("172.15.255.255") is False
    assert _is_rfc1918_172_16("172.32.0.1") is False
    assert _is_rfc1918_172_16("example.com") is False


# ---------------------------------------------------------------------------
# desktopBrowserOpen/Navigate accept {"name"} (parity with openWebsite)
# ---------------------------------------------------------------------------


def test_desktop_browser_open_name_only_passes_validation():
    from desktop_agent.registry import ValidationLayer

    out = ValidationLayer.validate({"name": "youtube"}, None, tool_name="desktopBrowserOpen")
    assert out == {"name": "youtube"}
    out2 = ValidationLayer.validate({"name": "youtube"}, None, tool_name="desktopBrowserNavigate")
    assert out2 == {"name": "youtube"}


def test_desktop_browser_open_empty_still_rejected():
    from desktop_agent.registry import ValidationLayer

    with pytest.raises(ToolError):
        ValidationLayer.validate({}, None, tool_name="desktopBrowserOpen")
    with pytest.raises(ToolError):
        ValidationLayer.validate({"name": ""}, None, tool_name="desktopBrowserNavigate")
