# MYRAA PLANNING ARCHITECTURE

Date: 2026-09-19. ONE planner family: canonical `Planner.create_plan`
(shared by BrainEngine + ExecutionBrain) wrapped by `MasterPlanner.
create_goal_plan` (same `ExecutionPlan`/`PlanStep` types + verification
metadata — wrapper, not fork).

## Plan representation

`PlannerGoal` → `PlanStep` (id, action, params, depends_on, retries,
timeout, rollback, verification, expected/actual) → `ExecutionPlan`
(status machine, progress, insert/remove) → `MasterPlan` (+ strategies,
fallback, capability_chain, dependencies, parallelizable, and — new this
pass — `experience_hints`).

## Execute → observe → replan

`Orchestrator.execute` (scheduler + ThreadPoolExecutor + retry/timeout/
rollback) → `ClosedLoopExecutor` (execute→observe→`_verify_goal`→replan,
bounded) → strategies resolved to REAL registered tools only (canonical
ids never reach the dispatcher — locked by test).

## Learning closes the loop (new)

`Experience.record` (success + verified tool sequences, mirrored to
Memory 2.0 best-effort) → `hint_for(capability)` → `create_goal_plan(...,
experience_hints=...)` → recorded on plan metadata + `to_dict` as
advisory context. Steps remain deterministic; hints never steer
construction or bypass authority. Covered by
tests/test_experience_hints.py (4 tests).

## Goal understanding

`Goal` carries outcome, constraints, dependencies, risks, deadlines,
success criteria (`super_brain/goal.py:31`). Ambiguity resolves via
confirmation gates, not guesses (destructive/uncertain → confirm/deny).
