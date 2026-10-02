# MYRAA AI Manager 4.0 — FIRST REPORT (Analyze-First)

> Status: ANALYSIS COMPLETE — no routing code modified yet.
> Author: Codex session (AI Manager 4.0 directive)
> Date: 2026-08-18

---

## 1. Existing AI Manager Architecture

**Single authoritative router:** `desktop_agent/brain/ai/ai_manager.py` (2550 lines)
`AIManager` is the composition root for all routing. The deprecated
`desktop_agent/brain/ai/router/` package (EPIC-03) explicitly defers to
`AIManager.route()`; nothing imports it for routing.

**Enums (all in `ai_manager.py`):**

| Enum | Line | Members |
|---|---|---|
| `Intent` | 13 | **74 members**, 4 duplicated declarations of `IntentCandidate` (lines 196/208) |
| `Domain` | 90 | 17 members (`TRADING_FINANCE` duplicates `TRADING`) |
| `ExecutionMode` | 110 | 11 members |
| `ReasoningDepth` | 124 | 5 members |
| `Freshness` | 132 | 3 members (STATIC/RECENT/REAL_TIME) |
| `RiskLevel` | 138 | 5 members |
| `Modality` | 146 | 7 members |
| `Language` | 156 | ENGLISH/HINGLISH |

**Data structures:** `TaskSignals` (entities/topic/object/action/requested_output/
modality/context/tool_hints/freshness/language), `DomainCandidate` (rich
component evidence), `IntentCandidate` (pattern_score + confidence only),
`TaskRoute` (12 fields, defined at the bottom of the file).

**Providers:** `PROVIDER_ORDER = ("nim","gemini","ollama")`; lazy `_by_name`;
`_PREFERENCES` maps 5 hint categories → ordered provider names;
`resolve_provider`/`generate`/`stream_generate` all call `route()` to obtain
`provider_preference`. `Capability` (inner class) registry has 12 capabilities.

**Consumers that must remain compatible:**
- `execution_brain.py:1144` reads `route.can_use_fast_path`
- `brain_engine.py:597` `self.ai.resolve_provider(...)`
- `semantic/providers/provider_factory.py` + `ollama_provider.py` → `ai.resolve_provider`/`ai.generate`
- `research/synthesizer.py` → `_PREFERENCES`, `_by_name`
- `tests/test_f4_llm.py`, `tests/test_ai_manager_nim*.py` → `generate`/`stream_generate`/`resolve_provider`
  (with monkeypatched `_preference_for` and `_providers`)
- `tests/test_f10_e2e.py` → monkeypatches `AIManager.resolve_provider`

## 2. Current Routing Flow (`route()`)

```
user_prompt + system_prompt
  → context dict
  → _extract_task_signals(combined_text)      # entities, action, topic(=object), output, modality, freshness, language, tool_hints
  → _detect_domain_candidates(signals)        # 10 weighted component scores; NOTE arbitrary ×1.5 bonus for non-GENERAL
  → best domain (max confidence; fallback GENERAL if empty)
  → _detect_intent(text, domain, domain_conf) # pattern-only scores + ×2.0 domain boost
  → _get_route_spec(domain, intent)           # (domain,intent) dict; falls back to (GENERAL,intent), then a default
  → confidence = 0.4*domain_conf + 0.6*intent_conf, ×1.1 if >3 words, + 0.5*spec.confidence_boost, capped 1.0
  → TaskRoute(...)                            # execution_mode/reasoning/freshness/risk/provider_pref from spec
  → _apply_confidence_calibration(...)        # NO-OP (returns route unchanged)
```

**Dead/missing code confirmed:**
- `_apply_fast_deterministic_check` is implemented (line 2396) but **never called**
  from `route()`.
- `_apply_confidence_calibration` (line 2387) is a **no-op**.
- `_determine_complexity_hints` / `_complex_keywords` / `_simple_keywords` **no
  longer exist** — `test_ai_manager.py` (root) and `test_execution_brain.py`
  reference them → `AttributeError`.
- `time` and `collections.defaultdict` are imported but unused.
- `IntentCandidate` is declared **twice** (identical, lines 196 and 208).
- `DomainCandidate` has 10 evidence fields, but `_detect_domain_candidates`
  never sets `semantic_score`, `context_fit`, or `tool_fit`, and `action_fit`/
  `topic_fit`/`object_fit`/`output_fit` are computed as `matched/len(vocab)` —
  tiny vocabularies make these scores minuscule (e.g. `Domain.VISION` topic
  vocab 10, matched 1 → 0.1).

## 3. Current Enum Model

The `Intent` enum mixes **three different dimensions** into one namespace:
1. **System/desktop verbs** (APP_CONTROL, FILE_OPEN, AUDIO_PLAY, SYSTEM_SLEEP…)
2. **Topic/output nouns** (CREATION_DOCUMENT, CREATION_PRESENTATION…)
3. **Conversational actions** (GENERAL_REQUEST, GREETING, TIME_QUERY…)

There is **no** canonical conversational intent for the most common natural
language asks: `simple_question`, `explanation`, `analysis`, `comparison`,
`why_question`, `calculation`, `equation`, `formula`, `relationship`,
`architecture`, `framework`, `strategies`, `approaches` — these labels were
removed from the enum (EPIC-14C) but **still exist as gold labels** in
`test_ai_manager_3.py` and the `validation_benchmark` datasets. Consequently:
- `evaluate_benchmark.py`'s `convert_string_to_enum("simple_question", Intent)`
  throws → silently falls back to the **first enum member** (`GENERAL_REQUEST`),
  deflating intent accuracy on exactly those cases.
- The 40-case smoke suite can only pass 10/40 for the same reason
  (previously documented in `MYRAA-P0-COMPLETION-REPORT.md` as pre-existing).

Separate namespace (`desktop_agent/brain/semantic/semantic_models.py`) defines a
**different** `Intent` (str enum: UNKNOWN/CHAT/QUESTION/OPEN_APPLICATION/…).
This is the semantic-parser's intent space, consumed by `ResponseRouter` and the
knowledge resolver. It must not be merged or deleted; it is out of scope except
where `BrainEngine` bridges to `AIManager`.

## 4. Current Capability Model

`_initialize_capability_registry()` builds 12 capabilities keyed by id:
TRADING_ENGINE, NX_ENGINEERING_ENGINE, RESEARCH_PIPELINE, CODING_ENGINE,
CREATION_ENGINE, SYSTEM_DIAGNOSTICS, COMPUTER_USE, PHONE_ENGINE, VISION_ENGINE,
VOICE_ENGINE, SYSTEM_ENGINE, FILES_ENGINE, GENERAL_INTELLIGENCE (fallback).

**Key finding:** `route()` **never selects a capability.** The registry is built
but only `_route_specs` (a separate, partially overlapping table) drives the
route. Capabilities are not connected to output types (no DOCUMENT_ENGINE /
PRESENTATION_ENGINE / SPREADSHEET_ENGINE distinction — everything "create" goes
to CREATION_ENGINE), and capability ids do not match the benchmark's expected
ids (`GLOBAL_INTELLIGENCE_ENGINE`, `VISION`, `SYSTEM_DIAGNOSTICS`). Execution
mode accuracy (29.8%) is low precisely because specialized engines are chosen
from the spec table only when the exact `(domain, intent)` pair is listed.

## 5. Current Benchmark Model

`validation_benchmark/`:
- `development.json` (312), `validation.json` (104), `held_out.json` (104),
  `full_benchmark.json` (520), `evaluation_results.json` (last real run).
- Each case: `request, intent, topic, entities, domain, capability, output_type,
  execution_mode, reasoning_depth, freshness, tools_required, risk_level,
  language, complexity, expected_response`.
- `evaluate_benchmark.py` converts labels via `Enum[name.upper()]` with silent
  first-member fallback — a **label-taxonomy mismatch** that both deflates real
  accuracy and hides the reason. Held-out uses only 7 domains, 16 intents,
  8 capabilities, 12 output types; several labels have no enum member
  (`simple_question`, `explanation`, `analysis`, `fast_model`→OK, `deep` vs
  `HIGH`, `live`, `vision`, `system_diagnostics` as execution modes).
- Last real eval: intent 0.481, domain 0.442, execution_mode 0.269, reasoning
  0.519, freshness 0.789, risk 0.577, tools 0.587, language 1.0, complexity
  0.904, unsafe 0.0, avg latency 0.21 ms. Baseline JSON (AI_MANAGER_3_1) records
  a different historical run (intent 0.779 etc.) — **baseline file is a record,
  not to be edited**; 4.0 gets its own benchmark + baseline.

## 6. Current Failures (root-caused)

1. **Intent enum missing canonical conversational intents** → 13 smoke labels +
   ~10 held-out labels silently map to `GENERAL_REQUEST`. Root cause of 10/40.
2. **Interrogative vs imperative not distinguished** → "why do we need sleep" →
   `SYSTEM_SLEEP`; "what is python" → `CODING_DEBUG`; "who is einstein" →
   `GENERAL_REQUEST`. No `is_question` signal.
3. **Domain-specific intent disambiguation missing** → "open notepad" →
   `FILE_OPEN`/`FOLDER_OPEN` (pattern-normalization ties beat APP_CONTROL);
   TRADING domain has no entry in `_domain_specific_intents_map`, so
   "should I buy reliance stock" → `GENERAL_REQUEST`.
4. **Hinglish verbs not in intent detection** → "youtube kholo" relies on the
   GENERAL lexical bag, not on a verb-level action signal.
5. **Arbitrary boosts** → ×1.5 non-GENERAL domain bonus (line 2203), ×2.0
   domain-intent boost (line 2329), ×0.5 confidence_boost cap, `+0.1` style
   word-count boost — unvalidated constants per the 4.0 directive.
6. **Fast path dead** → `_apply_fast_deterministic_check` never called.
7. **Calibration no-op** → confidence always `min(base + boost, 1.0)`; never
   reflects agreement/disagreement across components.
8. **No output type / capability / topic / multi-intent / abstention on the
   route** → TaskRoute carries 12 fields, none of the 4.0 dimensions.
9. **Capability registry disconnected** from routing (see §4).

## 7. Duplicate / Legacy Systems

- `desktop_agent/brain/ai/router/*` — DEPRECATED (EPIC-03). Keep as legacy
  reference; do not resurrect. `AIRouter.route()` returns LOCAL/LLM only.
- `IntentCandidate` x2 (lines 196/208) — collapse.
- `Domain.TRADING_FINANCE` — duplicate of `Domain.TRADING`; treat TRADING as
  canonical, keep member for back-compat (do not delete).
- `semantic_models.Intent` — separate intentional namespace; leave untouched.
- Complexity test script (`test_ai_manager.py`) relies on removed complexity
  API — restore `_determine_complexity_hints` (used to drive reasoning depth).

## 8. Proposed Changes (AI Manager 4.0)

All changes **extend `ai_manager.py`** (no second router/provider-selector/
capability-registry/confidence-engine/benchmark framework):

1. **Ontology:** add canonical conversational intents to `Intent` (ASK, EXPLAIN,
   ANALYZE, COMPARE, EVALUATE, CALCULATE, PLAN, OPTIMIZE, PREDICT, SUMMARIZE,
   VERIFY, DESIGN, EDIT, MODIFY — mapping the 4.0 recommended list onto the
   existing enum). Add `OutputType` enum. Extend `Freshness` with `LIVE`.
   Extend `TaskSignals` with `is_question`, `output_type`, `multi`.
   Extend `TaskRoute` (defaulted new fields → backward compatible):
   `capability`, `output_type`, `topic`, `entities`, `tools_required`,
   `raw_score`, `semantic_confidence`, `route_score`, `calibrated_confidence`,
   `decision` (ROUTE/CLARIFY/ABSTAIN), `clarification_question`,
   `multi_intents`, `component_scores`.
2. **Intent detection:** component evidence per candidate (pattern, action,
   domain, topic, output, entity, question) with weights summing to 1; hinglish
   verb map (kholo/banao/karo/dikhao/chalao/batao/band karo — a bounded verb
   set, not a giant dictionary); `is_question` suppresses pure-imperative tool
   intents; domain-conditional disambiguation (APP_CONTROL vs FILE_OPEN resolved
   by domain compatibility derived from route-spec/capability tables).
3. **Domain detection:** remove ×1.5 bonus; balanced, validated weights;
   populate `semantic_score`/`tool_fit`/`context_fit`; richer entity extraction
   (apps/websites/files) without memorization.
4. **Output classification:** `_classify_output_type` from requested-output
   nouns + action + domain (website/code/presentation/document/spreadsheet/
   analysis/report/answer/explanation/comparison/action/…). "create" alone never
   decides capability.
5. **Capability-first routing:** `_select_capability` scores every registry
   capability by domain/intent/output/tool/context fit; add DOCUMENT_ENGINE,
   PRESENTATION_ENGINE, SPREADSHEET_ENGINE; execution mode comes from the
   selected capability (fixes 29.8% execution accuracy) with the spec table as
   fallback for back-compat.
6. **Reasoning/freshness/risk/tools:** reasoning from restored complexity hints
   (MINIMAL/BASIC/MODERATE/HIGH/EXTENSIVE); freshness from signals + domain +
   new LIVE; risk = classification only (PermissionManager stays authoritative);
   tools_required from capability + tool_hints.
7. **Confidence & calibration:** separate `raw_score`, `semantic_confidence`
   (component agreement), `route_score`, `calibrated_confidence`. Disagreement
   across intent/domain/capability/output lowers calibrated confidence. No
   arbitrary +0.1/+0.2/×3/caps.
8. **Clarify / abstain:** low top-domain/top-intent confidence or cross-dimension
   disagreement → `decision=CLARIFY` with a generated question; UNKNOWN/no
   signals → `ABSTAIN`. Never unsafe: abstain rather than guess on risky tools.
9. **Multi-intent:** detect conjunctive/multi-clause inputs ("open notepad and
   close chrome") → `multi_intents` structured list (EPIC-BRAIN compatible);
   primary route = first segment.
10. **Fast path:** wire `_apply_fast_deterministic_check` at the top of `route()`
    for exact anchored patterns only (greeting/thanks/affirmative/negative/
    command/time) — no substring capture of longer phrases.
11. **Provider:** capability-first preference (capability.supported_models →
    fallback_models → spec/provider order) while preserving `_preference_for`
    contract; never a stronger model for its own sake.
12. **Self-evaluation telemetry:** in-memory ring buffer `_route_history`
    (input, selected route, candidate routes, component scores, confidence,
    decision, latency); `route_history()` / `self_evaluation_summary()`; no
    secrets, no self-modification.
13. **Benchmark:** repair only provably obsolete gold labels (rationale per
    label); create `AI_MANAGER_4_0_BENCHMARK/` with 500+ unseen cases across the
    required categories/case-types/languages; dev/validation/held-out split;
    extend `evaluate_benchmark.py` (new fields) rather than duplicating it.

**Backward-compat gates that must stay green:** `route()` still returns a
`TaskRoute` with the original 12 attributes; `_preference_for` signature
unchanged; `generate`/`stream_generate`/`resolve_provider`/`active_provider`/
`_by_name` unchanged; P0 suite (298 passing) must not regress; `_POWER_CALLS == []`.

**Out of scope (STOP gate):** no EPIC-BRAIN, no full MYRAA integration, no NX /
Trading / Creation expansion, no JARVIS UI, no EPIC-14H / EPIC-15.