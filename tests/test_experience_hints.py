"""B20 closed loop: experience hints feed planning as advisory context.

Covers the learning→planning seam wired in SuperBrain.process →
MasterPlanner.create_goal_plan(goal, experience_hints=...):

- hints surface only verified successful tool sequences (never failures,
  never unverified runs, never empty capability)
- plans carry hints as observed context (metadata + to_dict) WITHOUT
  changing deterministic step construction
- missing hints degrade to [] (backward compatible)

No network, models, microphone, or speaker required.
"""
from __future__ import annotations


def _goal(capability="BROWSER_ENGINE", text="open example site"):
    from desktop_agent.brain.super_brain.goal import Goal

    return Goal(text=text, capability=capability, confidence=0.9)


def _exp(capability, tools, *, success=True, verified=True):
    from desktop_agent.brain.super_brain.experience import Experience

    return Experience(
        request_id="r1",
        goal_text="g",
        capability=capability,
        success=success,
        tool_sequence=list(tools),
        verified=verified,
    )


def test_hint_for_returns_best_verified_sequence():
    from desktop_agent.brain.super_brain.experience import ExperienceEngine

    eng = ExperienceEngine()
    eng.record(_exp("BROWSER_ENGINE", ["desktopBrowserOpen"]))
    eng.record(_exp("BROWSER_ENGINE", ["desktopBrowserOpen", "desktopBrowserSearch"]))
    eng.record(_exp("BROWSER_ENGINE", ["desktopBrowserOpen", "desktopBrowserSearch"]))
    assert eng.hint_for("BROWSER_ENGINE") == ["desktopBrowserOpen", "desktopBrowserSearch"]


def test_hint_for_ignores_failures_unverified_and_empty():
    from desktop_agent.brain.super_brain.experience import ExperienceEngine

    eng = ExperienceEngine()
    assert eng.hint_for("BROWSER_ENGINE") == []
    assert eng.hint_for("") == []
    eng.record(_exp("BROWSER_ENGINE", ["badTool"], success=False, verified=True))
    eng.record(_exp("BROWSER_ENGINE", ["unverifiedTool"], success=True, verified=False))
    assert eng.hint_for("BROWSER_ENGINE") == []


def test_plan_without_hints_is_backward_compatible():
    from desktop_agent.brain.super_brain.planner import MasterPlanner

    plan = MasterPlanner().create_goal_plan(_goal())
    assert plan.experience_hints == []
    assert plan.plan.metadata.get("experience_hints") == []
    assert plan.to_dict()["experience_hints"] == []
    assert len(plan.steps) >= 1  # deterministic construction unaffected


def test_plan_carries_hints_as_observed_context_only():
    from desktop_agent.brain.super_brain.experience import ExperienceEngine
    from desktop_agent.brain.super_brain.planner import MasterPlanner

    eng = ExperienceEngine()
    eng.record(_exp("BROWSER_ENGINE", ["desktopBrowserOpen", "desktopBrowserSearch"]))
    hints = eng.hint_for("BROWSER_ENGINE")

    planner = MasterPlanner()
    plain = planner.create_goal_plan(_goal())
    hinted = planner.create_goal_plan(_goal(), experience_hints=hints)

    assert hinted.experience_hints == ["desktopBrowserOpen", "desktopBrowserSearch"]
    assert hinted.plan.metadata["experience_hints"] == hints
    assert hinted.to_dict()["experience_hints"] == hints
    # Same deterministic steps with or without hints — hints never steer
    # construction, they are observed context for executor/telemetry.
    assert [s.name for s in hinted.steps] == [s.name for s in plain.steps]
    assert [s.tool if hasattr(s, "tool") else s.name for s in hinted.steps] == \
           [s.tool if hasattr(s, "tool") else s.name for s in plain.steps]
