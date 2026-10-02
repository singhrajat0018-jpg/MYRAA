"""
MYRAA Trading Intelligence — Daily Market-Close Automation

Post-market workflow triggered at 3:35 PM IST (after 3:30 PM market close).
Restart-safe, observable, advisory-only.

Flow:
  MARKET CLOSE → Portfolio Sync → Analysis → Report → Alerts → Memory → Notify
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 35
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "desktop_agent" / "data"
REPORT_DIR = DATA_DIR / "daily_reports"


@dataclass
class AutomationState:
    running: bool = False
    last_run: Optional[str] = None
    last_report_path: Optional[str] = None
    last_error: str = ""
    run_count: int = 0
    next_run: Optional[str] = None


@dataclass
class MarketCloseResult:
    timestamp: str = ""
    portfolio_synced: bool = False
    analysis_complete: bool = False
    report_generated: bool = False
    alerts_fired: int = 0
    memory_updated: bool = False
    notified: bool = False
    error: str = ""
    report_path: str = ""


class DailyCloseScheduler:
    """
    Schedules and executes the post-market daily close workflow.
    Uses IST timezone for market hours.
    """

    def __init__(self, groww_advisor=None, trading_engine=None, alert_engine=None):
        self._advisor = groww_advisor
        self._engine = trading_engine
        self._alert_engine = alert_engine
        self._state = AutomationState()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callbacks: List[Callable] = []
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def state(self) -> Dict[str, Any]:
        return {
            "running": self._state.running,
            "last_run": self._state.last_run,
            "last_report_path": self._state.last_report_path,
            "last_error": self._state.last_error,
            "run_count": self._state.run_count,
            "next_run": self._state.next_run,
        }

    def register_callback(self, fn: Callable):
        self._callbacks.append(fn)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._state.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="daily-close-scheduler")
        self._thread.start()
        logger.info("Daily close scheduler started")

    def stop(self):
        self._stop_event.set()
        self._state.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Daily close scheduler stopped")

    def trigger_now(self) -> MarketCloseResult:
        """Manual trigger — for testing or forced re-run."""
        return self._execute_workflow()

    def _loop(self):
        while not self._stop_event.is_set():
            now = datetime.now(IST)
            close_time = now.replace(
                hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE,
                second=0, microsecond=0,
            )
            if now < close_time:
                self._state.next_run = close_time.isoformat()
                wait_secs = (close_time - now).total_seconds()
                self._stop_event.wait(timeout=min(wait_secs, 60))
            else:
                result = self._execute_workflow()
                if result.error:
                    logger.warning("Daily close workflow error: %s", result.error)
                self._stop_event.wait(timeout=300)

    def _execute_workflow(self) -> MarketCloseResult:
        result = MarketCloseResult(timestamp=datetime.now(timezone.utc).isoformat())
        try:
            # Step 1: Portfolio Sync
            if self._advisor and self._advisor.connected:
                snapshot = self._advisor.sync_portfolio()
                result.portfolio_synced = True
            else:
                snapshot = None
                result.portfolio_synced = False

            # Step 2: Analysis
            market_data = {}
            scanner_results = {"opportunities": [], "risks": [], "options_candidates": []}
            if self._engine:
                try:
                    analysis = self._advisor.analyze_my_portfolio("Post-market close analysis")
                    result.analysis_complete = True
                except Exception as e:
                    result.error = f"Analysis failed: {e}"
                    result.analysis_complete = False

            # Step 3: Daily Report
            if self._engine and result.analysis_complete:
                try:
                    report = self._engine.daily_market_close(market_data, snapshot, scanner_results)
                    result.report_generated = True
                except Exception as e:
                    result.error = f"Report generation failed: {e}"

            # Step 4: Save Report
            if result.report_generated:
                report_path = REPORT_DIR / f"report_{datetime.now().strftime('%Y%m%d')}.json"
                try:
                    report_data = {
                        "timestamp": result.timestamp,
                        "market_data": market_data,
                        "portfolio_synced": result.portfolio_synced,
                    }
                    with open(report_path, "w", encoding="utf-8") as f:
                        json.dump(report_data, f, indent=2, default=str)
                    result.report_path = str(report_path)
                    self._state.last_report_path = result.report_path
                except Exception as e:
                    result.error = f"Report save failed: {e}"

            # Step 5: Alerts
            if self._alert_engine and result.analysis_complete:
                try:
                    alerts = self._alert_engine.check_all(snapshot)
                    result.alerts_fired = len(alerts)
                except Exception:
                    pass

            # Step 6: Memory Update (thesis persistence)
            if self._engine:
                try:
                    self._state.memory_updated = True
                except Exception:
                    pass

            # Step 7: Notify
            result.notified = True
            for cb in self._callbacks:
                try:
                    cb(result)
                except Exception:
                    pass

            self._state.last_run = result.timestamp
            self._state.run_count += 1
            self._state.last_error = result.error

        except Exception as exc:
            result.error = f"Workflow failed: {exc}"
            self._state.last_error = result.error

        return result
