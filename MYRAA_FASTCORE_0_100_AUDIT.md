# MYRAA FASTCORE 0→100 AUDIT

Date: 2026-09-19. Method: forensic read of live code (3 parallel research
passes + direct verification). Nothing assumed from filenames or prior docs.
Corrections to earlier claims are marked [CORRECTION].

## 1. What FastCore actually is

Two different things share the name — this is the root of most confusion:

- **Shipped FastCore = deterministic regex/keyword router**
  (`desktop_agent/fastcore/classifier.py:197`, "rule-based... <1ms... No LLM
  calls"). `classify(text)->FastCoreOutput` over a 12-phase cascade into
  15 TaskType × 5 Complexity × 5 ModelRoute + safety/confidence/tools.
  ACTIVE but narrowly scoped: exactly ONE live caller, `POST /brain/stream`
  (`main.py:1001-1004`). Never on `/brain`, `/execute`, or voice.
- **Trained FastCore = LoRA adapter (r8, Qwen3-0.6B base, 9.2MB ×4
  checkpoints) that is DORMANT**: well-formed weights on disk, zero
  production importers (`load_model/predict` live only in `evaluate.py`;
  classifier imports only re/typing). Protected/frozen by invariant — stays
  that way.

## 2. Cognitive map (current, verified per-stage)

USER → INPUT (text /brain, voice Gemini loop, observer events) →
PERCEPTION (`_resolve_input`, semantic parse; BrainEngine-only) →
CLASSIFY: `/brain` uses **TaskRouter** (`assistant_runtime.py:525`),
`/brain/stream` uses **FastCoreClassifier** (`main.py:1004`), voice uses
Gemini function routing (two competing classifiers coexist, one per
endpoint — documented debt, NOT merged: both tuned per path) →
REASONING: fast-path Ollama stream (AssistantRuntime, REAL LLM) or
SuperBrain route→goal→fuse→plan→strategies→safety→execute→meta →
MEMORY: UnifiedMemoryManager (9-stage governed `remember`; WORKING→
EPISODIC→SEMANTIC consolidation RUNS via RuntimeManager 60s daemon —
[CORRECTION] an earlier pass reported consolidation unwired; it IS wired
via `runtime_manager.py:124-204`) → PLANNING: canonical `Planner`
(shared by BrainEngine + ExecutionBrain) wrapped by `MasterPlanner`
(same ExecutionPlan type + verification metadata — wrapper, not fork) →
TOOL SELECTION: CapabilityOrchestrator strategies → PERMISSION:
CommandDispatcher ValidationLayer→PermissionManager→raw handler (sole
authority; finance FINANCIAL→deny) → ACTION → OBSERVATION: executor
verify + F7 → RESULT → MEMORY UPDATE: experience.record → REFLECTION:
meta_controller + ReflectionEngine.record (learn/reflect paths dormant) →
NEXT ACTION / RESPONSE.

Legacy/dead weight (inventory, NOT deleted): `brain/planner.py`,
`brain/decision_engine.py`, `GoalPlanner`, `ActionPlanner`,
`CognitiveCycle` (reflect is `pass`), skills `AgentPlanner`,
`IntentRouter`/`ResponseRouter` (BrainEngine-only paths), legacy
`MemoryManager` + spare `WorkingMemory`, `manager.reconnect()` /
`request_reconnect()` (no callers), module-level remember_* (test-only).

## 3. Memory authority verdict (§33)

Python `UnifiedMemoryManager` (myraa_brain_memory.json) is the
brain-authoritative store: governed writes, provenance enum (8 values),
confidence/importance/sensitivity, conflict + reinforcement audit,
lifecycle transitions, atomic persistence, periodic consolidation.
Node `memories.json` is UI-facing and diverged (no sync, different schema)
— unification is a product-level migration: DOCUMENTED, NOT attempted here
(rule: no second brain, no speculative rewrites; migration design belongs
in MYRAA_MEMORY_ARCHITECTURE.md).

## 4. Gaps found → disposition

- G1 learning→planning loop open (hints never consumed) → FIXED this pass
  (advisory `experience_hints` on MasterPlan + metadata + to_dict; zero
  execution change; 4 regression tests).
- G2 Node/Python memory divergence → documented, not migrated.
- G3 legacy duplicate planners/routers → inventoried, not deleted (import
  risk outweighs hygiene value; each deletion needs per-file proof).
- G4 reflection `learn()` paths dormant → documented; hints seam now live
  for future use.
- G5 stale docs ("BrainEngine never calls generate") → noted; CLAUDE.md
  line in question describes dead-path behavior — left to owner.

## 5. Non-goals honored

No second brain/planner/memory/router created. No provider swap (Ollama
fast-path + Gemini voice preserved; routing benchmark shows AIManager 4.1
intent 97%/domain 99% — model is not the bottleneck). No protected-system
changes (PermissionManager, finance firewall, FastCore weights, voice,
browser untouched — verified by scan + suites below).

## 6. Verification status

- New: tests/test_experience_hints.py 4 passed.
- Related: test_phase8_browser_integration, SuperBrain suites — rerun in
  final validation (see final report).
- Live-model behavior: Ollama-dependent paths NOT LIVE VERIFIED here.
