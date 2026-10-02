#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_agent.brain.ai import AIManager
from desktop_agent.brain.ai.context_snapshot import ContextSnapshot

qs = [
    "advise on whether to sell my reliance holdings",
    "analyze nifty trend and monitor the volatility",
]
m = AIManager()
for q in qs:
    print("=" * 90)
    print("Q:", q)
    r = m.route(user_prompt=q, context=None)
    print("RESULT intent:", r.intent.name, "domain:", r.domain.name, "decision:", r.decision,
          "is_multi:", r.is_multi, "cal:", round(r.calibrated_confidence, 3),
          "score:", round(r.route_score, 3), "flags:", r.uncertainty_flags)
    print("  component_scores:", r.component_scores)
    print("  confidence_reason:", r.confidence_reason)
    print("  sub_tasks:", r.sub_tasks)
    print("  alternatives:", r.alternative_routes)
    print("  EXPLANATION:", r.explanation)