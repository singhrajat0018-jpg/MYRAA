"""
Website control: open named sites or arbitrary URLs in the default browser.

SINGLE AUTHORITY for website→URL resolution in MYRAA. ``SITE_URLS`` and
``resolve_site()`` are the one alias table; the brain/router layers import them
instead of keeping their own copies.

Uses the OS default-browser handler so the user's real Chrome/Edge/Firefox
opens at the requested destination. MYRAA owns no browser engine; the dormant
in-app BrowserAgent view is not part of the live chain. No browser executable is
ever hardcoded — Windows decides through the URL association.

Every launch emits structured diagnostics:
    URL_OPEN_REQUEST / URL_RESOLVED / URL_VALIDATED /
    URL_LAUNCH_STARTED / URL_LAUNCH_SUCCESS / URL_LAUNCH_FAILED
"""

from __future__ import annotations

import os
import time
import uuid
import webbrowser
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

from .registry import ToolError, register, slog

# Named shortcuts the model can request by friendly name.
SITE_URLS: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://chat.openai.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "wikipedia": "https://www.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "linkedin": "https://www.linkedin.com",
    "maps": "https://maps.google.com",
    "translate": "https://translate.google.com",
    "drive": "https://drive.google.com",
    "calendar": "https://calendar.google.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "huggingface": "https://huggingface.co",
}


# ── Centralized website resolver (single authority) ────────────────
# Every layer (brain router, fast path, semantic mapper, tool handlers) resolves
# a spoken site name through these helpers. No other module keeps a site table.

# Trailing generic TLDs stripped before the SITE_URLS lookup so
# "youtube.com" / "www.youtube.com" / "YouTube" share one canonical entry.
_SITE_SUFFIXES = (".com", ".org", ".net", ".in", ".io", ".co", ".ai", ".tv", ".me")


def _site_key(value: str) -> str:
    """Normalize a spoken site name into a SITE_URLS lookup key."""
    key = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    if key.startswith("www."):
        key = key[4:]
    for suffix in _SITE_SUFFIXES:
        if key.endswith(suffix):
            key = key[: -len(suffix)]
            break
    return key


def is_known_site(value: str) -> bool:
    """True when ``value`` names a site MYRAA may open by alias."""
    key = _site_key(value)
    return bool(key) and key in SITE_URLS


def resolve_site(value: str) -> Optional[str]:
    """Resolve a spoken site name OR URL to a canonical http(s) URL.

    THE website resolver for the whole system. Returns ``None`` when the value
    is neither a known alias nor a URL that survives the http/https-only
    security policy. Never raises: the same value may legitimately be an
    application name, and the caller decides whether a miss is an error.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    key = _site_key(raw)
    if key in SITE_URLS:
        return SITE_URLS[key]
    # A bare host / URL must be a single token ("youtube.com", "example.org/x")
    # so a spoken sentence fragment ("open the file notes.txt") is never turned
    # into a bogus URL. Blocked hosts still fail closed via _normalize_url.
    if "://" in raw or ("." in key and not any(ch.isspace() for ch in raw)):
        try:
            return _normalize_url(raw)
        except ToolError:
            return None
    return None


# Argument aliases accepted by the open tools. Guards the schema-mismatch class
# the model can produce (url vs URL vs website vs target vs site): a differently
# named destination still reaches the ONE resolver instead of failing.
_URL_ALIASES = ("url", "website", "target", "site", "link", "address")
_NAME_ALIASES = ("name", "app", "application")


def normalize_open_args(args: Any) -> Dict[str, Any]:
    """Fold accepted URL/name aliases onto canonical ``url`` / ``name`` keys."""
    out: Dict[str, Any] = {}
    for key, value in dict(args or {}).items():
        out[str(key).strip().lower()] = value
    if not out.get("url"):
        for alias in _URL_ALIASES:
            if out.get(alias):
                out["url"] = out[alias]
                break
    if not out.get("name"):
        for alias in _NAME_ALIASES:
            if out.get(alias):
                out["name"] = out[alias]
                break
    for alias in _URL_ALIASES[1:]:
        out.pop(alias, None)
    for alias in _NAME_ALIASES[1:]:
        out.pop(alias, None)
    return out


# Dangerous schemes that must be rejected even without "://" (e.g. a bare
# "javascript:alert(1)" or "ms-settings:display"). You cannot safely whitelist
# these by prefixing https:// — reject them outright before normalization.
_ALWAYS_BLOCKED_PREFIXES = (
    "javascript:", "data:", "vbscript:", "ms-settings:", "shell:",
    "cmd:", "powershell:", "file:", "ftp:", "ssh:", "telnet:", "smb:",
)


def _normalize_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise ToolError("Empty URL.")
    lowered = url.lower()
    if any(lowered.startswith(p) for p in _ALWAYS_BLOCKED_PREFIXES):
        prefix = next(p for p in _ALWAYS_BLOCKED_PREFIXES if lowered.startswith(p))
        raise ToolError(
            f"URL blocked: scheme '{prefix}' is not allowed. "
            "Only http and https URLs can be opened (security policy)."
        )
    if "://" not in url:
        # Treat bare "youtube.com" as https://youtube.com
        url = "https://" + url
    _validate_browser_url(url)
    return url


# Authoritative browser-open security policy. Only http/https (the web) may be
# opened in the user's default browser. Everything else — file:, javascript:,
# data:, vbscript:, ms-settings:, shell:, cmd:, ssh:, etc. — is rejected so a
# hostile or malformed URL can never execute a local program or a shell handler.
# Localhost / private / link-local metadata hosts are also blocked (SSRF-style,
# consistent with server/routes/proxy.ts isUnsafeUrl).
_ALLOWED_BROWSER_PROTOCOLS = ("http", "https")

# RFC1918 private + link-local + loopback prefixes (lowercased host compare).
_BLOCKED_BROWSER_HOST_PREFIXES = (
    "localhost", "127.", "10.", "192.168.", "169.254.",
    "[::1]", "::1", "0.",
)
_BLOCKED_BROWSER_HOST_EXACT = {"metadata.google.internal", "169.254.169.254"}


def _is_rfc1918_172_16(host: str) -> bool:
    """True for the 172.16.0.0/12 private range (172.16.x.x – 172.31.x.x).

    SSRF parity with server/routes/proxy.ts isUnsafeUrl, which blocks
    172.16–31. Prefix matching cannot express this range, so parse the
    second octet explicitly.
    """
    if not host.startswith("172."):
        return False
    try:
        second = int(host.split(".")[1])
    except (IndexError, ValueError):
        return False
    return 16 <= second <= 31


def _validate_browser_url(url: str) -> None:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        proto = parsed.scheme.lower()
        if proto not in _ALLOWED_BROWSER_PROTOCOLS:
            raise ToolError(
                f"URL blocked: protocol '{proto or '(none)'}' is not allowed. "
                "Only http:// and https:// URLs can be opened (security policy)."
            )
        host = (parsed.hostname or "").lower()
        if not host:
            raise ToolError("URL blocked: missing host.")
        if host in _BLOCKED_BROWSER_HOST_EXACT:
            raise ToolError("URL blocked: internal/metadata host not allowed.")
        if any(host.startswith(p) for p in _BLOCKED_BROWSER_HOST_PREFIXES):
            raise ToolError("URL blocked: local/private/internal host not allowed.")
        if _is_rfc1918_172_16(host):
            raise ToolError("URL blocked: local/private/internal host not allowed.")
        # Reject URLs embedding credentials ("https://user:pass@host").
        if parsed.username or parsed.password:
            raise ToolError("URL blocked: embedded credentials are not allowed.")
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"URL blocked: malformed URL ({e}).")


def _launch_default_browser(url: str) -> bool:
    """Hand the URL to the OS; Windows decides which browser that is.

    No browser executable is ever named here. ``os.startfile`` uses the Windows
    shell URL association (the OS-level default-browser mechanism), and
    ``webbrowser`` uses the registered default browser. Returns True only when
    the launch was actually accepted, so success is never faked.
    """
    startfile = getattr(os, "startfile", None)
    if startfile is not None:
        try:
            startfile(url)
            return True
        except OSError:
            pass  # fall through to the stdlib default-browser handler
    try:
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False


def open_url(url: str, *, request_id: Optional[str] = None,
             tool: str = "openWebsite") -> str:
    """Open a URL in the default browser; returns the resolved URL.

    Raises ToolError when the URL is not permitted or when Windows could not
    launch the default browser. A successful return means the OS accepted the
    launch — never an optimistic report.
    """
    request_id = request_id or f"U{uuid.uuid4().hex[:8].upper()}"
    slog.info("URL_OPEN_REQUEST", requestId=request_id, tool=tool,
              url=str(url), timestamp=time.time())

    resolved = _normalize_url(url)
    slog.info("URL_RESOLVED", requestId=request_id, tool=tool,
              url=resolved, timestamp=time.time())

    _validate_browser_url(resolved)
    slog.info("URL_VALIDATED", requestId=request_id, tool=tool,
              url=resolved, timestamp=time.time())

    # Test-mode guard (conftest sets MYRAA_TEST_MODE=true for every test):
    # automated runs never open a real browser window.
    if os.environ.get("MYRAA_TEST_MODE") == "true":
        return resolved

    slog.info("URL_LAUNCH_STARTED", requestId=request_id, tool=tool,
              url=resolved, timestamp=time.time())
    if not _launch_default_browser(resolved):
        slog.error(
            "URL_LAUNCH_FAILED",
            RuntimeError("OS could not launch the default browser"),
            requestId=request_id, tool=tool, url=resolved, timestamp=time.time(),
        )
        raise ToolError(
            "Browser open failed: Windows could not launch the default browser "
            f"for {resolved}."
        )
    slog.info("URL_LAUNCH_SUCCESS", requestId=request_id, tool=tool,
              url=resolved, timestamp=time.time())
    return resolved


@register("openWebsite")
def open_website(args: Dict[str, Any]) -> Dict[str, Any]:
    params = normalize_open_args(args)
    name = params.get("name")
    url = params.get("url")
    if not url and name:
        # ONE resolver for aliases and bare domains.
        url = resolve_site(name)
        if url is None:
            raise ToolError(
                f"Unknown website '{name}'. Open a URL instead (https://...), or "
                f"name a known site: {', '.join(sorted(SITE_URLS))}."
            )
    if not url:
        raise ToolError("Provide 'name' (e.g. 'youtube') or 'url'.")
    resolved = open_url(url, tool="openWebsite")

    host = urlparse(resolved).netloc

    return {
        "result": f"Opened {resolved} in the default browser.",
        "url": resolved,
        "website": host,
        "application": "default_browser",
    }


# Expose for sibling modules (tools_search).
def _build_search_url(engine: str, query: str) -> str:
    q = quote(query)
    base = {
        "google": f"https://www.google.com/search?q={q}",
        "youtube": f"https://www.youtube.com/results?search_query={q}",
        "github": f"https://github.com/search?q={q}&type=repositories",
        "chatgpt": f"https://www.google.com/search?q={q}",  # no search API
        "duckduckgo": f"https://duckduckgo.com/?q={q}",
        "bing": f"https://www.bing.com/search?q={q}",
        "amazon": f"https://www.amazon.com/s?k={q}",
        "wikipedia": f"https://en.wikipedia.org/w/index.php?search={q}",
    }
    if engine not in base:
        raise ToolError(
            f"Unsupported search engine '{engine}'. Choose from "
            f"{', '.join(sorted(base))}."
        )
    return base[engine]


__all__ = [
    "open_website",
    "open_url",
    "resolve_site",
    "is_known_site",
    "normalize_open_args",
    "SITE_URLS",
    "_build_search_url",
]
