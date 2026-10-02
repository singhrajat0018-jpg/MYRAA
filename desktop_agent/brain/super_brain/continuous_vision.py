"""
MYRAA Phase 3.4 — Continuous Vision Controller.

Consumes ScreenShareEngine directly as the single capture authority.
Adds frame health tracking, stale detection, change detection, and
integration with ContextFusion/SuperBrain.

NOT a second vision architecture. It is a consumer that:
  - reads frames from ScreenShareEngine (single capture authority)
  - tracks frame health metrics
  - detects stale/stale frames
  - suppresses duplicate visual context
  - feeds structured vision state to ContextFusion
  - provides visual evidence to SuperBrain for action verification
  - enforces loop guards for visual polling

VISION = perception + visual verification.
VISION is NOT a brain, planner, or autonomy engine.
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


# ================================================================
# Vision State
# ================================================================

class VisionStatus(str, Enum):
    """High-level vision pipeline status."""
    IDLE = "idle"
    CAPTURING = "capturing"
    ANALYZING = "analyzing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    STOPPED = "stopped"


# ================================================================
# Frame Health
# ================================================================

@dataclass
class FrameHealth:
    """Tracks actual frame delivery health."""
    total_frames: int = 0
    valid_frames: int = 0
    dropped_frames: int = 0
    stale_frames: int = 0
    last_frame_time: float = 0.0
    last_analysis_time: float = 0.0
    last_valid_frame_time: float = 0.0
    provider_errors: int = 0
    reconnect_count: int = 0
    processing_latencies: List[float] = field(default_factory=list)
    _max_latencies: int = 100

    @property
    def avg_latency_ms(self) -> float:
        if not self.processing_latencies:
            return 0.0
        return sum(self.processing_latencies) / len(self.processing_latencies)

    @property
    def frame_age_s(self) -> float:
        if self.last_valid_frame_time <= 0:
            return float("inf")
        return time.time() - self.last_valid_frame_time

    @property
    def is_stale(self) -> bool:
        """True if no valid frame in last 10 seconds."""
        return self.frame_age_s > 10.0

    @property
    def drop_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return self.dropped_frames / self.total_frames

    def record_frame(self, valid: bool, latency_ms: float = 0.0) -> None:
        self.total_frames += 1
        now = time.time()
        self.last_frame_time = now
        if valid:
            self.valid_frames += 1
            self.last_valid_frame_time = now
        else:
            self.dropped_frames += 1
        if latency_ms > 0:
            self.processing_latencies.append(latency_ms)
            if len(self.processing_latencies) > self._max_latencies:
                self.processing_latencies = self.processing_latencies[-self._max_latencies:]

    def record_stale(self) -> None:
        self.stale_frames += 1

    def record_error(self) -> None:
        self.provider_errors += 1

    def record_reconnect(self) -> None:
        self.reconnect_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_frames": self.total_frames,
            "valid_frames": self.valid_frames,
            "dropped_frames": self.dropped_frames,
            "stale_frames": self.stale_frames,
            "frame_age_s": round(self.frame_age_s, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "drop_rate": round(self.drop_rate, 3),
            "provider_errors": self.provider_errors,
            "reconnect_count": self.reconnect_count,
            "last_frame_time": self.last_frame_time,
            "last_valid_frame_time": self.last_valid_frame_time,
            "last_analysis_time": self.last_analysis_time,
        }


# ================================================================
# Visual State (structured output for ContextFusion)
# ================================================================

@dataclass
class VisualState:
    """Structured visual state produced by continuous vision."""
    application: str = ""
    window_title: str = ""
    page_type: str = ""
    ui_targets: List[Dict[str, Any]] = field(default_factory=list)
    visual_state: str = ""
    confidence: float = 0.0
    timestamp: float = 0.0
    frame_id: int = 0
    has_error: bool = False
    error_text: str = ""
    changed: bool = False
    change_regions: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "application": self.application,
            "window_title": self.window_title,
            "page_type": self.page_type,
            "ui_targets_count": len(self.ui_targets),
            "visual_state": self.visual_state,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "frame_id": self.frame_id,
            "has_error": self.has_error,
            "error_text": self.error_text[:200] if self.error_text else "",
            "changed": self.changed,
            "change_regions_count": len(self.change_regions),
        }

    def to_context_dict(self) -> Dict[str, Any]:
        """Slim context for ContextFusion injection."""
        return {
            "application": self.application,
            "window_title": self.window_title,
            "page_type": self.page_type,
            "visual_state": self.visual_state,
            "confidence": round(self.confidence, 3),
            "has_error": self.has_error,
            "changed": self.changed,
        }


# ================================================================
# Continuous Vision Controller
# ================================================================

class ContinuousVisionController:
    """
    Monitors ScreenShareEngine output, tracks frame health, detects
    stale frames, produces structured VisualState, and integrates
    with ContextFusion/SuperBrain.

    Phase 3.4: Consumes ScreenShareEngine directly (single capture authority).
    NOT a second vision pipeline.
    """

    def __init__(
        self,
        screen_share: Optional[Any] = None,
        memory_2_0: Optional[Any] = None,
        stale_threshold_s: float = 10.0,
        change_threshold: float = 0.02,
        analysis_throttle_s: float = 1.0,
    ) -> None:
        self.screen_share = screen_share
        self.memory_2_0 = memory_2_0
        self.stale_threshold_s = stale_threshold_s
        self.change_threshold = change_threshold
        self.analysis_throttle_s = analysis_throttle_s

        self.health = FrameHealth()
        self.status = VisionStatus.IDLE
        self.current_state: Optional[VisualState] = None
        self._previous_state: Optional[VisualState] = None

        self._lock = threading.RLock()
        self._callbacks: List[Callable[[VisualState], None]] = []
        self._last_analysis_time = 0.0
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ================================================================
    # Lifecycle
    # ================================================================

    def start(self) -> None:
        """Start the continuous vision monitor."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self.status = VisionStatus.CAPTURING

            # Subscribe to ScreenShareEngine state updates
            if self.screen_share is not None:
                try:
                    self.screen_share.subscribe(self._on_screen_state)
                except Exception as exc:
                    log.warning("Failed to subscribe to ScreenShareEngine: %s", exc)

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="MYRAA-VisionMonitor",
            )
            self._monitor_thread.start()
            log.info("Continuous vision controller started (consuming ScreenShareEngine).")

    def stop(self) -> None:
        """Stop the continuous vision monitor."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            self.status = VisionStatus.STOPPED
            # Unsubscribe from ScreenShareEngine
            if self.screen_share is not None:
                try:
                    self.screen_share.unsubscribe(self._on_screen_state)
                except Exception:
                    pass
            if self._monitor_thread is not None:
                self._monitor_thread.join(timeout=2)
            log.info("Continuous vision controller stopped.")

    # ================================================================
    # ScreenShareEngine Callbacks
    # ================================================================

    def _on_screen_state(self, screen_state: Any) -> None:
        """Called by ScreenShareEngine when new ScreenState is available."""
        start = time.perf_counter()
        try:
            visual = self._extract_visual_state(screen_state)
            latency_ms = (time.perf_counter() - start) * 1000

            self.health.record_frame(valid=True, latency_ms=latency_ms)
            self.health.last_analysis_time = time.time()

            with self._lock:
                self._previous_state = self.current_state
                self.current_state = visual
                self.status = VisionStatus.HEALTHY

            # Detect change
            if self._previous_state is not None:
                visual.changed = self._detect_change(self._previous_state, visual)
                if visual.changed:
                    visual.change_regions = getattr(screen_state, "changed_regions", [])

            # Notify callbacks
            for cb in self._callbacks:
                try:
                    cb(visual)
                except Exception:
                    pass

        except Exception as exc:
            self.health.record_error()
            log.debug("Vision state extraction failed: %s", exc)

    # ================================================================
    # Visual State Extraction
    # ================================================================

    def _extract_visual_state(self, screen_state: Any) -> VisualState:
        """Convert ScreenState to structured VisualState."""
        state = VisualState(
            timestamp=time.time(),
            frame_id=getattr(screen_state, "frame_id", 0),
            confidence=getattr(screen_state, "confidence", 0.0),
        )

        # Extract active window info
        active_win = getattr(screen_state, "active_window", {})
        if isinstance(active_win, dict):
            state.window_title = active_win.get("title", "")
            state.application = active_win.get("application", "")
        else:
            state.window_title = getattr(screen_state, "active_window_title", "")
            state.application = getattr(screen_state, "active_application", "")

        # Extract screen summary
        summary = getattr(screen_state, "screen_summary", None)
        if summary is not None:
            state.page_type = str(getattr(summary, "screen_type", ""))
            state.visual_state = str(getattr(summary, "primary_action", ""))

            # Extract UI targets from nodes
            vision_ctx = getattr(screen_state, "vision_context", None)
            if vision_ctx is not None:
                nodes = getattr(vision_ctx, "nodes", [])
                for node in nodes[:20]:  # bound to 20 targets
                    target = {
                        "type": str(getattr(node, "node_type", "")),
                        "text": str(getattr(node, "text", ""))[:100],
                        "bounds": getattr(node, "bounds", None),
                    }
                    state.ui_targets.append(target)

        # Extract error info
        changed = getattr(screen_state, "changed_regions", [])
        state.change_regions = changed

        return state

    # ================================================================
    # Change Detection
    # ================================================================

    def _detect_change(self, prev: VisualState, curr: VisualState) -> bool:
        """Detect meaningful visual change between states."""
        if prev.application != curr.application:
            return True
        if prev.window_title != curr.window_title:
            return True
        if prev.page_type != curr.page_type:
            return True
        if abs(prev.confidence - curr.confidence) > 0.3:
            return True
        if len(curr.change_regions) > 0:
            return True
        if prev.has_error != curr.has_error:
            return True
        return False

    # ================================================================
    # Monitor Loop (stale detection, health checks)
    # ================================================================

    def _monitor_loop(self) -> None:
        """Background monitor for frame health and stale detection."""
        while self._running and not self._stop_event.is_set():
            time.sleep(2.0)

            if not self._running:
                break

            # Check stale frames
            if self.health.total_frames > 0 and self.health.is_stale:
                self.health.record_stale()
                self.status = VisionStatus.STALE
                log.warning(
                    "Vision stale: no valid frame for %.1fs",
                    self.health.frame_age_s,
                )

                # Attempt recovery (ScreenShareEngine handles capture recovery)
                self._attempt_recovery()

            # Check degraded (high drop rate)
            elif self.health.total_frames > 10 and self.health.drop_rate > 0.3:
                self.status = VisionStatus.DEGRADED
                log.warning(
                    "Vision degraded: drop rate %.1f%%",
                    self.health.drop_rate * 100,
                )

    def _attempt_recovery(self) -> None:
        """Attempt to recover from stale vision."""
        self.status = VisionStatus.RECONNECTING
        self.health.record_reconnect()

        # ScreenShareEngine handles its own capture recovery.
        # If screen_share is active but frames are stale, the engine
        # is already retrying internally. Just wait for recovery.
        if self.screen_share is not None:
            try:
                if self.screen_share.is_active:
                    log.info("ScreenShareEngine active — waiting for recovery.")
                else:
                    log.info("ScreenShareEngine inactive — restarting.")
                    self.screen_share.start()
            except Exception as exc:
                log.warning("Vision recovery failed: %s", exc)
                self.status = VisionStatus.FAILED

    # ================================================================
    # Public API
    # ================================================================

    def add_listener(self, callback: Callable[[VisualState], None]) -> None:
        """Register for visual state updates."""
        self._callbacks.append(callback)

    def get_current_state(self) -> Optional[VisualState]:
        """Get the latest visual state."""
        return self.current_state

    def get_context_for_fusion(self) -> Optional[Dict[str, Any]]:
        """Get slim visual context for ContextFusion injection."""
        if self.current_state is None:
            return None
        if self.health.is_stale:
            return None  # Never inject stale context
        return self.current_state.to_context_dict()

    def verify_action(self, expected_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Visual verification: check if current screen matches expected state.
        Used by SuperBrain for action verification.
        """
        if self.current_state is None:
            return {"verified": False, "reason": "no visual state available"}

        results = []
        for key, expected_val in expected_state.items():
            actual_val = getattr(self.current_state, key, None)
            if actual_val is None:
                results.append({"check": key, "match": False, "reason": "field not available"})
            elif str(actual_val).lower() == str(expected_val).lower():
                results.append({"check": key, "match": True})
            else:
                results.append({
                    "check": key,
                    "match": False,
                    "expected": expected_val,
                    "actual": str(actual_val)[:100],
                })

        all_match = all(r["match"] for r in results) if results else False
        return {
            "verified": all_match,
            "checks": results,
            "confidence": self.current_state.confidence,
        }

    def is_healthy(self) -> bool:
        """Check if vision pipeline is healthy."""
        return self.status in (VisionStatus.HEALTHY, VisionStatus.CAPTURING)

    def is_stale(self) -> bool:
        """Check if vision data is stale."""
        return self.health.is_stale

    # ================================================================
    # Status / Telemetry
    # ================================================================

    def status_report(self) -> Dict[str, Any]:
        """Full vision status report."""
        return {
            "status": self.status.value,
            "health": self.health.to_dict(),
            "current_state": self.current_state.to_dict() if self.current_state else None,
            "is_healthy": self.is_healthy(),
            "is_stale": self.is_stale(),
            "callbacks": len(self._callbacks),
            "screen_share_attached": self.screen_share is not None,
        }

    def telemetry(self) -> Dict[str, Any]:
        """Lightweight telemetry for UI."""
        return {
            "status": self.status.value,
            "frame_count": self.health.total_frames,
            "valid_frames": self.health.valid_frames,
            "dropped_frames": self.health.dropped_frames,
            "frame_age_s": round(self.health.frame_age_s, 1),
            "avg_latency_ms": round(self.health.avg_latency_ms, 1),
            "is_stale": self.is_stale(),
            "application": self.current_state.application if self.current_state else "",
            "confidence": round(self.current_state.confidence, 2) if self.current_state else 0,
        }
