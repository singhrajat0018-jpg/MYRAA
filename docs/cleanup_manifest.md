# MYRAA — Cleanup Manifest (Phase U.2)

Evidence-based classification. Only J/H/I classes were removed; everything
else is kept and documented. `git` history preserves all pre-cleanup state.

Metrics before → after:
- Python files: 907 → 866 (41 removed: 40 zero-byte dead scaffolds + 1 mis-path dup)
- 0-byte py files: 117 → 77 (all remaining are `__init__.py` package markers or referenced/UNKNOWN)
- Root generated reports removed: 8 (performance_audit_*.json, eval_output*.txt,
  epic13_audit.txt, temp_audit_summary.txt, FINAL_AUDIT_OUTPUT.txt, security_report.txt)

## Removed (BATCH 1 — class J: empty + zero references, verified via git grep)
| Path | Rationale |
|---|---|
| brain/autonomy/{curiosity_engine,opportunity_detector}.py | 0-byte, 0 refs; AutonomyController lives in super_brain |
| brain/knowledge/{analyzer,cache,graph,indexer,providers,scanner,search}/* (18) | 0-byte scaffolds superseded by live knowledge services wired via app_context + research_router |
| brain/observer/observers/{battery,internet,pc_health,weather}_observer.py | 0-byte stubs; ObserverManager registry-driven, only stock+screen registered |
| brain/planner/{memory/*,goal_context,plan_validator}.py | 0-byte; canonical planner is brain/planner/planner.py + subpackage |
| brain/thinking/internal_dialogue.py | 0-byte; ThinkingEngine canonical elsewhere in thinking/ |
| desktop/vision/analyzers/office.py, vision/image_matcher.py | 0-byte; screen_analyzer imports .generic explicitly, no dynamic loader |
| runtime/{autonomy_runtime,desktop_runtime,perception_loop,runtime_events}.py | 0-byte; RuntimeManager/BrainBridge are the real runtime layer |
| desktop_agent/tests/{automation,desktop,stress,vision,voice}_test.py, utils.py | 0-byte test scaffolds |

## Removed (BATCH 2 — class K: generated output reports, distinctive names, 0 code refs)

## Deliberately KEPT (with classification)
| Item | Class | Reason |
|---|---|---|
| All `__init__.py` (incl. now-empty) | A/CANONICAL | package markers; removal breaks imports |
| brain/knowledge intelligence SearchOrchestrator/KnowledgeRouter | H-candidate→DORMANT | non-empty dead code per audit; removal requires migration cycle — documented for next batch |
| semantic/entity_extractor/* empties | UNKNOWN→KEEP | generic stems caused false-positive ref hits; real contract unclear |
| vision/analyzers/{browser,desktop,explorer,settings,vscode}.py empties | UNKNOWN→KEEP | same false-positive risk; explicit-import audit needed first |
| root *.png debug artifacts (~14) | K/UNKNOWN→KEEP | basenames collide with real modules (crop, gray, frame_difference) — cannot prove unreferenced cheaply |
| notifications/ | G/DORMANT | Phase-K candidate; unreachable today, intentional future seam |
| world_model/ top-level package | C/DORMANT | reachable via skills/world_model_bridge (multi-agent capability path) |
| design/, skills/, neural_engine/, self_healing/ | C | Phase-I/J/F frameworks; reachable via capability seam / REST; §14–§18 preserve rules |
| Node memories.json + server_memory.ts | B/UI-adapter | UI-facing memory authority (separate concern from Memory 2.0); ownership documented here |
| services/ai/*, services/voice/* (empty), backend/speech/{speech_service,transcript_bus}.ts | J→KEPT temporarily | public-ish module paths; removal deferred to a dedicated batch with import-graph proof (tsc barrel risk) |
| agent.log / agent_debug.log / logs/ / runtime/memory/*.json | K/RUNTIME-DATA | active runtime data — never delete (§26) |

## Duplicate-authority ledger (documented; consolidation status)
| Domain | Canonical | Others | Status |
|---|---|---|---|
| Request routing | TaskRouter | IntentRouter(action-map), ResponseRouter(capability), ai/router/ DEPRECATED | layered by design; legacy dir marked deprecated in-source |
| Planning | SuperBrain MasterPlanner → Planner | brain/planner.py + brain/decision_engine.py top-level legacy | LEGACY, unused — next-batch candidates |
| World model | brain/world_model.py (runtime) | desktop_agent/world_model/ (via skills bridge) | dual-layer documented |
| Conversational entry | AssistantRuntime | Brain facade (legacy compat, observers/autonomy internal) | compat retained |
| Voice transport | Gemini Live (Node) + ContinuousVoiceLoop state machine | services/voice/* empty scaffolds | scaffolds pending batch-3 |
