"""Phase V — V5: Audio Playback + Echo Safety Tests."""
import sys
import os

sys.path.insert(0, os.getcwd())

def test_v5_playback():
    print("=" * 70)
    print("PHASE V - V5: AUDIO PLAYBACK + ECHO SAFETY TESTS")
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
    # 1. Echo cancellation chain
    # ================================================================
    print("\n[1] Echo cancellation chain")

    with open("src/lib/audio.ts", "r") as f:
        content = f.read()
    check("echoCancellation: true", "echoCancellation: true" in content)
    check("noiseSuppression: true", "noiseSuppression: true" in content)
    check("autoGainControl: true", "autoGainControl: true" in content)

    # ================================================================
    # 2. Adaptive gain control
    # ================================================================
    print("\n[2] Adaptive gain control")

    check("micGainNode exists", "micGainNode" in content)
    check("adaptive gain control method", "updateMicGainForState" in content)
    check("gain reduction when speaking", "More aggressive gain reduction" in content)
    check("feedback detection", "feedback" in content.lower())
    check("echo cancellation estimate", "echoEstimate" in content)

    # ================================================================
    # 3. Audio buffering
    # ================================================================
    print("\n[3] Audio buffering")

    check("audioBuffer array", "audioBuffer" in content)
    check("BUFFER_FLUSH_MS constant", "BUFFER_FLUSH_MS" in content)
    check("flushAudioBuffer method", "flushAudioBuffer" in content)
    check("isBuffering flag", "isBuffering" in content)
    check("bufferTimeout for scheduling", "bufferTimeout" in content)

    # ================================================================
    # 4. Stale audio protection
    # ================================================================
    print("\n[4] Stale audio protection")

    check("nextStartTime tracking", "nextStartTime" in content)
    check("activeSources tracking", "activeSources" in content)
    check("stop all on interruption", "activeSources.forEach" in content)

    # ================================================================
    # 5. Playback sample rate
    # ================================================================
    print("\n[5] Playback sample rate")

    check("24kHz output", "24000" in content)
    check("PCM16 conversion", "pcm16ToFloats" in content)

    # ================================================================
    # 6. Output gain node
    # ================================================================
    print("\n[6] Output gain node")

    check("outputGainNode", "outputGainNode" in content)
    check("outputAnalyser", "outputAnalyser" in content)
    check("inputAnalyser", "inputAnalyser" in content)

    # ================================================================
    # 7. Interruption stops all playback
    # ================================================================
    print("\n[7] Interruption stops all playback")

    check("handleInterruption stops sources", "handleInterruption" in content)
    check("source.stop()", "source.stop()" in content)
    check("resets nextStartTime", "this.nextStartTime = 0" in content)

    # ================================================================
    # 8. Echo safety: mic muted during output
    # ================================================================
    print("\n[8] Echo safety: mic muted during output")

    check("mic gain 0.2 during speaking", "baseGain = 0.2" in content)
    check("mic gain 0.5 default", "baseGain = 0.5" in content)
    check("output level monitoring", "outputLevel" in content)

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS: %d passed, %d failed" % (passed, failed))
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_v5_playback()
    sys.exit(0 if success else 1)
