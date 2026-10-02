#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_agent.brain.ai import AIManager
from desktop_agent.brain.ai.context_snapshot import ContextSnapshot

SNAP = ContextSnapshot(
    conversation_relevance="user has been analyzing nifty trend",
    active_task="analyze nifty trend", active_app="Notepad",
    browser_summary="chrome with a stock analysis tab open",
    portfolio="reliance, tcs, infosys, hdfc bank",
    previous_request="analyze nifty trend",
    previous_route={"intent": "TRADING_ANALYSIS", "domain": "TRADING",
                    "output_type": "MARKET_ANALYSIS", "capability": "TRADING_ENGINE"},
)

qs = [
    "analyze nifty trend and monitor the volatility",
    "open notepad and type hello and minimize the window",
    "analyze nifty and recommend entry levels",
    "analyze the risks of investing in crypto",
    "when did world war 2 end",
    "advise on whether to sell my reliance holdings",
    "create a logo image for my startup",
    "teach me the basics of investing",
]
m = AIManager()
for q in qs:
    r = m.route(user_prompt=q, context=SNAP)
    s = m._extract_task_signals(q.lower())
    print("=" * 78)
    print("Q:", q)
    print("  entities:", sorted(s.entities), "| action:", sorted(s.action),
          "| topic:", sorted(s.topic), "| output:", sorted(s.requested_output),
          "| is_question:", s.is_question, "| modality:", s.modality)
    dom = m._detect_domain_candidates(s)
    print("  domain cands:", [(c.domain.name, round(c.confidence, 3)) for c in dom])
    print("  intent:", r.intent.name, "domain:", r.domain.name, "cap:", r.capability,
          "out:", r.output_type.name if r.output_type else None,
          "exec:", r.execution_mode.name, "reason:", r.reasoning_depth.name,
          "fresh:", r.freshness.name, "risk:", r.risk_level.name,
          "is_multi:", r.is_multi, "decision:", r.decision)