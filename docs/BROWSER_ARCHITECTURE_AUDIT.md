# MYRAA — Default Windows Browser Architecture Audit

Status: FINAL (Phase 1 audit + Phase 2–4 implementation complete)
Date: 2026-09-19

## 1. Current architecture

MYRAA's browser capability uses the Windows OS default-browser mechanism only.
There is NO embedded browser, NO bundled Chromium, NO Playwright/Puppeteer/
Selenium, NO custom browser server, NO browser automation daemon.

Canonical open path (single authority):

    openWebsite / searchWeb / searchYouTube / searchGoogle / searchGitHub
    desktopBrowserOpen / desktopBrowserNavigate / desktopBrowserSearch
        -> tools_websites.open_url(raw)
             -> _normalize_url(raw)  [scheme allowlist + host guard]
             -> webbrowser.open(url, new=2)   [OS default browser]
             -> structured result {url, website, application: "default_browser"}

All browser-open and search tools funnel through `tools_websites.open_url` /
`_normalize_url`, so it is the one authoritative open capability.

In-page interaction (single authority):

    desktopBrowserClick / desktopBrowserType / desktopBrowserScroll
        -> UniversalController (THE ONE vision-based automation engine,
           container-created, shared via registry.STATE.universal_controller)
             -> vision/OCR target discovery
             -> registry.dispatch(leftClick/typeText/scrollMouse/moveMouse)
                  -> ValidationLayer -> PermissionManager -> handler
             -> structured ok/limitation result

MYRAA owns no browser engine; the browser window belongs to Windows and is
observed through the existing continuous-vision pipeline (AUTO-START).

## 2. Browser entry points

| Entry | File | Delegates to | State |
|---|---|---|---|
| openWebsite | tools_websites.py | open_url | ACTIVE |
| searchWeb / searchYouTube / searchGoogle / searchGitHub | tools_search.py | open_url | ACTIVE |
| desktopBrowserOpen / Navigate / OpenTab / Search | tools_browser.py | open_url / search_web | ACTIVE |
| desktopBrowserCloseTab | tools_browser.py | foreground check + pressKey("ctrl+w") | ACTIVE (focus-verified) |
| desktopBrowserClick / Type / Scroll | tools_browser.py | UniversalController + registry dispatch | ACTIVE (vision-based) |
| desktopBrowserFillForm | tools_browser.py | (unsupported — ok:false) | EXPLICITLY UNSUPPORTED |
| desktopBrowserGoBack / GoForward | tools_browser.py | (unsupported — ok:false) | EXPLICITLY UNSUPPORTED (unverified-focus hazard) |

## 3. Browser dependencies

- webbrowser (stdlib) — the ONLY open mechanism. ACTIVE.
- No playwright/puppeteer/selenium/chromium in package.json or requirements.txt. ABSENT.
- `local-agent.js` (Playwright Chromium server, :3001) — REMOVED. ABSENT.
- No browser installer UI; BrowserAgent.tsx shows an honest default-browser notice. ACTIVE (dormant component, not in live app chain).


## 4. Security posture (implemented)

`tools_websites._normalize_url` / `_validate_browser_url`:
- ONLY http/https may be opened; javascript:, data:, vbscript:, ms-settings:,
  shell:, cmd:, powershell:, file:, ftp:, ssh:, telnet:, smb: are rejected.
- Internal/private/metadata hosts (localhost, 127.*, 10.*, 192.168.*,
  169.254.*, metadata.google.internal) rejected (SSRF-style, consistent with
  server/routes/proxy.ts isUnsafeUrl).
- URLs embedding credentials rejected.
- Verified behaviorally by tests/test_browser_security.py (33 tests).

Additional hardening in tools_browser.py:
- `_dispatch_tool` routes every browser interaction through the registry
  dispatcher (ValidationLayer + PermissionManager + F7 recovery) and converts
  failures to structured ok:False — never a leaked exception, never a faked
  success.
- `_succeeded` treats explicit ok:False as FAILURE (a truthiness check on
  `result` would read failure envelopes as successes — fixed defect).
- `desktopBrowserCloseTab` refuses Ctrl+W unless the foreground window is a
  browser (win32 foreground check via tools_screenshot).

## 5. Web/screen content is untrusted data

Webpage text and OCR'd screen text are DATA for the brain, never instructions.
There is no path from page content to tool execution that bypasses the Brain →
Plan → PermissionManager → Tool pipeline. (Systemic trust-boundary labelling is
tracked as a cross-cutting roadmap item in the main audit.)


## 6. Dead artifacts removed

- tests/browser_coldstart_profile.py — Playwright cold-start profiler; the
  playwright dependency is removed and the script was not pytest-collected.
- tools_browser.py: dead weak `_normalize_url` duplicate (unguarded, unused,
  security footgun), dead `_sync_wrap` + async re-registration loop (no async
  handlers exist since the Playwright removal), stale Playwright header text.
- registry.py / CLAUDE.md / desktop_agent/README.md / finance docstrings:
  stale Playwright references updated to the default-browser architecture.

## 7. Remaining (classified, not deleted)

- `.kilo/worktrees/knowing-client/` — a git worktree checked out at the initial
  commit, which still contains the old Playwright-era code. STALE ARTIFACT of
  the history, not part of the live chain. Recommend `git worktree remove`
  (it may be managed by the Kilo extension; not auto-removed).
- `.pytest_cache_epic10b/` — stale pytest cache; regenerable, harmless.
- Dormant test files (stress_test.py, test_benchmark_suite.py,
  test_failure_injection.py, test_manual_validation.py,
  test_performance_integration.py, test_soak_procedure.py,
  test_start_stop_restart.py) import symbols that no longer exist
  (`PlaywrightBrowser`, `BrowserTools`, `_ensure_browser_async`) inside
  deferred/skipped functions — they never execute in the suite. Cleanup
  candidates for a dedicated test-hygiene pass.

## 8. Tests

- tests/test_browser_security.py — protocol/host/credential guard (behavioral).
- tests/test_browser_universal_integration.py — behavior tests for the UC
  integration: honest no-UC refusal, click/type/scroll through the dispatcher,
  verbatim typing, target-not-found never acts, focus-verified close-tab,
  honest unsupported actions, registry completeness, no-playwright import,
  STATE/container wiring invariant.
- tests/test_prod_e_universal_control.py::TestNoPlaywright — engine-absence.

## 9. Known limitations (honest)

- DOM/selector automation is intentionally unavailable (no engine).
- GoBack/GoForward require verified browser focus (Alt+Left/Right at the wrong
  focus target is destructive); a future focus+verify implementation could
  enable them safely.
- FillForm is unsupported; use desktopBrowserType per field.
- Scroll lands at the current cursor position; if cursor position is
  unreadable, the vision engine anchors the cursor first.
