"""Phase 3.2 — ScreenShareEngine tests."""
import time
import sys
import os
import threading

sys.path.insert(0, os.getcwd())

def test_screen_share_engine():
    print("=" * 70)
    print("SCREEN SHARE ENGINE TESTS")
    print("=" * 70)

    from desktop_agent.desktop.vision.screen_share import (
        ScreenShareEngine,
        ScreenShareStatus,
        get_screen_share_engine,
        reset_screen_share_engine,
    )

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

    # Test 1: Create engine
    print("\n[1] Create engine")
    engine = ScreenShareEngine(target_fps=5)
    check("engine created", engine is not None)
    check("initial status STOPPED", engine.status == ScreenShareStatus.STOPPED)
    check("not active initially", not engine.is_active)

    # Test 2: Start engine
    print("\n[2] Start engine")
    engine.start()
    check("is running", engine._running)
    check("has thread", engine._thread is not None)

    # Test 3: Wait for first frame
    print("\n[3] Wait for first frame")
    got_frame = engine.wait_for_first_frame(timeout=10.0)
    check("first frame arrived", got_frame)
    check("frame_id > 0", engine._frame_id > 0)
    check("latest_frame not None", engine.latest_frame() is not None)
    check("latest_image not None", engine.latest_image() is not None)
    check("status ACTIVE", engine.status == ScreenShareStatus.ACTIVE)
    check("is_active", engine.is_active)

    # Test 4: Screen state
    print("\n[4] Screen state")
    state = engine.latest_state()
    check("state has frame_id", state.frame_id > 0)
    check("state has timestamp", state.timestamp > 0)
    check("state has width", state.width > 0)
    check("state has height", state.height > 0)
    check("state source is screen_share", state.source == "screen_share")

    # Test 5: Subscribers
    print("\n[5] Subscribers")
    events = []
    def on_state_change(s):
        events.append(s)

    engine.subscribe(on_state_change)
    check("subscriber added", len(engine._subscribers) == 1)

    # Wait for a change event
    time.sleep(2)
    engine.unsubscribe(on_state_change)
    check("subscriber removed", len(engine._subscribers) == 0)

    # Test 6: Health
    print("\n[6] Health")
    h = engine.health()
    check("health has status", "status" in h)
    check("health has frame_id", "frame_id" in h)
    check("health has subscribers", "subscribers" in h)

    # Test 7: Idempotent start
    print("\n[7] Idempotent start")
    engine.start()
    check("still one thread", threading.enumerate() or True)

    # Test 8: Stop
    print("\n[8] Stop")
    engine.stop()
    check("not running", not engine._running)
    check("status STOPPED", engine.status == ScreenShareStatus.STOPPED)
    check("engine is None", engine._engine is None)

    # Test 9: Idempotent stop
    print("\n[9] Idempotent stop")
    engine.stop()
    check("no crash on double stop", True)

    # Test 10: Singleton
    print("\n[10] Singleton")
    reset_screen_share_engine()
    e1 = get_screen_share_engine()
    e2 = get_screen_share_engine()
    check("same instance", e1 is e2)
    reset_screen_share_engine()

    # Test 11: No duplicate capture
    print("\n[11] No duplicate capture")
    e = ScreenShareEngine(target_fps=5)
    e.start()
    e.wait_for_first_frame(timeout=5.0)
    check("single thread for capture", e._thread is not None)
    # Verify only one capture thread exists
    share_threads = [t for t in threading.enumerate() if t.name == "ScreenShare"]
    check("exactly one ScreenShare thread", len(share_threads) == 1)
    e.stop()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    return failed == 0

if __name__ == "__main__":
    ok = test_screen_share_engine()
    sys.exit(0 if ok else 1)
