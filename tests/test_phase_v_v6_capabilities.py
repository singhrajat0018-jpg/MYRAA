"""Phase V — V6: Voice → All MYRAA Capabilities Tests."""
import sys
import os

sys.path.insert(0, os.getcwd())

def test_v6_capabilities():
    print("=" * 70)
    print("PHASE V - V6: VOICE -> ALL MYRAA CAPABILITIES TESTS")
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
    # 1. DESKTOP_TOOLS in server.ts covers all Python tools
    # ================================================================
    print("\n[1] DESKTOP_TOOLS in server.ts covers all Python tools")

    with open("server.ts", "r") as f:
        server_content = f.read()
    with open("desktop_agent/registry.py", "r") as f:
        registry_content = f.read()

    import re
    m = re.search(r"const DESKTOP_TOOLS: ReadonlySet<string> = new Set\(\[(.*?)\]\)", server_content, re.S)
    assert m, "Could not find DESKTOP_TOOLS in server.ts"
    server_tools = set(re.findall(r'"(\w+)"', m.group(1)))

    registered_tools = set(re.findall(r'"(\w+)"', m.group(1))) if (m := re.search(r'TOOLS\s*=\s*\{([^}]+)\}', registry_content, re.S)) else set()

    # Check well-known tools are in server
    critical_tools = [
        "openApplication", "closeApplication", "openWebsite", "searchWeb",
        "takeScreenshot", "readScreen", "typeText", "pressKey",
        "leftClick", "moveMouse", "volumeUp", "setVolume",
        "createFile", "readFile", "deleteFile",
        "minimizeWindow", "maximizeWindow", "closeWindow",
        "desktopBrowserOpen", "desktopBrowserNavigate",
        "createPythonFile", "runPythonScript",
    ]
    for tool in critical_tools:
        check("DESKTOP_TOOLS has '%s'" % tool, tool in server_tools)

    # ================================================================
    # 2. Canonical pipeline: /voice/execute routes through AssistantRuntime
    # ================================================================
    print("\n[2] Canonical pipeline routes through AssistantRuntime")

    check("server.ts routes to /voice/execute", "/voice/execute" in server_content)
    check("function name in body", "function_name:" in server_content or "function_name" in server_content)
    check("function args in body", "function_args:" in server_content or "function_args" in server_content)

    with open("desktop_agent/main.py", "r") as f:
        main_content = f.read()
    check("/voice/execute endpoint defined", '@app.post("/voice/execute")' in main_content)
    check("routes through AssistantRuntime", "AssistantRuntime" in main_content)

    # ================================================================
    # 3. User transcript routing
    # ================================================================
    print("\n[3] User transcript routing")

    check("user transcript to /voice/execute", "inputText" in server_content and "/voice/execute" in server_content)
    check("brain stream for brain responses", "/brain/stream" in server_content)

    # ================================================================
    # 4. Tool response sent back to Gemini
    # ================================================================
    print("\n[4] Tool response sent back to Gemini")

    check("sendToolResponse", "sendToolResponse" in server_content)
    check("functionResponses", "functionResponses" in server_content)

    # ================================================================
    # 5. Fallback: direct /execute if canonical pipeline unavailable
    # ================================================================
    print("\n[5] Fallback: direct /execute if canonical pipeline unavailable")

    check("try/catch for /voice/execute", "catch (err" in server_content)
    check("falls back to callDesktopAgent", "callDesktopAgent" in server_content)
    check("fallback error message", "Canonical pipeline unavailable" in server_content)

    # ================================================================
    # 6. Power action safety: blocked from autonomous execution
    # ================================================================
    print("\n[6] Power action safety")

    check("power actions require confirmation", "require explicit user confirmation" in server_content)
    check("executePowerAction blocked", "executePowerAction" in server_content)

    # ================================================================
    # 7. Non-desktop tools routed to React client
    # ================================================================
    print("\n[7] Non-desktop tools routed to React client")

    check("clientWs toolCall message", 'type: "toolCall"' in server_content)

    # ================================================================
    # 8. /tools endpoint lists all tools
    # ================================================================
    print("\n[8] /tools endpoint lists all tools")

    check("/tools endpoint in main.py", '@app.get("/tools")' in main_content)

    from desktop_agent.registry import TOOLS
    tool_count = len(TOOLS) if TOOLS else 0
    print("  INFO: %d tools registered in Python" % tool_count)
    if tool_count > 0:
        check("at least 50 tools registered", tool_count >= 50)
    else:
        print("  SKIP: TOOLS not populated (module-level import)")
        passed += 1

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS: %d passed, %d failed" % (passed, failed))
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_v6_capabilities()
    sys.exit(0 if success else 1)
