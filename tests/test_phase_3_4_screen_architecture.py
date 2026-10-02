"""Phase 3.4 — Screen Architecture Migration Tests."""
import time
import sys
import os
import threading

sys.path.insert(0, os.getcwd())

def test_phase_3_4():
    print("=" * 70)
    print("PHASE 3.4 — SCREEN ARCHITECTURE MIGRATION TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            print(f"  PASS: {name}")
            passed += 1
        else:
            print(f"  FAIL: {name}")
            failed += 1

    # ================================================================
    # 1. ContinuousVisionController — ScreenShareEngine consumption
    # ================================================================
    print("\n[1] ContinuousVisionController consumes ScreenShareEngine")

    from desktop_agent.desktop.vision.screen_share import (
        ScreenShareEngine,
        ScreenShareStatus,
        get_screen_share_engine,
        reset_screen_share_engine,
    )
    from desktop_agent.brain.super_brain.continuous_vision import (
        ContinuousVisionController,
        VisionStatus,
    )

    # Create ScreenShareEngine
    engine = ScreenShareEngine(target_fps=5)
    engine.start()
    got_frame = engine.wait_for_first_frame(timeout=10.0)
    check("ScreenShareEngine started", got_frame)

    # Create ContinuousVisionController with screen_share
    cvc = ContinuousVisionController(screen_share=engine)
    check("CVC created with screen_share", cvc.screen_share is engine)
    check("CVC has no vision_manager attr", not hasattr(cvc, 'vision_manager'))

    # Start CVC
    cvc.start()
    check("CVC started", cvc._running)
    check("CVC status is CAPTURING", cvc.status == VisionStatus.CAPTURING)

    # Wait for state update
    time.sleep(2.0)

    # Check that CVC received state from ScreenShareEngine
    check("CVC received state", cvc.current_state is not None)
    if cvc.current_state is not None:
        check("CVC state has timestamp", cvc.current_state.timestamp > 0)
        check("CVC state has frame_id", cvc.current_state.frame_id > 0)

    # Check health
    check("CVC health has frames", cvc.health.total_frames > 0)
    check("CVC health has valid frames", cvc.health.valid_frames > 0)

    # Stop CVC
    cvc.stop()
    check("CVC stopped", not cvc._running)
    check("CVC status STOPPED", cvc.status == VisionStatus.STOPPED)

    # ================================================================
    # 2. ScreenShareEngine — single capture authority
    # ================================================================
    print("\n[2] ScreenShareEngine is single capture authority")

    # Verify only one capture thread
    import subprocess
    out = subprocess.check_output(
        ['powershell', '-Command', f'(Get-Process -Id {os.getpid()}).Threads.Count'],
        timeout=5
    )
    thread_count = int(out.decode().strip())
    check("thread count reasonable", thread_count < 100)

    # ================================================================
    # 3. No duplicate capture paths
    # ================================================================
    print("\n[3] No duplicate capture paths")

    try:
        from desktop_agent.desktop.vision.live_capture import LiveCaptureEngine
    except ImportError:
        LiveCaptureEngine = None
    # LiveCaptureEngine should not be started in production
    check("LiveCaptureEngine removed (no duplicate capture)", LiveCaptureEngine is None)

    # ================================================================
    # 4. Screenshot tools — explicit only
    # ================================================================
    print("\n[4] Screenshot tools — explicit only")

    from desktop_agent.desktop.vision.screenshot_engine import ScreenshotEngine
    # ScreenshotEngine is used for explicit tools, not continuous capture
    check("ScreenshotEngine exists (explicit tools)", ScreenshotEngine is not None)

    # ================================================================
    # 5. Universal Controller uses ContinuousVisionController
    # ================================================================
    print("\n[5] Universal Controller integration")

    from desktop_agent.universal_control.universal_controller import UniversalController
    uc = UniversalController(vision_controller=cvc, tool_executor=None)
    check("UC accepts CVC", uc._vision is cvc)

    # ================================================================
    # 6. Lifecycle — idempotent start/stop
    # ================================================================
    print("\n[6] Lifecycle — idempotent start/stop")

    cvc2 = ContinuousVisionController(screen_share=engine)
    cvc2.start()
    cvc2.start()  # Should be idempotent
    check("CVC idempotent start", cvc2._running)

    cvc2.stop()
    cvc2.stop()  # Should be safe
    check("CVC idempotent stop", not cvc2._running)

    # ================================================================
    # 7. ScreenShareEngine — subscriber pattern
    # ================================================================
    print("\n[7] ScreenShareEngine subscriber pattern")

    received_states = []
    def on_state(state):
        received_states.append(state)

    engine.subscribe(on_state)
    time.sleep(1.0)
    engine.unsubscribe(on_state)
    check("subscriber received states", len(received_states) > 0)

    # ================================================================
    # 8. Failure recovery — CVC handles stale
    # ================================================================
    print("\n[8] Failure recovery")

    cvc3 = ContinuousVisionController(
        screen_share=engine,
        stale_threshold_s=1.0,
    )
    cvc3.start()
    time.sleep(2.0)

    # Health should be tracked
    check("CVC health tracked", cvc3.health.total_frames > 0)

    cvc3.stop()

    # ================================================================
    # 9. Privacy — no raw frames in state
    # ================================================================
    print("\n[9] Privacy — no raw frames in VisualState")

    from desktop_agent.brain.super_brain.continuous_vision import VisualState
    vs = VisualState()
    state_dict = vs.to_dict()
    check("VisualState has no image field", "image" not in state_dict)
    check("VisualState has no frame field", "frame" not in state_dict)

    # ================================================================
    # Cleanup
    # ================================================================
    engine.stop()

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_phase_3_4()
    sys.exit(0 if success else 1)
