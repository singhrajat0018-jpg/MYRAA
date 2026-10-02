# MYRAA AI Manager Deep Forensic Audit

**Date:** 2026-08-18  
**Auditor:** Claude Code (Principal Architect)  
**Repository:** MYRAA (Windows Desktop AI Assistant)  
**Scope:** Complete repository-wide forensic audit with special emphasis on AI Manager  
**Restrictions:** Audit only – no code modifications, no refactoring, no implementation.

---

## Executive Summary

MYRAA is a Windows desktop AI assistant inspired by JARVIS/Tony Stark, designed to understand natural language, speak & listen naturally, act proactively, observe screen, control mouse/keyboard/apps/browser, perform file/system operations, research the web, and serve as an advisory trading companion (Hinglish). The current implementation consists of:

- **Frontend:** React/Electron voice companion with Gemini Live voice/vision bridge.
- **Backend:** Node/Express server (`:3000`) handling WebSocket `/live` for Gemini Live, REST APIs, and proxy services.
- **Desktop Agent:** Python/FastAPI server (`:8765`) exposing `/execute` and `/brain` endpoints, housing the core AI, tools, and automation capabilities.
- **Brain:** Rule/heuristic-based cognitive architecture (no LLM invocation) with modules for perception, memory, planning, execution, etc.
- **AI Manager:** Routing component that maps user intents to capabilities, execution modes, and providers via pattern matching and heuristics.

**Key Findings:**
- The AI Manager is a sophisticated rule-based routing system (AI Manager 4.0) with well-defined intents, domains, capabilities, and execution modes.
- However, the **Brain does not invoke any LLM** – it is entirely rule/heuristic-based, making the AI Manager's output never actually fed to a generative model.
- Critical **disconnections**: Node→Python desktop-tool dispatch is stubbed (`server.ts` never calls `callDesktopAgent`); memory persistence is disabled; financial `YahooProvider` is broken; permission system is a no-op.
- The AI Manager architecture is internally consistent but **isolated from the LLM/provider layer** – it prepares routing decisions but the system does not use LLMs for reasoning or generation.
- Overall, MYRAA demonstrates substantial desktop automation capabilities but lacks true AI-driven reasoning, learning, or adaptive behavior.

**Scores (out of 100):**
- Overall MYRAA: 48
- Architecture: 55
- AI Intelligence: 30
- AI Manager: 70
- Reasoning: 25
- Generalization: 40
- Computer Use: 80
- Vision: 65
- Research: 20
- Coding: 55
- Creation: 45
- Memory: 30
- Planning: 50
- Verification: 35
- Recovery: 25
- Safety: 60
- Security: 55
- Performance: 70
- Voice: 75
- Trading: 20
- NX: 10
- UI: 80
- Testing: 30
- Documentation: 50
- Integration: 35

**Super-Brain Readiness:** 20/100 – Major rework required to integrate LLM-driven reasoning, connect broken components, and wire research/finance/trading pipelines.

---

## 1. Full System Architecture

### 1.1 Actual Architecture (Verified)

```
React (Electron) ── WS /live ──► Node (server.ts, :3000)
React ── fetch /api/* ─────────► Node
Node ── POST /execute, /brain ─► Python Desktop Agent (FastAPI :8765)
Python ── CommandDispatcher ──► Tool handlers (pyautogui / Playwright / win32)
Python ── observer loop (30s) ─► BrainEngine.process_event
React ── video frames ──► Node ──► Gemini Live (vision)
Node ── audio/transcripts ──► Gemini Live (STT/TTS/voice)
```

### 1.2 Critical Discrepancy
In `server.ts` the desktop-tool branch (`DESKTOP_TOOLS.has(fc.name)`, ~line 1473) is **stubbed** — it sets `agentResult = { ok: true, result: brainResult }` and **never calls `callDesktopAgent(fc.name, fc.args)`**. So Gemini function calls for desktop tools currently get a fake `{result:"Done."}` response and **do not actually reach Python**. `ENABLE_FUNCTION_CALL_BRAIN = false`. The real bridge exists (`services/desktop/desktop_agent.ts → callDesktopAgent` → `POST /execute`) but is not wired into the tool-call path.

### 1.3 Directory Structure (as verified)

- `server.ts` – Node/Express + WS /live
- `server_paths.ts` – data dir + Gemini API key secrets store
- `server_memory.ts` – memories.json load + Gemini memory consolidation (WRITE DISABLED)
- `desktop_agent/` – Python Desktop Agent (FastAPI :8765)
  - `main.py` – FastAPI app + CommandDispatcher + wiring
  - `registry.py` – TOOLS dict, register(), State, PermissionManager
  - `tools_*.py` – 15 tool modules (real pyautogui/Playwright/win32/PIL implementations)
  - `brain/` – BrainEngine, ExecutionBrain, knowledge/, observer/, ai/, planner/, etc.
  - `finance/` – advisory-only stubs (YahooProvider broken)
- `src/` – React frontend (App.tsx shell, components/, lib/, core/)
- `tests/` – Python pytest for desktop tools + finance + parsers (many stubs)

### 1.4 Data Flow for Voice Command (Actual)
1. React (`src/lib/audio.ts`) opens `ws://host/live`, streams 16kHz mic PCM.
2. Node (`server.ts`) bridges to **Gemini Live** (`gemini-3.1-flash-live-preview`), forwards model 24kHz PCM back, sends transcriptions.
3. For every user turn, Node also calls the **Python Brain** (`POST /brain`) and (when enabled) routes Gemini function calls to the Python agent.
   - **Currently disabled**: Desktop-tool branch stubbed → no actual tool execution via Python.
4. Python dispatches to tool handlers → Windows (when tools are called via `/execute`).

### 1.5 Working / Broken / Limitations (Per CLAUDE.md)

**Working:**
- React voice companion ↔ Gemini Live
- Video frames to Gemini vision
- All ~60 desktop tools (mouse/keyboard/files/windows/clipboard/OCR/browser/coding/system/volume/brightness/power-confirmation/autostart)
- Brain/ExecutionBrain pipeline (rule-based)
- Observer → brain events
- Electron shell + splash
- API-key onboarding; settings; logs; web/youtube proxies

**Broken / Disabled:**
- **Node→Python desktop-tool dispatch is stubbed** (server.ts `DESKTOP_TOOLS` branch never calls `callDesktopAgent`) — Gemini function calls don't reach Python.
- **Memory persistence disabled** — `saveMemories()` write is commented out in `server_memory.ts`.
- **`YahooProvider` runtime `TypeError`** against `MarketQuote` contract; `yfinance` missing from requirements.
- `PermissionManager.check` is a no-op (no real permission gate).
- `spawnDesktopAgent()` is a stub (agent must be started externally).
- `services/ai` and `services/voice` are empty scaffolding.
- Groww/NSE finance providers, SafetyManager, VerificationManager are stubs.

**Missing:**
- Finance NIFTY/indicators/decision-model/trade-history/intelligence
- Research `/research` endpoint + orchestration
- **All telemetry**
- TS tests
- Brain LLM invocation (rule-based only)

---

## 2. AI Manager Architecture Deep Dive

### 2.1 Overview
The AI Manager (`desktop_agent/brain/ai/ai_manager.py`) is responsible for:
- Language detection (English/Hinglish)
- Fast-path deterministic matching (greetings, thanks, commands, time)
- Semantic signal extraction (entities, topic, action, output, modality, freshness)
- Intent classification (pattern-based, with domain-specific boosts)
- Domain detection (lexical, entity, action, topic, object, output, modality weighting)
- Capability selection (capability-first routing)
- Routing to execution mode, reasoning depth, freshness, risk, tools
- Confidence calculation and calibration
- Provider selection (Gemini, Ollama, Nim) based on hints and route
- Self-evaluation telemetry (in-memory)

It returns a `TaskRoute` object but does **not** invoke any LLM or perform generation. The `BrainEngine` uses this route? Actually, from code inspection, the AIManager's `route` method is called by `BrainEngine` or directly? In `main.py`, the `/brain` endpoint calls `BRAIN.run`, which likely uses the AIManager internally. However, the CLAUDE.md states: "`BrainEngine.process()` only computes an AI route and **never calls `provider.generate()`**. The brain is effectively **rule/heuristic-based**, not LLM-driven."

### 2.2 Core Components
- **Enums**: Intent (101 values), Domain (17), ExecutionMode (11), ReasoningDepth (6), Freshness (5), RiskLevel (8), Modality (7), Language (2), OutputType (24)
- **TaskSignals**: Container for extracted signals (entities, topic, object, action, requested_output, modality, context, tool_hints, freshness, language, is_question, output_type, multi)
- **DomainCandidate**, **IntentCandidate**, **CapabilityCandidate**: Scoring objects with evidence and confidence
- **AIManager**: Main class with initialization of patterns, mappings, route specs, capability registry
- **TaskRoute**: Output object containing routing decision

### 2.3 Initialization (Key Data Structures)
- `_domain_patterns`: Keyword lists per domain (heavily overlapping, especially GENERAL domain which includes almost every word)
- `_intent_patterns`: Word/phrase lists per intent (large overlaps, many generic terms)
- `_domain_specific_intents_map`: Maps domains to intents specific to that domain (e.g., TRADING → TRADING_ANALYSIS, TRADING_MONITORING, TRADING_DECISION)
- `_action_verbs`, `_domain_action_verbs`, `_intent_action_verbs`: Verb mappings
- `_domain_topic_nouns`, `_domain_object_nouns`, `_domain_output_nouns`: Noun mappings per domain
- `_domain_entities`: Known entities per domain (e.g., TRADING: nifty, sensex, stock, etc.)
- `_route_specs`: Hardcoded routing specifications for (Domain, Intent) tuples → execution_mode, reasoning_depth, freshness, tool_required, risk_level, latency_sensitivity, provider_preference, confidence_boost, explanation
- `_capability_registry`: Map of capability IDs to Capability objects (TRADING_ENGINE, NX_ENGINEERING_ENGINE, RESEARCH_PIPELINE, CODING_ENGINE, DOCUMENT_ENGINE, PRESENTATION_ENGINE, SPREADSHEET_ENGINE, CREATION_ENGINE, SYSTEM_DIAGNOSTICS, COMPUTER_USE, PHONE_ENGINE, VISION_ENGINE, VOICE_ENGINE, SYSTEM_ENGINE, FILES_ENGINE, GENERAL_INTELLIGENCE_ENGINE)

### 2.4 Routing Flow (AI Manager 4.0 Pipeline)
```
USER INPUT
  → language detection (Hinglish indicators)
  → fast-path exact match (anchored regex patterns)
     → if match: return TaskRoute with FAST_DETERMINISTIC execution
  → signal extraction (_extract_task_signals)
     → entities, action, topic, object, requested_output, modality, freshness, language, is_question, tool_hints, context (empty)
  → output-type classification (_classify_output_type)
     → maps nouns to OutputType (PRESENTATION, SPREADSHEET, WEBSITE, CODE, etc.)
  → domain detection (_detect_domain_candidates)
     → weighted combination of lexical, entity, action, topic, object, output, modality fits
  → intent classification (_get_intent_candidates)
     → pattern_score, action_fit, domain_fit, topic_fit, output_fit, entity_fit, semantic_score (Hinglish)
     → interrogative suppression: if question and intent in _QUESTION_SUPPRESS_INTENTS and no action verb match → reduce domain_fit
  → capability selection (_capability_for)
     → capability-first: score capabilities by intent_fit, domain_fit, output_fit, tool_fit, context_fit
  → route spec lookup (_get_route_spec)
     → fallback to GENERAL if Domain-Intent pair not found
  → execution mode selection (_capability_execution_mode)
     → capability-first mapping: TRADING_ENGINE → TRADING_ENGINE mode, etc.; conversational intents use _CONVERSATIONAL_EXECUTION_MODE
  → reasoning depth (_derive_reasoning_depth)
     → based on intent and complexity hints (_determine_complexity_hints: simple/medium/complex/deep_planning)
  → freshness (_derive_freshness)
     → from signals, intent, domain (TRADING → REAL_TIME, VISION → LIVE, RESEARCH/SYSTEM → RECENT)
  → risk (_derive_risk)
     → FINANCIAL for trading intents/domains; MEDIUM for system-critical actions; LOW for computer/phone/file/vision/voice; NONE for conversational
  → tools required (_tools_required_for)
     → from capability.required_tools + signal.tool_hints
  → provider preference
     → from route.spec.provider_preference, overridden by capability.supported_models
  → confidence calculation (_calculate_confidence)
     → domain_confidence * 0.4 + intent_confidence * 0.6 (capped at 1.0)
  → confidence calibration (_apply_confidence_calibration)
     → downward pressure only on conflicting evidence (no arbitrary boosts)
  → final TaskRoute with all dimensions
```

### 2.5 Provider Selection
- AIManager does **not** invoke providers in `route()`; it only prepares `provider_preference` list.
- Separate methods: `resolve_provider()`, `generate()`, `stream_generate()` use `_preference_for()` to get ordered provider list, then lazily instantiate providers (GeminiProvider, OllamaProvider, NimProvider) and call their `.generate()`.
- Provider health, availability, and failover managed via failure containment.

### 2.6 Knowledge & Research Wiring
- The `brain/knowledge/` library exists (TavilyProvider, QueryClassifier, SearchRouter, etc.) but is **not wired into the running app** — no `/research` endpoint, no ResearchOrchestrator, no complexity classifier.
- Only the project/knowledge part is wired via `core/app_context.py` into semantic parsing.
- Retrieved web content treated as untrusted (must never execute instructions or override MYRAA behavior).

## 3. Ontology Analysis

### 3.1 Concept Separation Assessment
| Concept | Current Implementation | Correct Meaning | Current Problem | Impact | Severity |
|---------|------------------------|-----------------|-----------------|--------|----------|
| **Intent** | What the user wants to do (verb) | ✅ Largely correct | Some intents overlap with topics/outputs (e.g., CREATING vs. CREATION_DOCUMENT) | Medium | P2 |
| **Topic** | Subject matter (nouns from signals.topic) | ✅ Used correctly | Often conflated with intent via keyword spotting (e.g., "analyze" triggers ANALYZE intent regardless of topic) | High | P1 |
| **Entity** | Domain-specific nouns (e.g., nifty, python) | ✅ Extracted correctly | Limited to hardcoded lists; no NER or dynamic extraction | Medium | P2 |
| **Domain** | Subject area (e.g., TRADING, CODING) | ✅ Detected via multi-evidence scoring | Heavily reliant on keyword overlap; GENERAL domain acts as catch-all; domain detection can be overridden by intent compatibility | High | P1 |
| **Capability** | Engine that can fulfill request (TRADING_ENGINE, etc.) | ✅ Capability-first routing | Capability selection heavily influenced by intent/domain fit; output_fit scoring is simplistic | Medium | P2 |
| **Output Type** | First-class product (PRESENTATION, CODE, etc.) | ✅ Introduced in AI Manager 4.0 | Still competes with intent (e.g., "create a presentation" – intent CREATION vs. output PRESENTATION) | Medium | P2 |
| **Execution Mode** | How to process (FAST_MODEL, DEEP_REASONING, etc.) | ✅ Mostly correct | Often tied to intent/capability rather than emergent complexity; reasoning depth heuristics are simplistic | High | P1 |
| **Reasoning Depth** | Depth of thinking required | ❌ Not derived from actual reasoning | Based on intent + complexity hints; no evidence of multi-step reasoning or planning depth | High | P1 |
| **Freshness** | Recency requirement | ✅ Correctly derived | LIVE only for VISION SCREEN/OBJECT/OCR; no real-time ticker for trading despite specification | Medium | P2 |
| **Risk** | Risk classification (separate from auth) | ✅ Mostly correct | FINANCIAL risk identified but no actual financial permission gate; PermissionManager is no-op | High | P1 |
| **Tools Required** | Actual tool invocations needed | ✅ Derived from capability + signals | Often missing implied tools (e.g., web research needs browser_tool but capability may not list it) | Medium | P2 |
| **Context** | Conversational/situational context | ❌ Not passed to AIManager | context set is always empty in signals; context fusion happens later in Brain? | High | P1 |
| **Modality** | Input/output modality (TEXT, VOICE, etc.) | ✅ Detected from verbs/nouns | Limited heuristics; no fusion of multimodal inputs | Medium | P2 |
| **Confidence** | Routing confidence score | ❌ Not calibrated probability | Heuristic blend of domain/intent scores; no grounding in actual accuracy; prone to inflation | High | P1 |

### 3.2 Key Ontology Problems
- **Intent/Topic Blur**: Many intents are defined by generic verbs (analyze, explain, create) that do not uniquely determine the action without topic/context.
- **Domain as Keyword Salad**: Domain detection relies on keyword lists with massive overlap (especially GENERAL domain), leading to ambiguous domain assignment.
- **Capability vs Intent Redundancy**: Many capabilities support nearly identical intents (e.g., CREATION_ENGINE vs DOCUMENT_ENGINE vs PRESENTATION_ENGINE).
- **Execution Mode Static Mapping**: Execution mode is largely a static lookup from intent/capability, not dynamically computed from task complexity, dependencies, or resource constraints.
- **Reasoning Depth Misnomer**: Reasoning depth is not correlated with actual reasoning steps, planning depth, or verification requirements; it's a static label per intent.
- **Confidence Heuristic**: Confidence is a weighted average of domain/intent scores with no probabilistic interpretation; does not support abstain/clarify/escalate decisions effectively.

## 4. Routing Flow Analysis (Concrete Examples)

### 4.1 Request: "analyze NIFTY"
1. Language: English (no Hinglish)
2. Fast-path: No match
3. Signals:
   - entities: {'nifty'}
   - action: {'analyze'}
   - topic: {'analyze'} (from domain topic nouns? Actually "analyze" is verb, not noun – topic extraction may miss)
   - requested_output: {} (no output nouns)
   - modality: TEXT
   - freshness: STATIC → later overridden to REAL_TIME by TRADING intent
   - is_question: false
4. Domain Detection:
   - TRADING: entity match (nifty) → high entity_score; action match (analyze) → good action_fit; lexical: 'analyze' in TRADING patterns → lexical_score
   - CODING: 'analyze' in CODING patterns → but no entity match
   - GENERAL: high lexical due to broad patterns
   - Likely TRADING wins due to entity boost
5. Intent Detection:
   - Patterns: 'analyze' matches INTENT.ANALYZE, TRADING_ANALYSIS, etc.
   - Domain-specific boost: TRADING domain -> boosts TRADING_ANALYSIS, TRADING_MONITORING, TRADING_DECISION
   - Best intent: TRADING_ANALYSIS (high pattern + domain boost)
6. Output Type: No output nouns → defaults to ANSWER? Actually `_classify_output_type` sees 'analyze' in text → returns OutputType.ANALYSIS (line 2255-2258)
7. Capability Selection:
   - TRADING_ENGINE: intent_fit=1.0 (supports TRADING_ANALYSIS), domain_fit=1.0, output_fit for ANALYSIS? `_capability_output_fit`: ANALYSIS -> 0.8 if capability in RESEARCH_PIPELINE or TRADING_ENGINE → 0.8
   - Tool fit: signals.tool_hints empty? `_extract_task_signals` for 'analyze' adds 'web_research'? No, only if action includes search/google/find → no. So tool_fit = 0.3 (default if required_tools exists)
   - Overall confidence high → selects TRADING_ENGINE
8. Route Spec: (TRADING, TRADING_ANALYSIS) → execution_mode=TRADING_ENGINE, reasoning_depth=HIGH, freshness=REAL_TIME, tool_required=true, risk=FINANCIAL, etc.
9. Final Route: Intent=TRADING_ANALYSIS, Domain=TRADING, ExecutionMode=TRADING_ENGINE, ReasoningDepth=HIGH, Freshness=REAL_TIME, Risk=FINANCIAL, ToolsRequired=['market_data'] (from capability)

### 4.2 Request: "create a presentation about AI"
1. Signals: action={'create'}, requested_output={'presentation'}, topic maybe {'presentation'}
2. Domain: CREATIVE (output nouns match) or GENERAL
3. Intent: CREATION_DOCUMENT? Actually 'create' matches CREATING intent; domain-specific boost for CREATIVE domain may boost CREATION_DOCUMENT, CREATION_PRESENTATION, etc.
   - However, `_classify_output_type` returns PRESENTATION due to 'presentation' in requested_output.
4. Capability Selection: PRESENTATION_ENGINE wins for intent_fit (if intent is CREATION_PRESENTATION?) or CREATION_ENGINE.
   - If intent remains CREATING, CREATION_ENGINE may win due to broader intent support.
5. Output Type correctly classified as PRESENTATION.
6. Route: Likely CREATION_ENGINE or PRESENTATION_ENGINE → ExecutionMode=CREATION_ENGINE.

### 4.3 Request: "what is the time"
- Fast-path match for 'time' → Intent.TIME_QUERY, Domain=GENERAL (from `_fast_domain_for`), ExecutionMode=FAST_DETERMINISTIC, ReasoningDepth=MINIMAL, Freshness=REAL_TIME (from spec), etc.

### 4.4 Request: "explain why the sky is blue"
1. Signals: action={'explain'}, topic maybe {'sky','blue'}
2. Domain: GENERAL or EDUCATION
3. Intent: EXPLAIN (pattern match)
4. Output Type: EXPLANATION
5. Capability: GENERAL_INTELLIGENCE_ENGINE (fallback) or maybe DOCUMENT_ENGINE? Actually `_classify_output_type` for 'explain' → EXPLANATION → `_capability_output_fit` gives 0.5 for GENERAL_INTELLIGENCE_ENGINE.
6. Route Spec: (GENERAL, EXPLAIN) → execution_mode=DEEP_REASONING, reasoning_depth=MODERATE (from `_CONVERSATIONAL_EXECUTION_MODE`), etc.
7. Final: Intent=EXPLAIN, Domain=GENERAL, ExecutionMode=DEEP_REASONING, ReasoningDepth=MODERATE.

## 5. Capability Analysis

### 5.1 Capability Registry Summary
| Capability ID | Domain | Supported Intents (examples) | Required Tools | Freshness | Risk | Latency | Supported Models |
|---------------|--------|------------------------------|----------------|-----------|------|---------|------------------|
| TRADING_ENGINE | TRADING | TRADING_ANALYSIS, TRADING_MONITORING, TRADING_DECISION | ['market_data'] | REAL_TIME | FINANCIAL | high | nim, gemini |
| NX_ENGINEERING_ENGINE | NX_ENGINEERING | NX_CREATE, NX_CONVERT | ['nx_tools'] | STATIC | LOW | medium | nim, gemini |
| RESEARCH_PIPELINE | RESEARCH | RESEARCHING, INVESTIGATING, STUDYING | ['web_research'] | RECENT | LOW | medium | nim, gemini |
| CODING_ENGINE | CODING | CODING_DEBUG, CODING_BUILD, CODING_FIX, CREATION_CODE | ['code_execution', 'debugger'] | STATIC | LOW | medium | nim, gemini |
| DOCUMENT_ENGINE | DOCUMENT | CREATION_DOCUMENT, DOCUMENT_SUMMARIZE, DOCUMENT_TRANSLATE | ['document_editor'] | STATIC | LOW | medium | nim, gemini |
| PRESENTATION_ENGINE | CREATIVE | CREATION_PRESENTATION | ['presentation_tool'] | STATIC | LOW | medium | nim, gemini |
| SPREADSHEET_ENGINE | CREATIVE | CREATION_SPREADSHEET | ['spreadsheet_tool'] | STATIC | LOW | medium | nim, gemini |
| CREATION_ENGINE | CREATIVE | CREATION_DOCUMENT, CREATION_PRESENTATION, CREATION_SPREADSHEET, CREATION_CODE | ['document_editor', 'presentation_tool'] | STATIC | LOW | medium | nim, gemini |
| SYSTEM_DIAGNOSTICS | SYSTEM | SYSTEM_DIAGNOSTICS | ['system_tools'] | RECENT | LOW | medium | gemini, ollama, nim |
| COMPUTER_USE | COMPUTER | APP_CONTROL, WEB_NAVIGATION, SCREEN_CAPTURE | ['desktop_tool'] | STATIC | LOW | medium | gemini, ollama |
| PHONE_ENGINE | PHONE | PHONE_CONTROL, PHONE_CALL, PHONE_SMS | ['phone_tool'] | STATIC | LOW | medium | gemini, ollama |
| VOICE_ENGINE | VOICE | 11 audio/voice intents | ['voice_tool'] | STATIC | LOW | medium | gemini, ollama |
| SYSTEM_ENGINE | SYSTEM | 7 system intents | ['system_tools'] | RECENT | LOW | medium | gemini, ollama |
| FILES_ENGINE | FILES | 11 file/folder intents | ['file_tool'] | STATIC | LOW | medium | gemini, ollama |
| GENERAL_INTELLIGENCE_ENGINE | GENERAL | all intents (fallback) | [] | STATIC | NONE | low | gemini, ollama |

### 5.2 Capability Problems
- **Tool Mismatch**: Many capabilities list generic tools (e.g., 'web_research') that are not actual registered tool names in `TOOLS`. The real tools are like `searchWeb`, `searchYouTube`, etc. This creates a disconnect where capability.required_tools does not match actual tool handlers.
- **Output Fit Simplistic**: `_capability_output_fit` uses hardcoded mapping (e.g., PRESENTATION only from PRESENTATION_ENGINE) ignoring that CREATION_ENGINE can also produce presentations at reduced confidence.
- **Fallback Models Missing**: Many capabilities have empty fallback_models, forcing reliance on gemini/ollama only.
- **Latency Profiles Vague**: 'high', 'medium', 'low' not quantified.
- **Context Requirements Generic**: e.g., ['template', 'outline'] for creation engines – not validated or used elsewhere.

## 6. Benchmark Analysis (From Available Files)

### 6.1 Test Files Reviewed
- `test_ai_manager.py`: Complexity detection tests (simple/medium/complex/deep_planning)
- `test_ai_manager_3.py`: AI Manager 3.0 semantic routing tests (intent/execution mode matching)
- `test_epic14g_fast_path.py`: Fast path deterministic matching
- `test_route.py`: Likely route testing
- `AI_MANAGER_3_1_BASELINE.json`: Baseline metrics

### 6.2 Observations from Test Files
- **Complexity Detection**: Rule-based keyword sets; works for clear cases but likely fails on ambiguous or novel phrasing.
- **AI Manager 3.0 Tests**: Show that intent matching works for explicit keywords but struggles with implicit or paraphrased requests.
- **Fast Path**: Over 100 anchored regex patterns for greetings, commands, time, app control, etc. – high precision for exact matches but low recall for variations.
- **Baseline JSON**: Contains confidence scores, latency, etc. for a set of test cases (not examined in detail due to scope).

### 6.3 Benchmark Limitations
- Tests are **unit-tests** for the AIManager in isolation; they do not test end-to-end routing with actual LLM/provider invocation (since none occurs).
- No held-out set for generalization to unseen linguistic variations (hinglish, code-switching, ellipsis).
- No adversarial testing for intent/domain confusion.
- Benchmarks measure internal consistency, not real-world accuracy or user satisfaction.

## 7. Confidence Analysis

### 7.1 How Confidence is Computed
1. **Domain Confidence**: From `_detect_domain_candidates` – weighted sum of lexical, entity, action, topic, object, output, modality fits.
2. **Intent Confidence**: From `_get_intent_candidates` – weighted sum of pattern_score, action_fit, domain_fit, topic_fit, output_fit, entity_fit, semantic_score (Hinglish).
3. **Base Confidence**: `domain_confidence * 0.4 + intent_confidence * 0.6` (capped at 1.0).
4. **Calibration**: Downward multiplier of 0.9 if:
   - Top two domain candidates have <0.05 margin
   - Top two intent candidates for the selected intent have <0.05 margin (and intents differ)
   - Capability candidate confidence <0.3

### 7.2 Problems
- **No Probabilistic Grounding**: Confidence scores are not calibrated to actual correctness rates; a confidence of 0.8 does not mean 80% chance of correct routing.
- **Inflation Risk**: Multiple evidence types can additive boost confidence beyond what is warranted (e.g., high lexical + entity + action fits).
- **Arbitrary Weights**: 0.4/0.6 split between domain and intent is heuristic.
- **Calibration Heuristics**: Downward pressure only; no upward calibration for strong evidence.
- **No Abstain/Clarify Thresholds**: System always returns a route (unless exception); no mechanism to say "low confidence, ask for clarification".
- **Semantic Confidence Always 0**: Not used; Hinglish gives semantic_score boost but not reflected in final semantic_confidence field.

### 7.3 Example of Overconfidence
Request: "analyze this code"  
- Domain: CODING (entity: 'code'? Actually 'code' is in entity extraction? Yes, from `_extract_entities` adds 'python', 'java', etc. if found. 'code' alone may not be detected as entity unless in list. But 'analyze' action matches CODING domain patterns.
- Intent: ANALYZE (pattern match)
- Context: empty
- Confidence may be high due to strong action/pattern match, but the request could be ambiguous (analyze code for bugs? for quality? for refactoring?) – yet confidence likely >0.7.

## 8. Integration Analysis

### 8.1 Brain → AIManager
- The Brain likely calls AIManager.route() during `BrainEngine.process()` to determine how to handle the input.
- However, **the Brain never invokes an LLM**; it uses the route to set internal state but then proceeds with rule-based reasoning only.
- **Disconnection**: AIManager prepares a route that includes LLM provider preferences, but the Brain ignores them and does not call `provider.generate()`.

### 8.2 AIManager → Provider
- Provider selection methods exist (`resolve_provider`, `generate`, `stream_generate`) and are functional (assuming API keys set).
- However, **no codepath from the main request flow (`/brain` or `/execute`) calls these methods** for reasoning/generation.
- The `/brain` endpoint returns a structured result from the Brain's rule-based processing, not from an LLM.

### 8.3 AIManager → Tools
- The AIManager's `tool_required` flag and `tools_required` list are computed but **not used to gate execution**; tool execution happens via `/execute` endpoint when Node forwards a desktop tool call (currently stubbed).
- When the stub is fixed, the AIManager's tool requirements could be used to verify necessary tools are available.

### 8.4 AIManager → Memory/Context
- **Context signals are always empty** in `_extract_task_signals` (line 3113: `signals.context = set()`).
- The AIManager does not receive conversation memory, project context, screen state, etc. as input.
- Context fusion presumably happens later in the Brain (e.g., in `context_manager.py`), but the AIManager operates context-free.

### 8.5 AIManager → Vision/Voz
- Modality detection works via verb/noun heuristics (e.g., 'see' → Modality.IMAGE, 'screen' → Modality.SCREEN).
- However, **the AIManager does not receive actual image/screen data**; it only infers modality from text.
- Real vision processing happens via the `/execute` endpoint for tools like `takeScreenshot`, `analyzeScreenshot`.

### 8.6 AIManager → Finance/Trading
- Finance intents/domains correctly routed to TRADING_ENGINE with REAL_TIME freshness and FINANCIAL risk.
- However, the **finance pipeline is broken**: YahooProvider has TypeError due to field mismatch; no historical data; no indicators; no trading engine execution.
- The AIManager would route correctly, but the backend cannot fulfill the request.

### 8.7 AIManager → Research
- Research intents route to RESEARCH_PIPELINE with RECENT freshness.
- However, **the research pipeline is not wired**: no Tavily API key usage in the live system; no web research tool registered; no `/research` endpoint.
- The capability exists but is inert.

### 8.8 AIManager → Coding/Creation
- Coding and creation intents route correctly to their respective engines.
- The **tools are registered and functional** (e.g., `createFile`, `runPythonScript`, `openApplication`).

## 9. Performance Analysis

### 9.1 Latency Components (Estimated)
- Signal extraction: O(N) over text + lookups in sets (fast)
- Pattern matching: O(P*I) for intents? Actually optimized via precompiled regex for fast path; intent patterns are iterated over.
- Domain detection: O(D*W) where D=domains, W=words in text (with weighting)
- Intent classification: O(I*P) similar
- Capability selection: O(C) where C=number of capabilities (~15)
- Overall: Likely <10ms for typical utterances on modern hardware.

### 9.2 Inefficiencies Noted
- **Redundant Iterations**: The AIManager iterates over all intents (101) for each request, computing pattern matches against large keyword lists.
- **Repeated Domain Detection**: Domain detection run once; intent classification re-checks domain compatibility via `_intent_compatible_domains`.
- **No Caching**: No caching of frequent phrases (e.g., greetings, common questions).
- **String Lowercasing**: Multiple lowercasing operations (`text.lower()` appears in many places).

### 9.3 Optimization Opportunities
- Compile intent patterns into regexes like fast path.
- Precompute intent-domain compatibility matrix.
- Cache signal extraction for repeated inputs.
- Use tries or Aho-Corasick for keyword matching.
- However, given the rule-based nature and low query volume (desktop assistant), current performance is likely acceptable.

## 10. Safety Analysis

### 10.1 Permission System
- `PermissionManager.check` is a **no-op** (`pass`) – no actual permission enforcement.
- Dangerous actions (power, file delete, etc.) rely on **two-step confirmation token flow** (`tools_confirmation.py`).
- This is a reasonable temporary measure but not scalable for fine-grained permissions.

### 10.2 Risk Classification
- Risk levels: NONE, LOW, MEDIUM, HIGH, FINANCIAL.
- FINANCIAL risk assigned to trading intents/domains.
- However, **risk classification is separate from authorization**; the AIManager reports risk but the PermissionManager does not use it.
- The confirmation flow is triggered by `PermissionManager.check` returning `"decision": "confirm"` for certain tools (e.g., power actions, file delete) – but since check is a no-op, it never returns `"confirm"`; the confirmation logic is dead.

### 10.3 Tool Safety
- Individual tools (e.g., `executePowerAction`, `deleteFile`) implement their own safety checks (e.g., validation, confirmation requirements in their handlers).
- However, without a functional PermissionManager, there is no centralized policy enforcement.

### 10.4 Prompt Injection Boundaries
- The AIManager does not execute user input as code; it only extracts signals and routes.
- The LLM providers (if invoked) would be exposed to user input, but currently **no LLM invocation occurs**.
- Therefore, **prompt injection via AIManager routing is not possible** – the worst case is misrouting, not code execution.

### 10.5 Data Leakage
- No secrets are logged or returned in routes (API keys remain server-side).
- Memories are not persisted (disabled), reducing leakage risk.

## 11. Generalization Analysis

### 11.1 Lingual Variation Handling
- **Hinglish**: Supported via `_extract_task_signals` (language detection) and `_intent_action_verbs` (hinglish verb mapping). However, the intent patterns themselves are English-only; hinglish verbs are mapped to English equivalents in `_HINGLISH_VERB_MAP` but only for a small set (kholo/banao/karo/dikhao/bata). Complex hinglish phrases may not be recognized.
- **Code-switching**: No explicit support; relies on English keyword spotting.
- **Misspellings/Typos**: No fuzzy matching; exact substring or word boundary matching only.
- **Paraphrasing**: The system relies on exact keyword matches; paraphrased requests (e.g., "can you tell me the time?" vs "what time is it") may fail fast path and rely on semantic similarity via intent patterns – but intent patterns are still keyword-based.

### 11.2 Conceptual Generalization Test (from instructions)
| Request | Expected Understanding | AIManager Likely Behavior |
|---------|------------------------|---------------------------|
| "analyze NIFTY" → "nifty ko detail mein check karo" | Same intent (TRADING_ANALYSIS) | Second phrase: hinglish verbs 'check karo' may map to 'check' → not in action verbs for TRADING_ANALYSIS; domain detection may still pick up 'nifty' entity → likely TRADING domain but intent may fall back to GENERAL_REQUEST or TRADING_MONITORING? Low confidence. |
| "create a presentation" → "AI par slides bana do" | CREATION_PRESENTATION | 'slides' may map to presentation topic; 'bana do' maps to 'create' → action {'create'}, topic maybe {'slides'} → likely CREATIVE domain, intent CREATING? Output type PRESENTATION from 'slides' → may route to CREATION_ENGINE with moderate confidence. |
| "research latest AI" → "AI ke recent developments ka detailed study karo" | RESEARCHING | 'detailed study karo' -> action {'study'}? hinglish 'karo' maps to 'do'? Not clear. Entity 'AI' not in extraction. May hit RESEARCH domain via 'recent developments'? Low confidence. |

**Verdict**: The AIManager exhibits **surface-level generalization** for simple hinglish verb mappings but **fails on deeper conceptual generalization** due to over-reliance on exact keyword matches and lack of semantic understanding.

## 12. Super-Brain Readiness Assessment

### 12.1 Criteria for Super-Brain (Master Brain + Memory + World Model + Task Graph + Specialized Engines + Research + Vision + Creation + Trading + NX)
The AIManager would need to:
- Accept rich context (memory, world model, task graph) as input.
- Output not just a route but also subgoals, required resources, and verification plans.
- Interface with LLM providers for reasoning, planning, and generation.
- Handle multimodal inputs (vision, audio) as first-class context.
- Support dynamic capability composition and tool chaining.
- Provide calibrated uncertainty estimates to enable clarification/abstain/escalation.
- Learn from feedback and update routing models over time.

### 12.2 Current GAPS
| Area | Status | Missing Work |
|------|--------|--------------|
| **Context Fusion** | ❌ No context input to AIManager | Modify `_extract_task_signals` to accept conversation memory, project state, screen state, active app, etc. |
| **LLM Integration** | ❌ Brain does not invoke LLMs; AIManager route not used for generation | Wire BrainEngine to call LLM providers based on route.provider_preference; enable reasoning_depth to control LLM temperature/top_p/t_max_tokens. |
| **Uncertainty Calibration** | ❌ Confidence is heuristic | Replace with calibrated probabilities using validation data; add thresholds for ROUTE/CLARIFY/ESCALATE/ABSTAIN. |
| **Dynamic Reasoning Depth** | ❌ Static per intent | Compute from task complexity (dependencies, tool count, verification needs) and available time/resources. |
| **Multimodal Routing** | ❌ Modality inferred only from text | Accept actual modality flags (from Node: audio, video, screen, document) and route accordingly (e.g., vision input → VISION_ENGINE regardless of text intent). |
| **Task Graph Support** | ❌ No decomposition | Enable AIManager to output subtasks, dependencies, and intermediate results for multi-intent requests (e.g., "research X and make a PPT"). |
| **Learning from Feedback** | ❌ No update mechanism | Log routing decisions and outcomes; periodically adjust pattern weights or retrain lightweight classifiers. |
| **Capability Chaining** | ❌ Atomic capabilities only | Allow routing to sequences of capabilities (e.g., RESEARCH_PIPELINE → CREATION_ENGINE) with data passing between stages. |

### 12.3 Readiness Score: 20/100
The AIManager architecture is **internally sound** as a rule-based router but **lacks the hooks, extensions, and integration points** to serve as the control layer of a true AI-driven Super-Brain. Major rework is required in context handling, LLM invocation, uncertainty quantification, and task decomposition.

## 13. Full MYRAA Capability Matrix (Working/Status)

| Capability | Status | Notes |
|------------|--------|-------|
| Voice Companion (STT/TTS) | ✅ Working | React ↔ Gemini Live via WS /live |
| Vision (Frame to Gemini) | ✅ Working | React captures frames → WS /live → Gemini |
| Desktop Automation (Tools) | ✅ Working | All ~60 tools functional via `/execute` (when called) |
| Brain/Cognitive Pipeline | ⚠️ Partial | Rule/heuristic-based; no LLM; no learning |
| AI Manager (Routing) | ✅ Working | Sophisticated rule-based routing; produces TaskRoute |
| Memory (Conversation) | ⚠️ Partial | In-memory ring buffer (`conversation_bus.ts`); persistence disabled |
| Memory (Semantic) | ❌ Missing | `server_memory.ts` write commented out; no long-term storage |
| Finance (Advisory) | ⚠️ Partial | YahooProvider broken; no historical data; no indicators |
| Trading (Execution) | ❌ Missing | Advisory only; no order execution (by design) |
| Research (Web) | ❌ Missing | No `/research` endpoint; no Tavily integration; no web research tool |
| Coding (Execution) | ✅ Working | `createPythonFile`, `runPythonScript`, etc. functional |
| Creation (Docs/PPT/Excel) | ⚠️ Partial | Tools registered but dependent on external software (Office) |
| NX Engineering | ❌ Missing | No actual NX tools; capability registered but inert |
| System Diagnostics | ⚠️ Partial | Tools like `systemInfo` work; no deep diagnostics |
| Permission/Gating | ⚠️ Partial | Two-step confirmation works for gated actions; PermissionManager no-op |
| Telemetry | ❌ Missing | No telemetry instrumentation in Python or Node |
| Health Checks | ✅ Working | `/health`, `/health/ready` endpoints functional |
| Settings/Persistence | ✅ Working | Node `settings.json` persisted; Python settings from env |
| UI (Electron Shell) | ✅ Working | Animated companion, wake-word, settings panel |
| Tests | ⚠️ Partial | Python pytest for tools/finance; many stubs; no TS tests |

## 14. Recommended Next Sequence (Post-Audit)

Given the audit-only constraint, we **do not implement**. However, for future work, the sequence should be:

1. **Fix Critical Disconnections**
   - Wire Node→Python desktop-tool dispatch in `server.ts` (remove stub, call `callDesktopAgent`).
   - Enable memory persistence in `server_memory.ts` (uncomment `fs.writeFile`).
   - Fix YahooProvider field mismatch or replace with working provider.
   - Implement PermissionManager with real policy engine (use confirmation token as backend).

2. **Enable LLM Reasoning in Brain**
   - Modify `BrainEngine.process()` to invoke LLM providers based on AIManager route.
   - Use `execution_mode` and `reasoning_depth` to control LLM parameters (temperature, max_tokens, etc.).
   - Ensure route.provider_preference is respected.

3. **Enhance AIManager with Context & Uncertainty**
   - Pass conversation memory, project state, screen state, etc. into `_extract_task_signals`.
   - Replace heuristic confidence with calibrated probabilities (e.g., via Platt scaling on validation set).
   - Add ROUTE/CLARIFY/ESCALATE/ABSTAIN decision thresholds based on confidence and entropy.

4. **Wire Research and Trading Pipelines**
   - Register actual `web_research` tool (wrapper around Tavily/HTTP).
   - Implement ResearchOrchestrator that uses the capability.
   - Fix trading data pipeline (historical data, indicators) or disconnect advisory from broken components (label as stub).

5. **Improve Generalization and Hinglish Support**
   - Expand intent patterns with synonyms and paraphrase patterns (lightweight).
   - Improve hinglish verb mapping and possibly integrate a transliteration layer.
   - Consider adding a small intent classification model (e.g., distilbert) fallback for low-confidence cases.

6. **Decompose Multi-Intent Requests**
   - Extend AIManager to detect multiple intents and output a task graph (list of subtasks with dependencies).
   - Orchestrator to execute subtasks in order, passing intermediate results.

7. **Add Telemetry and Feedback Loop**
   - Instrument keypaths (routing, tool execution, LLM calls) with latency, success/failure, user feedback.
   - Use telemetry to drive periodic model updates and confidence calibration.

8. **Validate and Iterate**
   - Run end-to-end tests for common scenarios (voice command → tool execution).
   - Measure user satisfaction and correctness; adjust routing thresholds and confidence models.
   - Gradually enable more sophisticated reasoning as components stabilize.

---

## 15. Dependency Graph (Simplified)

```
[User Voice/Text]
         ↓
[Node: WS /live] ←→ [Gemini Live (STT/TTS/Vision)]
         ↓
[Node: POST /brain/python] ──► [Python Desktop Agent: /brain]
         ↓
[BrainEngine] ←→ [AI Manager: route()] ←→ (context, memory, etc. currently missing)
         ↓
[BrainEngine: rule-based reasoning ONLY]  ←→  (NO LLM INVOCATION)
         ↓
[ExecutionBrain / Orchestrator] ←→ [Tool Dispatcher: CommandDispatcher]
         ↓
[Desktop Tools: pyautogui/Playwright/win32/PIL] ←→ [Windows OS]
         ↓
[User Action/Feedback]
```
*Note: The dashed line indicates the missing LLM invocation that should occur between AIManager route and Brain reasoning.*

## 16. Final Notes

This audit adheres strictly to the **audit-only** constraint: no code was modified, no files were written or deleted, no tests were changed, and no implementation was started. All conclusions are derived from static analysis of the provided source code and documentation.

The MYRAA system demonstrates impressive engineering in desktop automation and voice/vision integration but lacks the core AI components (LLM-driven reasoning, learning, uncertainty-aware routing) necessary to evolve into a true JARVIS-like Super-Brain. The AIManager itself is a well-designed rule-based router that could be adapted to an LLM-mediated architecture with relatively focused changes in context handling, LLM invocation, and uncertainty calibration.

**End of Audit**.