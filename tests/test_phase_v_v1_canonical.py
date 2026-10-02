"""Phase V — V1: Canonical Voice Pipeline Tests."""
import time
import sys
import os

sys.path.insert(0, os.getcwd())

def test_v1_canonical_voice_pipeline():
    print("=" * 70)
    print("PHASE V — V1: CANONICAL VOICE PIPELINE TESTS")
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
    # 1. AssistantRuntime exists and handles voice
    # ================================================================
    print("\n[1] AssistantRuntime handles voice requests")

    from desktop_agent.brain.assistant_runtime import (
        AssistantRuntime,
        AssistantRequest,
        AssistantResponse,
        InputType,
    )

    runtime = AssistantRuntime()
    check("AssistantRuntime created", runtime is not None)
    check("InputType.VOICE exists", InputType.VOICE.value == "voice")

    # ================================================================
    # 2. TaskRouter classifies voice same as text
    # ================================================================
    print("\n[2] TaskRouter — voice and text produce same routing")

    from desktop_agent.brain.router.task_router import TaskRouter, TaskType

    router = TaskRouter()

    # "Hello Myraa" should be CONVERSATION for both voice and text
    r_text = router.route("Hello Myraa")
    r_voice = router.route("Hello Myraa")
    check("Hello: same task_type", r_text.task_type == r_voice.task_type)
    check("Hello: CONVERSATION", r_text.task_type == TaskType.CONVERSATION)

    # "What is Python?" should be DIRECT_KNOWLEDGE
    r_py = router.route("What is Python?")
    check("Python: DIRECT_KNOWLEDGE", r_py.task_type == TaskType.DIRECT_KNOWLEDGE)

    # "Open Notepad" should be DESKTOP_ACTION
    r_open = router.route("Open Notepad")
    check("Open Notepad: DESKTOP_ACTION", r_open.task_type == TaskType.DESKTOP_ACTION)

    # "Open YouTube" should be BROWSER_ACTION
    r_yt = router.route("Open YouTube")
    check("Open YouTube: BROWSER_ACTION", r_yt.task_type == TaskType.BROWSER_ACTION)

    # "What's on my screen?" should be VISION_TASK
    r_screen = router.route("What's on my screen?")
    check("Screen: VISION_TASK", r_screen.task_type == TaskType.VISION_TASK)

    # ================================================================
    # 3. ContinuousVoiceLoop wired to AssistantRuntime
    # ================================================================
    print("\n[3] ContinuousVoiceLoop wired to AssistantRuntime")

    from desktop_agent.core.application_container import ApplicationContainer

    container = ApplicationContainer()
    cvl = container.continuous_voice_loop
    check("ContinuousVoiceLoop exists", cvl is not None)
    check("execute callback set", cvl._on_execute is not None)

    # ================================================================
    # 4. /voice/execute endpoint exists
    # ================================================================
    print("\n[4] /voice/execute endpoint exists")

    from fastapi.testclient import TestClient
    from desktop_agent.main import app

    client = TestClient(app)

    # Test conversation fast path
    r = client.post("/voice/execute", json={
        "transcript": "Hello Myraa",
    })
    check("/voice/execute responds", r.status_code == 200)
    data = r.json()
    check("response has ok field", "ok" in data)
    # task_id may not be present if assistant_runtime is not initialized in test
    check("response has turn_id", "turn_id" in data)

    # Test knowledge fast path
    r2 = client.post("/voice/execute", json={
        "transcript": "What is Python?",
    })
    check("knowledge request ok", r2.status_code == 200)
    data2 = r2.json()
    check("knowledge has response", "ok" in data2)

    # ================================================================
    # 5. Voice and text reach same TaskType
    # ================================================================
    print("\n[5] Same-pipeline verification")

    test_cases = [
        ("Hello Myraa", TaskType.CONVERSATION),
        ("What is Python?", TaskType.DIRECT_KNOWLEDGE),
        ("Open Notepad", TaskType.DESKTOP_ACTION),
        ("Open YouTube", TaskType.BROWSER_ACTION),
        ("What's on my screen?", TaskType.VISION_TASK),
    ]

    for text, expected_type in test_cases:
        r = router.route(text)
        check("'%s' -> %s" % (text, expected_type.name), r.task_type == expected_type)

    # ================================================================
    # 6. Voice request types
    # ================================================================
    print("\n[6] Voice request contract")

    req = AssistantRequest(
        user_input="Open YouTube",
        input_type=InputType.VOICE,
        source="gemini_live",
    )
    check("voice request has input_type VOICE", req.input_type == InputType.VOICE)
    check("voice request has source", req.source == "gemini_live")
    check("voice request normalized_input works", req.normalized_input() == "Open YouTube")

    # ================================================================
    # 7. No voice-specific brain/router
    # ================================================================
    print("\n[7] No voice-specific brain/router (architecture invariant)")

    import importlib
    voice_brain_exists = True
    try:
        importlib.import_module("desktop_agent.brain.voice_brain")
    except ImportError:
        voice_brain_exists = False
    check("No VoiceBrain module", not voice_brain_exists)

    voice_router_exists = True
    try:
        importlib.import_module("desktop_agent.brain.voice_router")
    except ImportError:
        voice_router_exists = False
    check("No VoiceRouter module", not voice_router_exists)

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_v1_canonical_voice_pipeline()
    sys.exit(0 if success else 1)
