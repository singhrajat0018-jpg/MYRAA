#!/usr/bin/env python3
"""Per-item held-out diagnostic: dump every item with its predicted vs
expected labels for all routing dimensions, plus a summary of the most
regressed dimensions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.brain.ai import AIManager
from desktop_agent.brain.ai.context_snapshot import ContextSnapshot

HERE = Path(__file__).resolve().parent

_DEFAULT_SNAPSHOT = ContextSnapshot(
    conversation_relevance="user has been analyzing nifty trend",
    active_task="analyze nifty trend",
    active_app="Notepad",
    browser_summary="chrome with a stock analysis tab open",
    portfolio="reliance, tcs, infosys, hdfc bank",
    previous_request="analyze nifty trend",
    previous_route={"intent": "TRADING_ANALYSIS", "domain": "TRADING",
                    "output_type": "MARKET_ANALYSIS", "capability": "TRADING_ENGINE"},
)


def snapshot_for(item):
    if item.get("category") == "CONTEXTUAL":
        return _DEFAULT_SNAPSHOT
    return None


def main():
    held = json.loads((HERE / "ai_manager_41_held_out.json").read_text(encoding="utf-8"))
    manager = AIManager()
    dims = ["intent", "domain", "capability", "output_type", "execution_mode",
            "reasoning_depth", "freshness", "risk_level"]
    fail_by_dim = {d: [] for d in dims}
    for i, item in enumerate(held):
        r = manager.route(user_prompt=item["request"], context=snapshot_for(item))
        row = {
            "i": i,
            "req": item["request"],
            "lang": item["language"],
            "cat": item.get("category", "?"),
        }
        for d in dims:
            val = getattr(r, d)
            pred = val.name if hasattr(val, "name") else (val or "")
            row[f"{d}_exp"] = item[d]
            row[f"{d}_got"] = pred
            if pred != item[d]:
                fail_by_dim[d].append(row)
        row["tools_expected"] = item.get("tools_required") or []
        row["tools_got"] = r.tools_required or []
        row["tool_hit"] = 1 if set(row["tools_got"]) & set(
            item.get("tools_required") or []) else 0
        row["is_multi_exp"] = bool(item.get("multi_intent"))
        row["is_multi_got"] = r.is_multi
        row["decision"] = getattr(r, "decision", None)
        row["expected_decision"] = item.get("expected_decision")
        row["conf"] = round(r.calibrated_confidence, 3)

    out = {"held_count": len(held), "fail_by_dim": fail_by_dim}
    (HERE / "diag_heldout.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    for d in dims:
        fails = fail_by_dim[d]
        print(f"\n=== {d.upper()} failures: {len(fails)} ===")
        for f in fails:
            print(f"[{f['i']:3d}] ({f['lang']:7s}/{f['cat']:11s}) "
                  f"{f['req'][:60]!r} -> {f[d+'_got']!s} exp {f[d+'_exp']!s}")


if __name__ == "__main__":
    main()