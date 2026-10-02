"""
MYRAA Trading Intelligence — Proactive Alerts Engine

User-configurable alerts. Advisory only — no automatic trade execution.
Alerts are generated when conditions are met and stored for notification.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from desktop_agent.finance.trading.models import PortfolioSnapshot

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "desktop_agent" / "data"
ALERTS_FILE = DATA_DIR / "trading_alerts.json"


@dataclass
class AlertRule:
    rule_id: str
    alert_type: str  # portfolio_movement, drawdown, breakout, breakdown, volume, key_level, news, iv_spike, thesis_invalidation, target_reached, report_ready
    symbol: str = ""
    threshold: float = 0.0
    direction: str = "above"  # above / below / change
    enabled: bool = True
    description: str = ""
    created_at: str = ""


@dataclass
class Alert:
    alert_id: str
    rule_id: str
    alert_type: str
    symbol: str
    message: str
    severity: str  # INFO, WARNING, CRITICAL
    timestamp: str
    data: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


class AlertEngine:
    """
    Manages alert rules and checks conditions against live portfolio data.
    Advisory only — never executes trades.
    """

    def __init__(self):
        self._rules: List[AlertRule] = []
        self._fired: List[Alert] = []
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []
        self._load_rules()

    @property
    def state(self) -> Dict[str, Any]:
        return {
            "rules_count": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
            "alerts_fired": len(self._fired),
            "unacknowledged": sum(1 for a in self._fired if not a.acknowledged),
        }

    def register_callback(self, fn: Callable):
        self._callbacks.append(fn)

    def add_rule(self, rule: AlertRule):
        with self._lock:
            rule.created_at = datetime.now(timezone.utc).isoformat()
            self._rules.append(rule)
            self._save_rules()

    def remove_rule(self, rule_id: str):
        with self._lock:
            self._rules = [r for r in self._rules if r.rule_id != rule_id]
            self._save_rules()

    def get_rules(self) -> List[Dict[str, Any]]:
        return [
            {"rule_id": r.rule_id, "alert_type": r.alert_type, "symbol": r.symbol,
             "threshold": r.threshold, "direction": r.direction, "enabled": r.enabled,
             "description": r.description}
            for r in self._rules
        ]

    def get_alerts(self, limit: int = 50, unacknowledged_only: bool = False) -> List[Dict[str, Any]]:
        alerts = self._fired
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return [
            {"alert_id": a.alert_id, "rule_id": a.rule_id, "alert_type": a.alert_type,
             "symbol": a.symbol, "message": a.message, "severity": a.severity,
             "timestamp": a.timestamp, "data": a.data, "acknowledged": a.acknowledged}
            for a in alerts[-limit:]
        ]

    def acknowledge(self, alert_id: str):
        for a in self._fired:
            if a.alert_id == alert_id:
                a.acknowledged = True
                break

    def check_all(self, snapshot: Optional[PortfolioSnapshot]) -> List[Alert]:
        fired = []
        if snapshot:
            fired.extend(self._check_portfolio_movement(snapshot))
            fired.extend(self._check_drawdown(snapshot))
            fired.extend(self._check_key_levels(snapshot))
            fired.extend(self._check_target_reached(snapshot))
        return fired

    def _check_portfolio_movement(self, snapshot: PortfolioSnapshot) -> List[Alert]:
        alerts = []
        for rule in self._rules:
            if not rule.enabled or rule.alert_type != "portfolio_movement":
                continue
            for pos in snapshot.positions:
                if rule.symbol and pos.symbol != rule.symbol:
                    continue
                if abs(pos.day_change_percent) >= rule.threshold:
                    alert = Alert(
                        alert_id=f"pm_{rule.rule_id}_{pos.symbol}",
                        rule_id=rule.rule_id,
                        alert_type="portfolio_movement",
                        symbol=pos.symbol,
                        message=f"{pos.symbol} moved {pos.day_change_percent:+.2f}% (threshold: {rule.threshold}%)",
                        severity="WARNING" if abs(pos.day_change_percent) > 5 else "INFO",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        data={"day_change": pos.day_change_percent, "threshold": rule.threshold},
                    )
                    alerts.append(alert)
                    self._fire(alert)
        return alerts

    def _check_drawdown(self, snapshot: PortfolioSnapshot) -> List[Alert]:
        alerts = []
        for rule in self._rules:
            if not rule.enabled or rule.alert_type != "drawdown":
                continue
            if snapshot.total_pnl_percent < -rule.threshold:
                alert = Alert(
                    alert_id=f"dd_{rule.rule_id}",
                    rule_id=rule.rule_id,
                    alert_type="drawdown",
                    symbol="PORTFOLIO",
                    message=f"Portfolio drawdown {snapshot.total_pnl_percent:.1f}% exceeds threshold {rule.threshold}%",
                    severity="CRITICAL" if snapshot.total_pnl_percent < -10 else "WARNING",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    data={"drawdown_pct": snapshot.total_pnl_percent, "threshold": rule.threshold},
                )
                alerts.append(alert)
                self._fire(alert)
        return alerts

    def _check_key_levels(self, snapshot: PortfolioSnapshot) -> List[Alert]:
        alerts = []
        for rule in self._rules:
            if not rule.enabled or rule.alert_type != "key_level":
                continue
            for pos in snapshot.positions:
                if rule.symbol and pos.symbol != rule.symbol:
                    continue
                if rule.direction == "above" and pos.current_price >= rule.threshold:
                    alert = Alert(
                        alert_id=f"kl_{rule.rule_id}_{pos.symbol}",
                        rule_id=rule.rule_id,
                        alert_type="key_level",
                        symbol=pos.symbol,
                        message=f"{pos.symbol} reached {pos.current_price:.2f} (above {rule.threshold})",
                        severity="INFO",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        data={"price": pos.current_price, "level": rule.threshold},
                    )
                    alerts.append(alert)
                    self._fire(alert)
                elif rule.direction == "below" and pos.current_price <= rule.threshold:
                    alert = Alert(
                        alert_id=f"kl_{rule.rule_id}_{pos.symbol}",
                        rule_id=rule.rule_id,
                        alert_type="key_level",
                        symbol=pos.symbol,
                        message=f"{pos.symbol} dropped to {pos.current_price:.2f} (below {rule.threshold})",
                        severity="WARNING",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        data={"price": pos.current_price, "level": rule.threshold},
                    )
                    alerts.append(alert)
                    self._fire(alert)
        return alerts

    def _check_target_reached(self, snapshot: PortfolioSnapshot) -> List[Alert]:
        alerts = []
        for rule in self._rules:
            if not rule.enabled or rule.alert_type != "target_reached":
                continue
            for pos in snapshot.positions:
                if rule.symbol and pos.symbol != rule.symbol:
                    continue
                if pos.average_price > 0:
                    gain_pct = (pos.current_price - pos.average_price) / pos.average_price * 100
                    if gain_pct >= rule.threshold:
                        alert = Alert(
                            alert_id=f"tr_{rule.rule_id}_{pos.symbol}",
                            rule_id=rule.rule_id,
                            alert_type="target_reached",
                            symbol=pos.symbol,
                            message=f"{pos.symbol} target reached: +{gain_pct:.1f}% (threshold: +{rule.threshold}%)",
                            severity="INFO",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            data={"gain_pct": gain_pct, "threshold": rule.threshold},
                        )
                        alerts.append(alert)
                        self._fire(alert)
        return alerts

    def fire_report_ready(self, report_path: str):
        alert = Alert(
            alert_id=f"rr_{datetime.now().strftime('%Y%m%d')}",
            rule_id="system",
            alert_type="report_ready",
            symbol="",
            message=f"Daily market close report ready: {report_path}",
            severity="INFO",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"report_path": report_path},
        )
        self._fire(alert)

    def fire_thesis_invalidation(self, symbol: str, reason: str):
        alert = Alert(
            alert_id=f"ti_{symbol}_{datetime.now().strftime('%Y%m%d%H%M')}",
            rule_id="system",
            alert_type="thesis_invalidation",
            symbol=symbol,
            message=f"Thesis invalidated for {symbol}: {reason}",
            severity="WARNING",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"reason": reason},
        )
        self._fire(alert)

    def _fire(self, alert: Alert):
        with self._lock:
            exists = any(a.alert_id == alert.alert_id for a in self._fired)
            if not exists:
                self._fired.append(alert)
                for cb in self._callbacks:
                    try:
                        cb(alert)
                    except Exception:
                        pass

    def _load_rules(self):
        try:
            if ALERTS_FILE.exists():
                with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for r in data.get("rules", []):
                    self._rules.append(AlertRule(**r))
        except Exception:
            pass
        if not self._rules:
            self._rules = [
                AlertRule("r1", "portfolio_movement", threshold=3.0, description="Alert on 3%+ stock move"),
                AlertRule("r2", "drawdown", threshold=5.0, description="Alert on 5%+ portfolio drawdown"),
                AlertRule("r3", "report_ready", description="Daily report notification"),
            ]

    def _save_rules(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = {"rules": [
                {"rule_id": r.rule_id, "alert_type": r.alert_type, "symbol": r.symbol,
                 "threshold": r.threshold, "direction": r.direction, "enabled": r.enabled,
                 "description": r.description, "created_at": r.created_at}
                for r in self._rules
            ]}
            with open(ALERTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
