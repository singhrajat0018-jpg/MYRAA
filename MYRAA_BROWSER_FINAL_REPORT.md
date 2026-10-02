# MYRAA — Default Windows Browser Final Report (Phases 1–6)

Date: 2026-09-19
Architecture enforced: Windows OS default browser ONLY. No Playwright / Puppeteer /
Selenium / Chromium automation / embedded browser / BrowserView / headless browser /
custom browser server / :3001 / local-agent.js. Nothing in this pass installs,
restores, or proposes any forbidden dependency.

## 1. Initial architecture (as found)

Already default-browser by design: `tools_websites.open_url → webbrowser.open`
single open authority with scheme/host guards; `desktopBrowser*` tools delegating
to it; in-page interaction via the ONE vision engine (UniversalController →
registry.dispatch → PermissionManager → vision verify); unsupported actions as
honest ok:false stubs; `local-agent.js`/:3001 already removed from disk;
`package.json`/`requirements.txt` free of forbidden deps. Prior art
`docs/BROWSER_ARCHITECTURE_AUDIT.md` described this; Phase 1 re-verified every
claim against live code (see root `BROWSER_ARCHITECTURE_AUDIT.md`).

## 2. Problems discovered (all behavior-verified)

- P1 — `desktopBrowserOpen`/`desktopBrowserNavigate` rejected valid
  `{"name": <site>}` calls at `ValidationLayer` (required `["url"]`, no OR
  entry), while handlers, Gemini decls, and tests all accept `name`. Real paths
  (POST /execute, unified dispatch, Gemini voice) all hit the gate. Reproduced
  before fix.
- P2 — Python URL guard missed the 172.16.0.0/12 private range (Node
  `isUnsafeUrl` blocks 172.16–31). `open_url("http://172.20.10.5/")` passed.
- P3 — Model-facing Gemini decls said "MYRAA browser" (no such thing); Navigate
  decl lacked the `name` prop its handler accepts.
- P4 — 8 stale "Playwright automation browser" references (CLAUDE.md x2,
  tools_search.py, tools_websites.py, permissions.py comment,
  desktop_agent.spec comment, EPIC-14F-SUMMARY.md, gemini strings).
- P5 (latent) — dormant `BrowserAgent.tsx`: unsandboxed `/api/web-proxy`
  iframe + origin-unchecked `postMessage` NAVIGATE handler + same-origin DOM
  scripting. Dormant (not in live chain) but live endpoint behind it.

## 3. Problems fixed

- P1: `OR_REQUIRED_ARGS` += desktopBrowserOpen/Navigate `["name","url"]`;
  `TOOL_REQUIRED_ARGS` both → `["name","url"]`. Verified: name-only now passes.
- P2: `_is_rfc1918_172_16()` + check in `_validate_browser_url` (parity with
  proxy.ts). Boundary-tested (172.16/172.31 blocked; 172.15/172.32 not).
- P3: decls → "Windows default browser"; `name` prop added to Navigate.
- P4: all 8 reworded; `excludes=["playwright"]` bundle hardening kept.
- P5: iframe `sandbox="allow-scripts allow-forms allow-popups"`
  `referrerPolicy="no-referrer"` (opaque origin — upstream JS can no longer run
  with MYRAA origin privilege); handler accepts same-origin or sandboxed-null
  only + rejects javascript:/data:/vbscript: targets. Side effect (intended):
  the dormant view's same-origin DOM scripting now fails closed into its
  existing honest error callbacks — in-page interaction belongs to UC/vision.

## 4. Files changed

1. `desktop_agent/config/permissions.py` — P1 (+P4 comment).
2. `desktop_agent/tools_websites.py` — P2 (+P4 header).
3. `desktop_agent/tools_search.py` — P4 docstring.
4. `desktop_agent/speech/gemini_live.py` — P3 strings.
5. `desktop_agent.spec` — P4 comment.
6. `CLAUDE.md` — P4 labels (x2).
7. `EPIC-14F-SUMMARY.md` — P4 wording.
8. `src/components/BrowserAgent.tsx` — P5 sandbox + origin/scheme guard.
9. `tests/test_browser_security.py` — 8 new regression tests.
10. `BROWSER_ARCHITECTURE_AUDIT.md` (new) — Phase-1 audit deliverable.
11. `MYRAA_BROWSER_FINAL_REPORT.md` (this file) — Phase-6 deliverable.

## 5. Browser architecture (final)

USER → TEXT/VOICE/VISION → BRAIN → PLAN → VALIDATION → PERMISSION → TOOL
REGISTRY → BROWSER TOOL → WINDOWS DEFAULT BROWSER → SCREEN/OCR → MOUSE/
KEYBOARD (via UC) → VERIFICATION → F7 → MEMORY → RESPONSE. One open authority
(`open_url`), one interact engine (UniversalController), one capture authority
(ScreenShareEngine), one recovery engine (F7). No second anything.

## 6. Default-browser implementation

`open_url(raw) → _normalize_url (scheme allowlist http/https only + host guard +
no embedded creds) → webbrowser.open(url, new=2) → {url, website, application:
"default_browser"}`. `MYRAA_TEST_MODE` guard prevents real opens in tests.
Electron external links → `shell.openExternal`. No auto-open on startup.

## 7. Vision integration

Unchanged and verified: ScreenShareEngine (auto-start) → ContinuousVisionController
(health/stale/change) → UC `get_current_state`/`verify_action` + OCR tools
(`analyzeScreenshot`/`readScreen`). No browser capture loop added.

## 8. UniversalController integration

Unchanged and verified production-ready: container-created, shared via
`STATE.universal_controller`, executes via `registry_dispatch`
(PermissionManager-gated), honest `universal_control_unavailable` /
`target_not_found` refusals, focus-verified close-tab. No second engine.

## 9. Permission flow

Unchanged: ValidationLayer → PermissionManager (category + arg-aware rules +
confirm tokens) → handler → F7 decision attached, on ALL THREE dispatch paths
(CommandDispatcher, registry unified_handler, GeminiToolRouter). Browser
categories: open/click/type/scroll/close/back/forward INTERACT, search READ,
fillform MODIFY. No weakening.

## 10. Security analysis

- URL injection/protocol abuse: blocked (allowlist + prefix guards + tests).
- SSRF: P2 closed; Python/Node now at parity (localhost, 127/8, 10/8,
  172.16/12, 192.168/16, 169.254/16, metadata hosts, ::1, 0.x, no creds).
- Web content = untrusted data: no page→tool path bypasses Brain→Permission;
  P5 sandboxing removes origin-privilege XSS in the dormant viewer.
- Finance firewall, power gating, secrets handling: untouched, verified intact.

## 11. Recovery behavior

Unchanged: F6 taxonomy + F7 `should_retry` attached in both dispatchers;
`desktopBrowser*` → "browser" subsystem accounting; honest ok:false stubs
(FillForm/GoBack/GoForward) are non-retryable terminal guidance, never retried
into success. No new retry engine.

## 12. Tests

- New: 8 regression tests in `tests/test_browser_security.py` (172.16
  boundaries, name-only validation parity, empty rejection).
- Targeted: `test_browser_security + test_browser_universal_integration +
  test_f2_dispatch` = 70 passed; `test_prod_e_universal_control +
  test_phase8_browser_integration + test_phase_d_groww_browser_advisor` =
  54 passed, 1 skipped (pre-existing skip).
- Full: `npm test` 1876/1876 pass; `tsc --noEmit` clean;
  `pytest desktop_agent/tests/` 25/25 pass (re-verified post-change).

## 13. Build

`npm run build` succeeds (vite + esbuild server bundle). `npm run lint` clean.

## 14. Remaining limitations (honest, by design)

DOM selectors, guaranteed tab semantics, FillForm, GoBack/GoForward: explicitly
unsupported, never faked. Voice allowlist exposes open/navigate/search +
screenshot/OCR only (no voice Click/Type/Scroll — deliberate boundary; text
`/execute` path drives them via UC). Scroll anchors at cursor. Proxied
iframe-DOM scripting in the dormant view now fails closed (use UC instead).

## 15. Runtime verification status

Static + test verification complete (above). Live runtime verification
(opening a real browser window, UC click against a live page) was NOT performed:
this environment's harness is non-interactive and opening real windows is a
side effect. Recommended manual check: start-myraa.bat → "open YouTube" →
"YouTube search for Minecraft" → confirm open + voice search; "close tab" with
browser focused/unfocused → confirm verify/refuse.

## 16. Final architecture diagram

See §5 (matches the mandated diagram: TEXT/GEMINI-LIVE → unified context →
MEMORY/VISION/SYSTEM → BRAIN → PLAN → PERMISSION → TOOL REGISTRY →
DESKTOP/BROWSER/FILES → WINDOWS DEFAULT BROWSER → SCREEN/OCR → MOUSE/KEYBOARD
→ VERIFICATION → F7 → MEMORY → TEXT/AUDIO/AVATAR). Rule holds: Windows Default
Browser + existing Vision + existing Mouse/Keyboard + UniversalController.
NO PLAYWRIGHT. NO PUPPETEER. NO SELENIUM. NO CUSTOM BROWSER.

## 17. Exact remaining TODOs

1. Manual runtime check (§15) on a Windows host with the agent running.
2. Optional test-hygiene pass (pre-existing, out of scope): empty
   `desktop/.../analyzers/browser.py`, deferred/skipped legacy test files
   referencing removed symbols, stale `STABILIZATION_BASELINE.md` M6 row
   (claims `STATE.playwright` which no longer exists — historical doc, left
   untouched), generated listings (`git_files*.txt`, `project_tree.txt`).
3. Keep `DESKTOP_TOOL_NAMES`/`DESKTOP_TOOLS`/permissions mapping in sync when
   adding tools (invariant holds today; Node set is defined-but-unused).
