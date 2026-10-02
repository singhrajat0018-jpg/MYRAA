# MYRAA REASONING ARCHITECTURE

Date: 2026-09-19. Honest account: MYRAA reasons by cascade, not by
exposed chain-of-thought — and that is a security property (no hidden
reasoning ever reaches tools or users; only conclusions, assumptions,
and uncertainty surface).

## How conclusions are actually reached

1. Deterministic cascade (TaskRouter / FastCoreClassifier / AIManager
   signals→patterns→overrides): intent, domain, capability, complexity,
   risk — all rule-based, all tested (4.1: intent 97.03%, domain 99.01%).
2. Decision strategies (`DecisionEngine._select_strategy`): MULTI_STEP→
   PLAN, VISION/CODE→REASON, DELETE/SYSTEM→CONFIRM, default DIRECT.
3. Bounded LLM reasoning where it pays: fast-path conversation stream,
   research synthesis — never for authorization (PermissionManager decides
   alone) and never for tool selection on the `/execute` rail.
4. Uncertainty handling: calibrated confidence (Brier 0.0524), escalate
   <0.8, confirm/deny gates, contradiction penalties in memory.

## What is NOT claimed

No explicit causal/abductive/counterfactual engine exists as a module;
comparison, constraint, and temporal reasoning live inside planners,
validators, and the recovery taxonomy (F6/F7). The §9 wishlist is mapped
to these real mechanisms rather than invented components.

## Verification over cleverness

Every reasoning output that acts is checked: plan verification strategies
(B13), executor `_verify_goal` with replan (max 2), CommandDispatcher
gates, F7 recovery taxonomy. A wrong conclusion fails safe.
