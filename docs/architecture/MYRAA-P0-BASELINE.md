# MYRAA P0 Foundation Hardening — Baseline Report (F0)

**Date:** 2026-08-18
**Author:** P0 Foundation Hardening session
**Repository:** `C:\Users\singh\OneDrive\Desktop\MYRAA` (git repo, branch `main`)

---

## 1. Repository State

| Item | Value |
|---|---|
| Branch | `main` (tracks `origin/main`) |
| Commits | `121bc7f` "Initial commit" (single commit) |
| Uncommitted changes | ~70 files modified, ~120 files untracked |
| Working tree | Large in-progress dev state (AI Manager 3.1, EPIC-14G perf infra, power-action safety) |

The repository has a single initial commit; essentially the entire current system is
uncommitted working-tree state. This is the state that F0–F10 must operate on.

---

## 2. Project Structure (relevant to P0)

```
server.ts                    # Node/Express + WS /live (Gemini Live bridge) — heavily modified
server_memory.ts             # Memory load/save (saveMemories write currently disabled)
services/desktop/desktop_agent.ts  # callDesktopAgent → POST /execute (real bridge)
desktop_agent/main.py        # FastAPI :8765 + CommandDispatcher
desktop_agent/registry.py    # TOOLS registry + PermissionManager
desktop_agent/config/permissions.py  # TOOL_CATEGORIES / risk classes / overrides
desktop_agent/tools_pc.py    # Power actions (test-mode + MYRAA_ALLOW_POWER_ACTIONS guards)
desktop_agent/tools_confirmation.py  # DANGEROUS_ACTIONS + single-use token flow
desktop_agent/brain/ai/ai_manager.py # AIManager semantic routing (3.1)
desktop_agent/brain/ai/provider.py   # AIProvider ABC
desktop_agent/brain/ai/providers/    # gemini / ollama / nim providers
desktop_agent/brain/brain_engine.py  # BrainEngine cognitive pipeline
desktop_agent/brain/execution_brain.py
desktop_agent/brain/error_taxonomy.py       # untracked — error categories (partial)
desktop_agent/brain/failure_containment.py  # untracked — failure classification
desktop_agent/brain/latency_tracing.py      # untracked
desktop_agent/brain/metrics.py              # untracked
desktop_agent/brain/memory/persistence.py   # untracked — memory persistence
desktop_agent/brain/performance_guard.py    # untracked
conftest.py                  # root pytest config: MYRAA_TEST_MODE + global power guard
pytest.ini                   # testpaths = tests, desktop_agent/brain
tests/                       # pytest suite (desktop tools, safety, permissions, parsers)
test_ai_manager.py, test_ai_manager_3.py, test_brain_engine.py, ...  # ad-hoc scripts
validation_benchmark/        # AI Manager 3.0 benchmark (104 held-out)
AI_MANAGER_3_1_BASELINE.json # recorded 40/40 smoke + benchmark metrics
```

---

## 3. Baseline Test Results

### 3.1 Full pytest suite

| Metric | Result |
|---|---|
| Collected | 183 |
| Passed | **175** |
| Errors | **8** (all `PermissionError: [WinError 5] Access is denied` on `C:\Users\singh\AppData\Local\Temp\pytest-of-singh`) |
| Failures | 0 |
| Warnings | 99 (deprecation warnings only) |

The 8 errors are **pre-existing, environmental** — parser/indexer tests
(`test_python_parser`, `test_typescript_parser`, `test_javascript_parser`,
`test_symbol_indexer`, `test_module_indexer`, `test_module_database`,
`test_module_analysis`, `test_workspace_detector`) require pytest temp-dir
fixtures that fail under the OneDrive profile permissions. Not caused by any P0
change.

### 3.2 AI Manager 40/40 smoke suite

| Metric | Recorded baseline (AI_MANAGER_3_1_BASELINE.json) | Actual current run |
|---|---|---|
| Smoke tests | 40/40 PASS (claimed) | **10/40 PASS** (`test_ai_manager_3.py`) |
| Intent accuracy (held-out, 104) | 0.779 | n/a (not re-run) |
| Unsafe routing rate | 0.0 | n/a |
| Average latency | 0.47 ms | n/a |

**DISCREPANCY:** The recorded "40/40" smoke suite does **not** currently pass.
`test_ai_manager_3.py` reports 10/40. The `test_ai_manager_3.py` file expects
intents like `greeting`, `app_control`, `simple_question`, `explanation`,
`trading_analysis`, etc. that the current `AIManager` no longer produces. This is a
**pre-existing regression** relative to the recorded baseline and must be resolved
during F10 (integration validation) — but the P0 constraint is "40/40 must remain
PASS", so this needs attention.

### 3.3 Ad-hoc root test scripts

| Script | Result |
|---|---|
| `test_ai_manager.py` | 1 failed — `AttributeError: 'AIManager' object has no attribute '_determine_complexity_hints'` (pre-existing) |
| `test_ai_manager_3.py` | 10/40 (pre-existing, see 3.2) |
| `test_brain_engine.py` | PASS |
| `test_execution_brain.py` | PASS |
| `test_route.py` | PASS |
| `test_domain.py` | PASS |
| `test_context_manager.py` | PASS |
| `test_epic14g_fast_path.py` | PASS |
| `test_comprehensive.py` | collection error (references removed `_determine_complexity_hints`) |
| `test_simple.py` | collection error (same cause) |
| `desktop_agent/tests/`, `desktop_agent/brain/planner/execution/tests/` | "no tests ran" (ad-hoc print-scripts, not pytest-collected) |

---

## 4. Known Current Failures (recorded, not hidden)

1. **Parser/indexer pytest errors (8)** — environmental temp-dir `PermissionError`.
   Pre-existing. Not touched by P0 (will re-verify at end; if still failing, report
   as PRE-EXISTING).
2. **`AIManager._determine_complexity_hints` missing** — breaks `test_ai_manager.py`,
   `test_comprehensive.py`, `test_simple.py` collection. The AI Manager routing
   internals were rewritten (3.1) but these scripts were not updated. Pre-existing.
3. **AI Manager 40/40 smoke = 10/40** — intent mapping drift between `test_ai_manager_3.py`
   expectations and current `AIManager` output. Pre-existing vs recorded baseline.
4. **Memory persistence disabled** — `server_memory.ts` `saveMemories()` has the
   `fs.writeFile` call commented out (target of F1).
5. **`services/ai` and `services/voice`** are empty scaffolding.
6. **Unsafe-routing / latency metrics** are recorded from `validation_benchmark` but
   were not re-derived this session (no route changes made during F0).

---

## 5. Metrics & Performance Baseline (recorded)

From `AI_MANAGER_3_1_BASELINE.json` and `validation_benchmark/validation_report.md`
(AI Manager 3.0, 104 held-out cases):

| Metric | Value |
|---|---|
| Intent accuracy | 0.779 |
| Domain accuracy | 0.625 |
| Execution mode accuracy | 0.298 |
| Reasoning depth accuracy | 0.423 |
| Freshness accuracy | 0.644 |
| Risk level accuracy | 0.356 |
| Tools-required accuracy | 0.750 |
| Language accuracy | 1.000 |
| Complexity accuracy | 0.904 |
| Unsafe routing rate | 0.0 |
| Average latency | 0.47 ms |
| P95 latency | 0.81 ms |
| P99 latency | 1.13 ms |
| Average confidence | 0.810 |
| Fast-path usage | 33.7% |

---

## 6. Safety State (power actions)

Already hardened prior to P0:
- `desktop_agent/tools_pc.py` `_run_power`: `MYRAA_TEST_MODE` guard + explicit
  `MYRAA_ALLOW_POWER_ACTIONS=1` opt-in gate before any real OS power command.
- `conftest.py`: autouse `MYRAA_TEST_MODE=true` + session-wide subprocess/os.system
  power-command backstop (`_POWER_CALLS`).
- `tests/test_power_action_guard.py`, `tests/test_tools_pc_safety_guard.py`,
  `tests/test_no_real_power_command.py`: power safety coverage.
- Targeted safety run at baseline: **60 passed** (power + permissions + dispatch).
- Global backstop `test_no_real_power_command_was_attempted` confirms **no real
  power command has ever been executed during tests**.

---

## 7. P0 Acceptance Baseline Note

No code changes were made during F0. This document records the trustworthy
starting point. Any subsequent P0 phase that changes behavior must not regress the
175 passing tests, and F10 must re-run the full suite and the AI Manager smoke.
