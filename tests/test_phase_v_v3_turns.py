"""Phase V — V3: Turn Management + Barge-In Tests."""
import sys
import os

sys.path.insert(0, os.getcwd())

def test_v3_turn_management():
    print("=" * 70)
    print("PHASE V - V3: TURN MANAGEMENT + BARGE-IN TESTS")
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
    # 1. VoiceInterface state machine
    # ================================================================
    print("\n[1] VoiceInterface state machine")

    from desktop_agent.speech.voice_interface import VoiceInterface, VoiceState

    vi = VoiceInterface()
    check("initial state IDLE", vi.state == VoiceState.IDLE)

    # Valid transitions
    vi.start_listening()
    check("IDLE -> LISTENING", vi.state == VoiceState.LISTENING)

    vi.user_speaking()
    check("LISTENING -> USER_SPEAKING", vi.state == VoiceState.USER_SPEAKING)

    vi.process_transcript("test")
    check("USER_SPEAKING -> PROCESSING", vi.state == VoiceState.PROCESSING)

    vi.speak("response")
    check("PROCESSING -> SPEAKING", vi.state == VoiceState.SPEAKING)

    vi.interrupt()
    check("SPEAKING -> INTERRUPTED", vi.state == VoiceState.INTERRUPTED)

    vi.start_listening()
    check("INTERRUPTED -> LISTENING", vi.state == VoiceState.LISTENING)

    # ================================================================
    # 2. All target states exist
    # ================================================================
    print("\n[2] All target states exist")

    target_states = [
        "IDLE", "CONNECTING", "READY", "LISTENING", "USER_SPEAKING",
        "PROCESSING", "SPEAKING", "INTERRUPTED", "RECONNECTING",
        "DEGRADED", "ERROR", "DISCONNECTED", "STOPPING",
    ]
    for state_name in target_states:
        check("state %s exists" % state_name, hasattr(VoiceState, state_name))

    # ================================================================
    # 3. New state transitions
    # ================================================================
    print("\n[3] New state transitions")

    vi2 = VoiceInterface()
    vi2.connecting()
    check("IDLE -> CONNECTING", vi2.state == VoiceState.CONNECTING)

    vi2.ready()
    check("CONNECTING -> READY", vi2.state == VoiceState.READY)

    vi2.start_listening()
    check("READY -> LISTENING", vi2.state == VoiceState.LISTENING)

    # Degraded
    vi3 = VoiceInterface()
    vi3.connecting()
    vi3.degraded()
    check("CONNECTING -> DEGRADED", vi3.state == VoiceState.DEGRADED)

    # Reconnecting
    vi4 = VoiceInterface()
    vi4.start_listening()
    vi4.process_transcript("test")
    vi4.interrupt()
    check("reached INTERRUPTED via valid path", vi4.state == VoiceState.INTERRUPTED)
    vi4.reconnecting()
    check("INTERRUPTED -> RECONNECTING", vi4.state == VoiceState.RECONNECTING)

    # ================================================================
    # 4. ContinuousVoiceLoop barge-in
    # ================================================================
    print("\n[4] ContinuousVoiceLoop barge-in")

    from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop, TurnStatus

    cvl = ContinuousVoiceLoop()
    check("ContinuousVoiceLoop created", cvl is not None)

    # Simulate barge-in
    result = cvl.on_interruption()
    check("interruption returns ok", result.get("ok") is True)
    check("interruption action", result.get("action") == "interrupted")

    # ================================================================
    # 5. State history tracking
    # ================================================================
    print("\n[5] State history tracking")

    vi5 = VoiceInterface()
    vi5.start_listening()
    vi5.user_speaking()
    vi5.process_transcript("hello")
    history = vi5.get_history()
    check("state history has entries", len(history) > 0)
    check("state history has timestamps", "timestamp" in history[0])

    # ================================================================
    # 6. State health
    # ================================================================
    print("\n[6] State health")

    vi6 = VoiceInterface()
    health = vi6.health()
    check("health has state", "state" in health)
    check("health has error_count", "error_count" in health)
    check("health has last_interaction", "last_interaction" in health)

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS: %d passed, %d failed" % (passed, failed))
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_v3_turn_management()
    sys.exit(0 if success else 1)
