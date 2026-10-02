# MYRAA COGNITIVE ARCHITECTURE

Date: 2026-09-19. ONE cognitive authority: shared singletons
(`application_container.py:85-226` — one Blackboard, Planner,
DecisionEngine, Orchestrator, UnifiedMemoryManager, AIManager) consumed by
three pipeline facades (AssistantRuntime front door, SuperBrain full path,
ExecutionBrain tool path). No second brain created by this evolution.

## Tiers (as built, not aspirational)

- FAST PATH: TaskRouter/FastCore classify → Ollama `stream_generate`
  direct (`assistant_runtime.py:284-303`). Smallest sufficient compute for
  conversation.
- REASONING PATH: SuperBrain route→goal→fuse→plan→strategies→safety→
  closed-loop execute→meta→experience (`super_brain.py:160-299`).
- DIRECT PATH: `/execute` validation→permission→handler→verify
  (`execution_brain.py:655-678`). Zero-LLM tool rail.
- VOICE PATH: Gemini Live loop with tool router (unchanged).

## Uncertainty (represented, not vibes)

Confidence fields on FastCoreOutput, TaskRoute (4.1 calibrated: Brier
0.0524 post-Platt), MemoryRecord, plans. Thresholds with teeth: escalate
<0.8 (FastCore), confirm tokens (PermissionManager), FINANCIAL→deny.
Unknowns surface as clarification/confirmation, not guesses — enforced by
gates, not guidelines.

## Attention / proactivity (honest status)

`attention.submit` receives observer events (`brain_engine.py:1607`);
AutonomyLoop learn/reflect are policy-gated (`can_learn`, `can_reflect`)
but the loop is never started in prod. No explicit AttentionBudget class
exists — proactivity today = bounded observer→event→record + 60s
consolidation daemon. A budget/policy object is future work, not claimed.

## Meta-cognition (what runs)

`meta_controller.decide` post-execution + `ReflectionEngine.record`
(via `_post_process` and execution coordinator). `learn()`/`reflect()`
entry points exist but are dormant; the live learning signal is
experience.record → hint_for → plan hints (wired this pass).
