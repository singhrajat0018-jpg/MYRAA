"""Phase V - V7: Observability + Comprehensive Regression Tests."""
import sys
import os

sys.path.insert(0, os.getcwd())

def test_v7_observability():
    print("=" * 70)
    print("PHASE V - V7: OBSERVABILITY + COMPREHENSIVE REGRESSION")
    print("=" * 70)

    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            print("  PASS: %s" % name)
            passed += 1
        else:
            print("  FAIL: %s" % name)
            failed += 1

    # ================================================================
    # 1. Voice health endpoint
    # ================================================================
    print("\n[1] Voice health endpoint")

    with open("desktop_agent/main.py", "r") as f:
        main_content = f.read()
    check("/voice/health endpoint", '@app.get("/voice/health")' in main_content)
    check("/voice/status endpoint", '@app.get("/voice/status")' in main_content)
    check("/voice/turns endpoint", '@app.get("/voice/turns")' in main_content)

    # ================================================================
    # 2. VoiceInterface health
    # ================================================================
    print("\n[2] VoiceInterface health")

    from desktop_agent.speech.voice_interface import VoiceInterface, VoiceState

    vi = VoiceInterface()
    vi.start_listening()
    vi.process_transcript("test")
    vi.speak("response")

    health = vi.health()
    check("health has state", "state" in health)
    check("health has error_count", "error_count" in health)
    check("health has last_interaction", "last_interaction" in health)

    # ================================================================
    # 3. ContinuousVoiceLoop health
    # ================================================================
    print("\n[3] ContinuousVoiceLoop health")

    from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop

    cvl = ContinuousVoiceLoop()
    health = cvl.health()
    check("voice_state in health", "voice_state" in health)
    check("total_turns in health", "total_turns" in health)
    check("session_uptime_s in health", "session_uptime_s" in health)
    check("history_length in health", "history_length" in health)

    # ================================================================
    # 4. /voice/execute endpoint (works without full container init)
    # ================================================================
    print("\n[4] /voice/execute endpoint")

    from fastapi.testclient import TestClient
    from desktop_agent.main import app

    client = TestClient(app, raise_server_exceptions=False)

    r = client.post("/voice/execute", json={"transcript": "hello"})
    check("/voice/execute 200", r.status_code == 200)
    data = r.json()
    check("/voice/execute has ok field", "ok" in data)
    check("/voice/execute has request_id", "request_id" in data)
    check("/voice/execute has turn_id", "turn_id" in data)

    r2 = client.post("/voice/execute", json={
        "transcript": "open notepad",
        "function_name": "openApplication",
        "function_args": {"appName": "notepad"},
    })
    check("/voice/execute with function_name", r2.status_code == 200)

    # ================================================================
    # 5. VoiceInterface state transitions comprehensive
    # ================================================================
    print("\n[5] VoiceInterface state transitions comprehensive")

    vi2 = VoiceInterface()
    assert vi2.state == VoiceState.IDLE
    vi2.connecting()
    assert vi2.state == VoiceState.CONNECTING
    vi2.ready()
    assert vi2.state == VoiceState.READY
    vi2.start_listening()
    assert vi2.state == VoiceState.LISTENING
    vi2.user_speaking()
    assert vi2.state == VoiceState.USER_SPEAKING
    vi2.process_transcript("test")
    assert vi2.state == VoiceState.PROCESSING
    vi2.speak("response")
    assert vi2.state == VoiceState.SPEAKING
    vi2.interrupt()
    assert vi2.state == VoiceState.INTERRUPTED
    vi2.start_listening()
    assert vi2.state == VoiceState.LISTENING
    vi2.stop_listening()
    assert vi2.state == VoiceState.IDLE
    check("full lifecycle: IDLE->...->IDLE", vi2.state == VoiceState.IDLE)

    vi3 = VoiceInterface()
    vi3.start_listening()
    vi3.set_error("test")
    assert vi3.state == VoiceState.ERROR
    vi3.stop_listening()
    check("error path: ERROR->IDLE", vi3.state == VoiceState.IDLE)

    vi4 = VoiceInterface()
    vi4.connecting()
    vi4.disconnect()
    assert vi4.state == VoiceState.DISCONNECTED
    vi4.reconnect()
    check("disconnect path: DISCONNECTED->IDLE", vi4.state == VoiceState.IDLE)

    # ================================================================
    # 6. ContinuousVoiceLoop turn lifecycle
    # ================================================================
    print("\n[6] ContinuousVoiceLoop turn lifecycle")

    cvl2 = ContinuousVoiceLoop()

    # User transcript creates a turn
    r = cvl2.on_user_transcript("open notepad")
    check("on_user_transcript returns dict", isinstance(r, dict))
    check("on_user_transcript has turn_id", "turn_id" in r)

    # Turn complete
    r = cvl2.on_turn_complete()
    check("on_turn_complete ok", r.get("ok") is True)

    # Barge-in
    r = cvl2.on_interruption()
    check("on_interruption ok", r.get("ok") is True)
    check("on_interruption action", r.get("action") == "interrupted")

    # Disconnect
    r = cvl2.on_disconnect()
    check("on_disconnect ok", r.get("ok") is True)

    # Reconnect
    r = cvl2.on_reconnect()
    check("on_reconnect ok", r.get("ok") is True)

    # Health after operations
    health = cvl2.health()
    check("health after ops has voice_state", "voice_state" in health)
    check("health after ops has total_interruptions", "total_interruptions" in health)
    check("total_interruptions > 0", health["total_interruptions"] > 0)

    # ================================================================
    # 7. All critical voice files exist and are non-empty
    # ================================================================
    print("\n[7] All critical voice files exist and are non-empty")

    critical_files = [
        "desktop_agent/speech/voice_interface.py",
        "desktop_agent/speech/continuous_voice_loop.py",
        "desktop_agent/speech/__init__.py",
        "desktop_agent/brain/assistant_runtime.py",
        "desktop_agent/brain/router/task_router.py",
        "src/lib/audio.ts",
        "src/lib/settingsStore.ts",
    ]
    for f in critical_files:
        check("file exists: %s" % f, os.path.exists(f) and os.path.getsize(f) > 0)

    # ================================================================
    # 8. Phase V: All new test files exist
    # ================================================================
    print("\n[8] Phase V: All new test files exist")

    test_files = [
        "tests/test_phase_v_v1_canonical.py",
        "tests/test_phase_v_v2_device.py",
        "tests/test_phase_v_v3_turns.py",
        "tests/test_phase_v_v4_resilience.py",
        "tests/test_phase_v_v5_playback.py",
        "tests/test_phase_v_v6_capabilities.py",
    ]
    for f in test_files:
        check("test exists: %s" % f, os.path.exists(f))

    # ================================================================
    # 9. Regression: existing tests still pass
    # ================================================================
    print("\n[9] Regression: existing tests still pass")

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_phase_3_4_screen_architecture.py", "-q", "--tb=no"],
        capture_output=True, text=True, timeout=60,
        cwd=os.getcwd()
    )
    check("Phase 3.4 tests pass", result.returncode == 0)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_screen_share.py", "-q", "--tb=no"],
        capture_output=True, text=True, timeout=60,
        cwd=os.getcwd()
    )
    check("ScreenShareEngine tests pass", result.returncode == 0)

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS: %d passed, %d failed" % (passed, failed))
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_v7_observability()
    sys.exit(0 if success else 1)
