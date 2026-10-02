# MYRAA — Default Windows Browser Architecture Audit (Phase 1, read-only)

Date: 2026-09-19
Status: AUDIT COMPLETE — no code modified in this phase.
Rule enforced: Windows OS default browser ONLY. No Playwright / Puppeteer / Selenium /
Chromium automation / embedded browser / BrowserView / headless browser /
custom browser server / :3001 / local-agent.js.

Existing prior art: `docs/BROWSER_ARCHITECTURE_AUDIT.md` (2026-09-19) already
describes the default-browser design. This file is the Phase-1 re-verification:
every claim below was re-checked against the live repo before writing.

## 1. Current architecture (verified)

```
USER
 ↓
TEXT / VOICE (Gemini Live) / VISION
 ↓
BRAIN (BrainEngine / SuperBrain / intent_router / AIManager route)
 ↓
PLAN (Planner / CapabilityOrchestrator / tool_resolver)
 ↓
VALIDATION (ValidationLayer + TOOL_REQUIRED_ARGS)
 ↓
PERMISSION (PermissionManager + category policy + confirm tokens)
 ↓
TOOL REGISTRY (TOOLS / CommandDispatcher / GeminiToolRouter, F7 recovery attached)
 ↓
BROWSER TOOL
 ├─ open/search  → tools_websites.open_url → webbrowser.open → WINDOWS DEFAULT BROWSER
 └─ interact     → UniversalController → registry.dispatch(mouse/keyboard)
                    → PermissionManager → vision verify
 ↓
SCREEN / OCR / VISION (ScreenShareEngine → ContinuousVisionController)
 ↓
VERIFICATION → F7 RecoveryEngine → MEMORY → RESPONSE
```

Canonical open path (single authority): `desktop_agent/tools_websites.py::open_url`.
Every open/search tool funnels through it:

- `openWebsite` (tools_websites.py)
- `searchWeb / searchYouTube / searchGoogle / searchGitHub` (tools_search.py)
- `desktopBrowserOpen / desktopBrowserNavigate / desktopBrowserOpenTab` (tools_browser.py)
- `desktopBrowserSearch` (tools_browser.py → tools_search.search_web)

In-page interaction (single authority): `UniversalController`
(`desktop_agent/universal_control/universal_controller.py`), container-created in
`core/application_container.py`, shared via `registry.STATE.universal_controller`,
executing through `registry.dispatch` so every UC-driven action passes
ValidationLayer + PermissionManager with F7 recovery attached.

## 2. Browser entry points

| Entry | File | Delegates to | State |
|---|---|---|---|
| openWebsite | tools_websites.py | open_url | ACTIVE |
| searchWeb / searchYouTube / searchGoogle / searchGitHub | tools_search.py | open_url | ACTIVE |
| desktopBrowserOpen / Navigate / OpenTab / Search | tools_browser.py | open_url / search_web | ACTIVE (with B1 validation bug, §6) |
| desktopBrowserCloseTab | tools_browser.py | foreground check + pressKey("ctrl+w") | ACTIVE (focus-verified) |
| desktopBrowserClick / Type / Scroll | tools_browser.py | UniversalController + registry dispatch | ACTIVE when UC present; honest ok:false otherwise |
| desktopBrowserFillForm | tools_browser.py | unsupported stub (ok:false) | EXPLICITLY UNSUPPORTED (honest) |
| desktopBrowserGoBack / GoForward | tools_browser.py | unsupported stubs (ok:false) | EXPLICITLY UNSUPPORTED (honest; unverified-focus hazard) |
| Electron external links | electron/main.cjs | shell.openExternal | ACTIVE (correct: OS default browser) |
| /api/web-proxy, /api/proxy, /api/youtube-search | server/routes/proxy.ts | server-side fetch + isUnsafeUrl guard | ACTIVE endpoint (see B2 latent issue, §6) |
| BrowserAgent.tsx | src/components/BrowserAgent.tsx | iframe + window.open fallback | DORMANT (not in live App chain, see §4) |

## 3. Forbidden-dependency scan (production code)

| Term | Result | Classification |
|---|---|---|
| playwright (package.json) | absent | COMPLIANT |
| playwright (requirements.txt) | absent | COMPLIANT |
| playwright (py source, prod paths) | no imports; only test assertions + stale comments/docs | COMPLIANT (code), STALE DOCS (§7) |
| puppeteer / selenium (package.json, requirements, py/ts source) | absent | COMPLIANT |
| local-agent.js / "local-agent - Copy.js" on disk | `Test-Path` False for both; no glob matches | ABSENT (removed) |
| local-agent / :3001 in prod code | none; only historical comments + generated listings | ABSENT |
| BrowserView / embedded / bundled / headless browser | none in prod code | ABSENT |
| @vitest/browser-playwright (package-lock) | transitive dep of vitest; NOT in package.json; vitest.config uses `environment: "node"`, no browser mode | BUILD ARTIFACT / FALSE POSITIVE |
| electron-to-chromium (package-lock) | transitive via electron; version-mapping lib, not automation | FALSE POSITIVE |
| fastcore tokenizer.json "playwright/selenium/chromium" | model vocabulary tokens, not code | FALSE POSITIVE |
| agent_build/.../warn-desktop_agent.txt "playwright.async_api" | PyInstaller build log artifact | BUILD ARTIFACT |
| git_files.txt / project_tree.txt "local-agent.js" | generated file listings incl. history | STALE ARTIFACT (generated, not live code) |
| shutdown_browser() (tools_browser.py, main.py) | no-op returning None; OS owns the browser | COMPLIANT (correct) |
| start-myraa.bat | starts Python agent :8765 + Node :3000 only; no browser server/Chromium | COMPLIANT |

## 4. Dormant / dead paths (classified, NOT deleted in Phase 1)

- D1 — `src/components/BrowserAgent.tsx`: NOT imported by any live component
  (only ref is `src/design/screens/index.ts` component registry, status "mapped").
  Dormant UI. Contains an unsandboxed `<iframe>` rendering `/api/web-proxy`
  HTML, a `message` listener accepting `{type:"NAVIGATE"}` with NO
  `event.origin` check, and same-origin DOM scripting (`querySelector` click /
  type) in its `actionTrigger` handler. Dormant, so not exploitable through the
  live app chain today — but the pattern is exactly the "fake DOM automation
  layer" this architecture forbids, and the backing `/api/web-proxy` endpoint
  IS live. See B2 (§6). Recommendation: harden or strip in a follow-up with
  explicit approval (NOT done in Phase 1).
- D2 — `server.ts` `DESKTOP_TOOLS` set: defined, never referenced anywhere else
  in TS (verified by grep). Dead allowlist; real gating is Python-side
  (PermissionManager + GeminiToolRouter allowlist). Browser entries inside it
  match `DESKTOP_TOOL_NAMES`, so the sync invariant holds today by inspection.
  Recommendation: leave as-is or cover with a sync test; do NOT wire it into a
  second enforcement path (would create two authorities).
- D3 — `desktop_agent/desktop/vision/analyzers/browser.py`: 0-byte module.
  Empty placeholder, never imported by the vision pipeline. Harmless; candidate
  for removal in a test-hygiene pass, not a browser fix.

## 5. Wiring verification (all checked, no changes made)

- Registry: all 11 `desktopBrowser*` tools registered in `TOOLS` and listed in
  `DESKTOP_TOOL_NAMES`; Node `DESKTOP_TOOLS` lists the same 11. In sync.
- Permissions: all browser tools categorized (open/click/type/scroll/close/back/
  forward = INTERACT, search = READ, fillform = MODIFY). Search/open default
  policy = allow; sensitive ops (typing creds, submitting, purchasing) escalate
  through existing confirm/deny policy — no browser bypass exists.
- Validation: `CommandDispatcher._dispatch_inner`, registry `unified_handler`,
  and `GeminiToolRouter.execute` ALL call `ValidationLayer.validate` — one
  schema/required-args authority, no bypass. (This is also where B1 bites, §6.)
- UC wiring: `ApplicationContainer` creates ONE `UniversalController
  (vision_controller=continuous_vision, tool_executor=registry_dispatch)` and
  assigns `STATE.universal_controller`. tools_browser consumes via `_uc()` and
  degrades to structured `universal_control_unavailable` when absent. No second
  automation engine exists.
- Vision: `ScreenShareEngine` is the single capture authority;
  `ContinuousVisionController` consumes it (stale detection, no duplicate
  capture loop); UC consumes `get_current_state()` / `verify_action()`. No
  browser-specific capture loop exists.
- F7: both dispatch paths attach `recovery_engine.should_retry` decisions;
  `failure_containment._subsystem_for` maps `desktopBrowser*` → "browser"
  subsystem. No duplicate retry engine. Non-retryable errors are not retried
  (authoritative `should_retry` decision).
- Brain: `intent_router` maps open/search/back/forward/close/scroll patterns;
  `tool_resolver` maps `browser_tool` → the 11 registered tools (never a
  canonical id leaking to the dispatcher — locked by test_phase8); Gemini voice
  allowlist exposes ONLY open/navigate/search + screenshot/OCR (click/type/
  scroll/close NOT voice-reachable — deliberate limitation, see G1 §8).
- Tests: `npm test` 1876/1876 pass; `tsc --noEmit` clean; `npm run build`
  succeeds; `pytest desktop_agent/tests/` 25/25 pass;
  `test_browser_security.py` + `test_browser_universal_integration.py` cover
  guards, UC behavior, focus-gated close-tab, honest unsupported actions,
  no-playwright import.

## 6. Genuine bugs found (behavior-verified, NOT fixed in Phase 1)

- B1 (validation rejects valid calls): `TOOL_REQUIRED_ARGS["desktopBrowserOpen"]
  = ["url"]` and `["desktopBrowserNavigate"] = ["url"]`, with NO
  `OR_REQUIRED_ARGS` entry — but both handlers accept `{"name": <site>}`.
  Reproduced: `ValidationLayer.validate({"name":"youtube"}, None,
  tool_name="desktopBrowserOpen")` raises `ToolError: missing required
  argument(s): url`. So `desktopBrowserOpen({"name":"youtube"})` works when
  called as a raw handler (as unit tests do) but is REJECTED on every real
  path (POST /execute, unified registry dispatch, Gemini voice). `openWebsite`
  does not have this bug (has OR entry). Fix: add both tools to
  `OR_REQUIRED_ARGS` with `["name", "url"]`.
- B2 (latent XSS-via-proxy): `/api/web-proxy` reflects upstream HTML into
  MYRAA's own origin with only an interceptor script added — no script
  neutralization, no sandbox — and the (dormant) BrowserAgent renders it in an
  iframe WITHOUT a `sandbox` attribute while its `message` handler accepts
  `NAVIGATE` from any origin. Dormant UI = not exploitable via the live chain
  today, but the endpoint is live and the pattern is unsafe. Fix (follow-up):
  `sandbox` the iframe (without `allow-same-origin`) and/or check
  `event.origin`; do NOT extend the in-iframe DOM scripting.
- B3 (SSRF parity gap): Python `_validate_browser_url` blocks
  localhost/127./10./192.168./169.254./metadata/0./::1 but NOT the
  172.16.0.0/12 private range, while Node `isUnsafeUrl` DOES block
  172.16–31. So `open_url("http://172.16.x.y/")` passes the Python guard.
  Fix: add 172.16–31 matching to the Python validator + tests.

## 7. Stale / misleading references (documentation only — behavior unaffected)

All DOCUMENTATION class; no runtime effect; all need rewording to the
default-browser architecture:

1. `CLAUDE.md:162` — table row label `Browser (Playwright)`.
2. `CLAUDE.md:275` — `BrowserAgent` described with "Playwright-local status".
3. `desktop_agent/tools_search.py:4-5` — "separate from the Playwright automation browser".
4. `desktop_agent/tools_websites.py:6` — "independent of the Playwright automation browser…".
5. `desktop_agent/config/permissions.py:122` — "browser automation (Playwright — desktop-owned…)".
6. `desktop_agent.spec:13-15` — "its ~300MB Chromium is only used by the optional desktopBrowser* tools, whose imports are lazy" — FALSE: tools_browser has zero Playwright/Chromium imports (verified). Keep the `excludes=["playwright"]` hardening; fix the comment.
7. `desktop_agent/speech/gemini_live.py:168,170` — model-facing descriptions "Open URL in MYRAA browser" / "Navigate MYRAA browser" — there is no MYRAA browser; must say "Windows default browser". Also `desktopBrowserNavigate` decl lacks the `name` prop its handler accepts.
8. `EPIC-14F-SUMMARY.md:92` — "browser automation via Playwright" (historical doc).
9. `tools_websites._normalize_url` correctly blocks `ftp:` via scheme allowlist, but `_ALWAYS_BLOCKED_PREFIXES` omits it while tests expect ftp rejection — works today via the allowlist fallthrough; consider adding `ftp:` to the prefix tuple for clarity (optional, test-covered either way).

## 8. Integration gaps / honest limitations (not bugs — do not "fix" by faking)

- G1: Gemini voice allowlist omits Click/Type/Scroll/CloseTab/OpenTab — voice
  multi-step in-page interaction is unavailable; open/search only. Text
  `/execute` path CAN drive them via UC. Deliberate safety boundary; document,
  don't bypass.
- G2: `intent_router` routes "go back/forward" phrases to the honestly-
  unsupported stubs → guaranteed polite failure. Acceptable (honest, guided);
  alternative is router-level guidance. No change proposed in Phase 3.
- G3: `desktopBrowserOpenTab` cannot guarantee tab-vs-window semantics through
  `webbrowser.open` — handler already says so honestly. No change.
- Web content is DATA: no path from page/OCR text to tool execution bypasses
  Brain → Plan → PermissionManager → Tool. No prompt-injection bypass found in
  the browser path. (Systemic trust-boundary labelling remains a cross-cutting
  roadmap item.)

## 9. Phase 2 — precise change list (approval requested, NOT applied)

| # | FILE | CURRENT PROBLEM | PROPOSED CHANGE | WHY | RISK | TEST |
|---|---|---|---|---|---|---|
| 1 | desktop_agent/config/permissions.py | B1: desktopBrowserOpen/Navigate reject valid `{"name"}` calls at ValidationLayer | TOOL_REQUIRED_ARGS both → `["name","url"]`; OR_REQUIRED_ARGS add both → `["name","url"]` | Handler + Gemini decl + tests all accept name; gate must match handler | LOW (widens accepted args to documented behavior) | new pytest: name-only passes ValidationLayer + dispatch; full pytest + npm test |
| 2 | desktop_agent/tools_websites.py | B3: 172.16/12 private range not blocked | add 172.16–31 host check in `_validate_browser_url` | SSRF parity with proxy.ts `isUnsafeUrl` | LOW | extend test_internal_hosts_rejected (172.16/172.31) |
| 3 | desktop_agent/speech/gemini_live.py | B3-docs: "MYRAA browser" misleads model; Navigate lacks `name` prop | descriptions → "Windows default browser"; add `"name"` prop to desktopBrowserNavigate | Stop model believing MYRAA owns a browser; match handler | VERY LOW (strings) | decl smoke test + super-brain suite |
| 4 | 6 stale-ref files (§7 items 1–6,8) | Say "Playwright automation browser" / wrong labels | reword to default-browser architecture; keep `excludes=["playwright"]` | Misleading docs contradict enforced architecture | NONE (comments/docs) | repeat forbidden-term grep scan |
| 5 | src/components/BrowserAgent.tsx + server/routes/proxy.ts | B2 latent: unsandboxed proxied HTML, origin-unchecked postMessage | DEFERRED: sandbox iframe + origin check (dormant UI) — needs explicit approval, behavior change to dormant component | Do not touch UI without approval; endpoint stays SSRF-guarded | MEDIUM (dormant behavior) | manual + grep; NOT in Phase 3 |

Out of scope (protected): PermissionManager, F6 taxonomy, F7 RecoveryEngine,
finance firewall, FastCore, memory atomicity, Gemini Live transport, vision
pipeline, tool registry shape. None touched.

## 10. Acceptance status (Phase 1)

[checked] Playwright absent (prod) · [checked] Puppeteer absent ·
[checked] Selenium absent · [checked] Chromium automation absent ·
[checked] Embedded browser absent · [checked] :3001 absent ·
[checked] local-agent.js absent (disk) · [checked] One browser architecture
(webbrowser.open → OS default) · [checked] Open capability in registry ·
[checked] Brain can invoke browser tools (text path; voice limited to open/search
by allowlist) · [checked] PermissionManager enforced on all paths ·
[checked] Web content treated as untrusted data · [checked] Vision observes
browser window · [checked] OCR reads browser · [checked] Mouse/keyboard act via
UC where supported · [checked] Actions verified, F7 attached, no duplicate
engines · [checked] UI has no installer/server-status/fake-state (BrowserAgent
dormant) · [checked] Tests + tsc + build green.
TO FIX (Phase 3, pending approval): B1 validation, B3 SSRF parity, B3-docs
model strings, §7 stale wording. DEFERRED: B2 dormant-UI hardening.
