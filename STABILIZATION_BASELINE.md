# MYRAA STABILIZATION — BASELINE + ISSUE MATRIX (2026-08-22)

Source of truth priority: CURRENT CODE > CURRENT TESTS > RUNTIME > CONFIG > DOCS.

## BASELINE TEST NUMBERS

| Suite | Collected | Passed | Failed | Skipped | Collection Errors | Hangs |
|---|---|---|---|---|---|---|
| `desktop_agent/` (full) | 258 | n/a (collection blocked) | n/a | n/a | **10** | no |
| `tests/` (root) | **1367** | n/a | n/a | n/a | 0 | full run not completed (some hit live endpoints) |
| `desktop_agent/desktop/tests/` | 1 | 0 | 0 | 0 | 1 (test_vision) | no |

## ROOT CAUSE OF THE 10 COLLECTION ERRORS

**9 of 10 errors** trace to ONE source:
`desktop_agent/brain/research/test_research_integration.py:19-24` unconditionally
stubs `sys.modules["cv2"]` and `sys.modules["google"]` at import time. This poisons
the global interpreter namespace, so every later `import pyautogui` → `pyscreeze`
fails on `cv2.__version__`. Affected: test_frame_difference, test_hotkeys,
test_image_processor, test_keyboard, test_mouse, test_mouse_bridge, test_screenshot,
test_full_integration, test_super_brain. Both cv2 (5.0.0) and google-genai (2.14.0)
are ACTUALLY installed — the stubs are unnecessary and must be conditional on
ImportError.

**1 error** (test_vision.py) is a genuine contract break: `VisionValidator.__init__`
passes `ocr_backend=` to `VisionPipeline` which no longer accepts it; validator
also calls `pipeline.analyze()` which no longer exists. VisionValidator is legacy
V3 that drifts from the current VisionPipeline(image_processor, ocr_engine, ...)
`.process(frame)` contract. Used only by test_vision.py; VisionManager is the
authoritative runtime (constructs pipeline with ImageProcessor + OCREngine(backend)).

## ISSUE MATRIX

| ID | Sev | Component | Actual Status | Root Cause | Evidence | Fix | Status |
|---|---|---|---|---|---|---|---|
| M1 | HIGH | Test collection (9 modules) | VERIFIED BROKEN | cv2/google sys.modules poisoning in test_research_integration.py | Reproduced: conditional import fixes it | Make stubs conditional on ImportError | TODO |
| M2 | HIGH | VisionValidator/VisionPipeline contract | VERIFIED BROKEN | Legacy validator passes ocr_backend + calls analyze() | vision_validator.py:46 TypeError | Rewrite validator to current VisionPipeline(ImageProcessor, OCREngine(backend)).process(frame) | TODO |
| M3 | HIGH | 8 desktop test scripts | VERIFIED BROKEN (0 items, live actions at import) | Scripts execute desktop actions at module level with no test_* functions | Import moves mouse / opens Notepad | Convert to real pytest tests w/ safe in-memory validation | TODO |
| M4 | MEDIUM | /brain → SuperBrain | VERIFIED (SuperBrain BYPASSED) | main.py:727 BRAIN.run()→BrainEngine; SuperBrain only on /autonomy | main.py:710-797; container.super_brain | Route /brain through SuperBrain; BrainEngine stays as compat | TODO |
| M5 | MEDIUM | NeuralEngine | VERIFIED (CODE EXISTS, NOT WIRED) | Zero NeuralEngine instantiation/ref in container/main/registry | grep: 0 refs | Wire ONE shared NeuralEngine in ApplicationContainer + register specialists + invoke where appropriate | TODO |
| M6 | LOW | Playwright dead state | VERIFIED | registry.py STATE.playwright/reset_playwright; no playwright import anywhere | registry.py:91-107,308-310 | Remove dead state refs | TODO |
| M7 | LOW | Duplicate/stale artifacts | VERIFIED | `- Copy.*` files, stale agent_build/, local-agent - Copy.js | ls root | Clean verified dead artifacts only | TODO |
| M8 | MEDIUM | Documentation | VERIFIED STALE | CLAUDE.md/AGENTS.md claim bridge stubbed, Playwright active, indicators missing | Code contradicts docs | Resync CLAUDE.md + AGENTS.md + architecture docs | TODO |
| M9 | MEDIUM | Memory authority | PARTIAL — verify | UnifiedMemoryManager is injected as single authority; legacy manager.py still has own persistence path | container:88-110 | Verify legacy is view/adapter only; prove one writer in test | TODO |
| M10 | MEDIUM | NIFTY/BANKNIFTY | IMPLEMENTED (enums + analyze_options); runtime unverified | InstrumentType has NIFTY/BANKNIFTY; engine.analyze_options handles | models.py:23-24; engine.py:180-196 | Verify no .NS corruption for indices; document status | TODO |
| M11 | MEDIUM | Groww E2E | CODE EXISTS + WIRED; LIVE E2E UNVERIFIED | Browser-first read-only advisor | browser_advisor.py | Verify read-only invariant; mark LIVE E2E UNAVAILABLE if no auth | TODO |
| M12 | MEDIUM | Self-healing | CODE EXISTS + REAL (detect/diagnose/recover/patch/sandbox/canary/promote/rollback present) | self_healing/ module is substantial | manager.py:apply_improvement→sandbox→promote | Verify scope, add integration test | TODO |
| M13 | LOW | YahooProvider | VERIFIED FIXED (no longer a finding) | Matches MarketQuote contract (high_price/low_price) | yahoo_provider.py:53-64 | none | DONE |
| M14 | MEDIUM | Security (secret sweep) | UNVERIFIED | Not swept this session | — | Run secret sweep w/ redacted evidence | TODO |
| M15 | MEDIUM | Performance | UNMEASURED | No measurements taken | — | Measure p50/p95/p99 | TODO |
| M16 | MEDIUM | Concurrency/shutdown | UNVERIFIED | Long-lived loops/threads | — | Verify clean start/cancel/shutdown | TODO |
| M17 | LOW | utcnow() deprecations | VERIFIED | datetime.utcnow() in working_blackboard.py, main.py | pytest warnings | Fix (safe, non-breaking) | TODO |

## NOTE
YahooProvider contract break, indicators missing, memory-persistence disabled, and
bridge-stubbed claims from the OLD audit are all OUTDATED — current code contradicts
them. Current execution wins.
