# MYRAA AI Manager 4.1 — Implementation Report

> Scope: Phase 29 documentation for the AI Manager 4.0 → 4.1 upgrade.
> Companion file: `MYRAA-AI-MANAGER-4-1-BEFORE-AFTER.md` (Phase 30 report).
> All routing changes live in `desktop_agent/brain/ai/`; no new duplicate systems.

---

## 1. What changed

### 1.1 New modules (`desktop_agent/brain/ai/`)

| Module | Responsibility |
|---|---|
| `context_snapshot.py` | Bounded conversation context (`ContextSnapshot`) + `detect_reference_mention` (deictic pronoun / definite-noun-phrase reference detection). |
| `calibration.py` | Platt-scaled confidence calibration (`platt_fit` / `platt_transform`) + calibration metrics (`brier_score`, `expected_calibration_error`, `accuracy_by_bucket`, `false_high_confidence_rate`, `false_low_confidence_rate`). |
| `feedback.py` | `RoutingFeedback` + `FeedbackStore` — persisted routing-feedback record (`record_feedback`). |
| `tool_resolver.py` | Canonical tool-id → registered desktop tool resolution (`resolve` / `is_resolvable`), the single mapping between AI Manager tool requirements and the real `registry.TOOLS`. |

`__init__.py` now exports: `AIManager`, `ContextSnapshot`, `ReferenceKind`,
`detect_reference_mention`, `FeedbackStore`, `RoutingFeedback`,
`resolve as resolve_tools`, `is_resolvable`.

### 1.2 `ai_manager.py` 4.1 additions

- **`ExecutionMode.MULTI_STAGE_WORKFLOW`** added (end of enum) for decomposed requests.
- **Hinglish normalization** (`_normalize_hinglish`): bounded phrase rules
  (`X ka analysis do/chahiye`, `X ko check karo`, `X aur Y me kya difference hai`,
  `report tayyar karo`, `analysis chahiye`, `summary karo`, …). Normalization is
  used **only** for signal extraction; the original prompt is preserved on the route.
- **Reference/context fusion**:
  - `_build_context_snapshot` — caller snapshot, else a minimal snapshot derived
    from recent route history (bounded, no unbounded memory).
  - `_resolve_reference` — resolves OPEN / SAME_AS_BEFORE / CONTINUE_PREVIOUS /
    REPEAT / IMPROVE_PREVIOUS / WORST_PERFORMER references, or returns a targeted
    Hinglish clarification question when context is insufficient.
  - Reference resolution runs **before** the fast-path check so `open that`,
    `same as before`, `continue` route to the resolved target.
  - Window/tab management verbs (`close/maximize/minimize/restore/switch/focus`)
    with `the window`/`the tab` are treated as actionable, **not** references
    (fixes `maximize the window` false positive). `read my file` is no longer an
    open-reference.
- **Multi-intent decomposition** (`_decompose_multi_intent`): splits on
  `and then|and|also|plus|to|so that|,|;|&`, detects temporal dependencies from
  the **original** text (`and then|then|so that`), routes each clause
  domain-first then intent-within-domain, and produces a `DecompositionResult`
  (`ClauseGoal` list + `capability_chain` + `dependencies`). The route reports
  `is_multi=True`, `sub_tasks`, `dependencies`, `capability_chain`.
- **Confidence calibration**: `_load_calibration_params` loads the fitted
  `calibration_params.json` (fallback a=1.0/b=0.0); `_apply_calibration` applies
  the Platt transform; `_apply_confidence_calibration` folds agreement margins
  (competing domains/intents, weak capability) into the route score before
  calibration and applies the **4.1 decision policy**.
- **4.1 decision policy** (structural, advisory only):
  - near-zero-information inputs (`x`, …) → **ABSTAIN**
  - deictic-only inputs without context (`do the thing`, `handle it`, …) → **CLARIFY**
  - `reference_resolved` → **ROUTE**
  - competing intents + competing domains → **CLARIFY**
  - calibrated ≥ 0.6 → **ROUTE**; multi-intent with calibrated < 0.3 → **CLARIFY**
  - else → **ROUTE** (best-guess path; calibration never blocks routing)
  - CLARIFY sets a Hinglish `clarification_question` on the route.
- **Evidence-based routing overrides** (`_apply_routing_overrides`): bounded
  heuristics for known false-positives — app open/close/launch + known app →
  APP_CONTROL/COMPUTER; `shares/stock + buy/sell/invest` → TRADING; `search …
  web/browser/google/internet` → SEARCH_WEB/RESEARCH; `when did/was`, `what time`
  → TIME_QUERY; `latest/recent/new` questions → RESEARCHING.
- **Question detection**: `signals.is_question` is now actually computed
  (wh-word / auxiliary at start) — this enables the pre-existing
  `_QUESTION_SUPPRESS_INTENTS` gate (pure-imperative tool intents are suppressed
  for interrogatives, e.g. `what is the speed of light` no longer routes to
  SYSTEM_PERFORMANCE).
- **Intent-aware output type** (`_classify_output_type(…, intent=…)`): research →
  RESEARCH_REPORT, trading decision → RECOMMENDATION, trading analysis →
  MARKET_ANALYSIS, coding → CODE, document/presentation/spreadsheet → respective
  types, desktop actions → SYSTEM_ACTION, greetings/affirmation → TEXT.
- **Intent-aware reasoning depth** (`_derive_reasoning_depth`): desktop/action
  intents → MINIMAL; code debug/fix → BASIC; code build/creation → MODERATE;
  trading analysis/decision + research → HIGH; trading monitoring → MODERATE.
- **Research config** (`_derive_research_config`): RECENT/REAL_TIME/LIVE or
  RESEARCH_PIPELINE or RESEARCHING/INVESTIGATING → research metadata
  (pipeline, freshness tier, primary query, search terms, fallback order,
  verify). Routing metadata only; `ResearchRouter` remains the canonical consumer.
- **Escalation tier** (`_determine_escalation_tier`): research_pipeline /
  trading_advisory / nim_deep_reasoning / system_diagnostics.
- **Feedback**: `record_feedback(request_id, expected, outcome, correct)` writes
  to the `FeedbackStore`.
- **TaskRoute** is a full 4.1 container: `primary_intent`, `secondary_intents`,
  `sub_tasks`, `dependencies`, `capability_chain`, `alternative_routes`,
  `confidence_reason`, `uncertainty_flags`, `modality`, `research_config`,
  `request_id`, `escalation_tier`, `context_used`, `is_multi`, `summary_dict()`.
  Route `request_id` = `uuid4().hex[:12]`.
- **`route()` signature**: `route(user_prompt, system_prompt="", task=None, context=None)`.
  Existing callers use keyword args (verified compatible).

### 1.3 Compatibility fixes applied

- Removed non-existent enum members: `Freshness.CURRENT` → RECENT/REAL_TIME/LIVE.
- Removed `OutputType.STEP_BY_STEP`/`TUTORIAL` references → REPORT/PLAN/RESEARCH_REPORT.
- `ExecutionMode['COMPUTER_USE']` (capability id) → mapped to `FAST_DETERMINISTIC`.
- Fixed `_preference_for` signature, `DomainCandidate.score` → `.confidence`,
  corrupted `continueopen` fast token, TaskRoute kwargs container.
- Fixed the latent `reference_resolved` bug: `reference_kind` value `'none'` was
  truthy and bypassed the `!= 'NONE'` check, wrongly routing every
  low-information request as resolved.

---

## 2. Benchmark & evaluation

### 2.1 Dataset (`validation_benchmark/generate_ai_manager_41.py`)

- **505 unique items**: `ai_manager_41_development.json` (303), `_validation.json`
  (101), `_held_out.json` (101), `_full.json` (505).
- Categories: COMPUTER_USE 124, TRADING 73, CODING 64, GENERAL 51, CREATION 45,
  RESEARCH 35, EDUCATION 27, VISION 20, HINGLISH 12, MULTI_INTENT 10,
  CONTEXTUAL 10, AMBIGUOUS 4, ADVERSARIAL 4, NX 4.
- Languages: ENGLISH 400 / HINGLISH 105. Complexity: simple 321, complex 89,
  current_live 67, multi_intent 10, adversarial 4, ambiguous 4, contextual 10.

### 2.2 Evaluator (`validation_benchmark/evaluate_ai_manager_41.py`)

- Fits Platt calibration **on the development split only** (a=0.961, b=0.799,
  n=303) → writes `desktop_agent/brain/ai/calibration_params.json`.
- Reports held-out-only metrics → `ai_manager_41_evaluation_results.json` +
  `ai_manager_41_report.md`.
- Tool-hit compares resolved **real** registered tool names (via `tool_resolver`)
  so canonical ids in the dataset match actual requirements.

### 2.3 Held-out results (101 items)

| Dimension | Accuracy |
|---|---|
| Intent | 81.19 |
| Domain | 78.22 |
| Capability | 86.14 |
| Output type | 71.29 |
| Execution mode | 84.16 |
| Reasoning depth | 79.21 |
| Freshness | 88.12 |
| Risk level | 90.10 |
| Tool requirement hit | 82.67 |
| Decision (CLARIFY/ABSTAIN) | 100.00 |
| Multi-intent route correctness | 99.01 |
| Reference resolution | 100.00 |
| Hinglish intent / domain | 93.75 / 81.25 |

Calibration (held-out): Brier raw **0.329** → calibrated **0.147**;
ECE raw **0.408** → calibrated **0.049**; false-high (≥0.8) 0.097;
false-low (<0.3) 0.0; decision accuracy (calibrated ≥0.5) **0.812**.
Latency: p50 **1.45 ms**, p95 **4.54 ms**, p99 **7.03 ms**.

### 2.4 Safety

- `unsafe_routing = 0` on both the 4.1 held-out set and the legacy 104-item
  benchmark. All routing remains advisory; no execution path changed.
- Adversarial/ambiguous held-out items: `x` → ABSTAIN; `do the thing` / `handle it`
  / `you know what to do` → CLARIFY with a Hinglish question; `ignore … shut down`
  → routed (permission/safety layer remains the execution gate).

---

## 3. What was NOT changed

- `provider.py`, `providers/*`, `router/*`, `brain_engine.py`, `execution_brain.py`,
  `research/*`, `registry.py`, `tools_*.py`, `PermissionManager` — untouched.
- No new dispatcher, no new brain pipeline, no new HTTP client, no autonomous
  financial execution.

## 4. Regression status

- P0 gate (`tests/test_f4_llm.py`, `tests/test_ai_manager_nim.py`,
  `tests/test_ai_manager_nim_streaming.py`): **18 passed**.
- Full `tests/` suite: **257 passed** (8 errors are pre-existing OneDrive
  `PermissionError` on tmp-path creation in parser/database tests — environmental).
- Legacy `validation_benchmark/evaluate_benchmark.py` (104 items): intent 0.731,
  domain 0.731, exec-mode 0.481, reasoning 0.481, freshness 0.933, risk 0.971,
  tools 0.875, unsafe 0. The legacy intent number is suppressed by two evaluator
  artifacts: (a) `explanation`/`simple_question` labels fall back to
  GENERAL_REQUEST in `convert_string_to_enum`; (b) legacy items labeled
  `creation_document` include presentations/websites that the 4.1 router now
  classifies precisely (CREATION_PRESENTATION / CREATION_CODE).