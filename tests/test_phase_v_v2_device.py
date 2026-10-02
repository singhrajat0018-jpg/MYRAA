"""Phase V — V2: Production Microphone/Device Tests."""
import sys
import os

sys.path.insert(0, os.getcwd())

def test_v2_device_handling():
    print("=" * 70)
    print("PHASE V - V2: PRODUCTION MICROPHONE/DEVICE TESTS")
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
    # 1. Settings store has micDeviceId
    # ================================================================
    print("\n[1] Settings store has micDeviceId")

    # Read the settingsStore.ts to verify micDeviceId is defined
    with open("src/lib/settingsStore.ts", "r") as f:
        content = f.read()
    check("micDeviceId in settings", "micDeviceId" in content)
    check("default micDeviceId empty", 'micDeviceId: ""' in content)

    # ================================================================
    # 2. Audio.ts uses device constraints
    # ================================================================
    print("\n[2] Audio.ts uses device constraints")

    with open("src/lib/audio.ts", "r") as f:
        audio_content = f.read()
    check("imports settingsStore", "settingsStore" in audio_content)
    check("uses deviceId constraint", "deviceId" in audio_content)
    check("uses exact constraint", "exact:" in audio_content or "exact :" in audio_content)

    # ================================================================
    # 3. Device health method exists
    # ================================================================
    print("\n[3] Device health method exists")

    check("getDeviceHealth method", "getDeviceHealth" in audio_content)
    check("returns micActive", "micActive" in audio_content)
    check("returns sampleRate", "sampleRate" in audio_content)
    check("returns deviceId", "deviceId" in audio_content)

    # ================================================================
    # 4. Echo/feedback prevention
    # ================================================================
    print("\n[4] Echo/feedback prevention")

    check("echoCancellation enabled", "echoCancellation: true" in audio_content)
    check("noiseSuppression enabled", "noiseSuppression: true" in audio_content)
    check("autoGainControl enabled", "autoGainControl: true" in audio_content)
    check("micGainNode exists", "micGainNode" in audio_content)
    check("adaptive gain control", "updateMicGainForState" in audio_content)

    # ================================================================
    # 5. SettingsPanel enumerates devices
    # ================================================================
    print("\n[5] SettingsPanel device enumeration")

    with open("src/components/SettingsPanel.tsx", "r") as f:
        panel_content = f.read()
    check("enumerateDevices", "enumerateDevices" in panel_content)
    check("microphone kind filter", "microphone" in panel_content.lower())

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS: %d passed, %d failed" % (passed, failed))
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_v2_device_handling()
    sys.exit(0 if success else 1)
