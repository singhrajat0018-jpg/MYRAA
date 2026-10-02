"""Phase V — V4: Gemini Live Resilience Tests."""
import sys
import os

sys.path.insert(0, os.getcwd())

def test_v4_resilience():
    print("=" * 70)
    print("PHASE V - V4: GEMINI LIVE RESILIENCE TESTS")
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
    # 1. Audio.ts has auto-reconnect logic
    # ================================================================
    print("\n[1] Audio.ts has auto-reconnect logic")

    with open("src/lib/audio.ts", "r") as f:
        content = f.read()
    check("reconnectAttempts field", "reconnectAttempts" in content)
    check("maxReconnectAttempts field", "maxReconnectAttempts" in content)
    check("reconnectTimer field", "reconnectTimer" in content)
    check("intentionalDisconnect field", "intentionalDisconnect" in content)
    check("attemptReconnect method", "attemptReconnect" in content)
    check("exponential backoff", "Math.pow(2" in content)
    check("bounded reconnect", "this.maxReconnectAttempts" in content)

    # ================================================================
    # 2. Disconnect tracks intentional vs unintentional
    # ================================================================
    print("\n[2] Disconnect tracks intentional vs unintentional")

    check("disconnect(intentional)", "disconnect(intentional" in content)
    check("clearTimeout on intentional", "clearTimeout(this.reconnectTimer)" in content)

    # ================================================================
    # 3. Server voice fallback loop (bounded)
    # ================================================================
    print("\n[3] Server voice fallback loop (bounded)")

    with open("server.ts", "r") as f:
        server_content = f.read()
    check("maxVoiceAttempts bounded", "maxVoiceAttempts" in server_content)
    check("voice stability window", "2500" in server_content)
    check("400ms between attempts", "400" in server_content)

    # ================================================================
    # 4. Server session_closed handler
    # ================================================================
    print("\n[4] Server session_closed handler")

    check("onSessionClosed handler", "onSessionClosed" in server_content)
    check("sends session_closed status", "session_closed" in server_content)
    check("sends voice_degraded", "voice_degraded" in server_content)

    # ================================================================
    # 5. Python /voice/reconnect endpoint
    # ================================================================
    print("\n[5] Python /voice/reconnect endpoint")

    with open("desktop_agent/main.py", "r") as f:
        main_content = f.read()
    check("/voice/reconnect endpoint", "/voice/reconnect" in main_content)
    check("/voice/health endpoint", "/voice/health" in main_content)
    check("/voice/status endpoint", "/voice/status" in main_content)

    # ================================================================
    # 6. ContinuousVoiceLoop health
    # ================================================================
    print("\n[6] ContinuousVoiceLoop health")

    from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop

    cvl = ContinuousVoiceLoop()
    health = cvl.health()
    check("health has voice_state", "voice_state" in health)
    check("health has total_interruptions", "total_interruptions" in health)
    check("health has consecutive_errors", "consecutive_errors" in health)

    status = cvl.status()
    check("status has state", "state" in status)

    # ================================================================
    # 7. VoiceInterface supports reconnecting state
    # ================================================================
    print("\n[7] VoiceInterface supports reconnecting state")

    from desktop_agent.speech.voice_interface import VoiceInterface, VoiceState

    vi = VoiceInterface()
    vi.connecting()
    vi.degraded()
    check("can reach DEGRADED", vi.state == VoiceState.DEGRADED)

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS: %d passed, %d failed" % (passed, failed))
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_v4_resilience()
    sys.exit(0 if success else 1)
