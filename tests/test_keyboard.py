"""
MYRAA Keyboard Control Test

Tests:
- typeText
- pressKey
- keyDown
- keyUp
- hotkey

NOTE:
Open Notepad and click inside it before running this test,
otherwise the typed text will go to the currently focused window.
"""

from __future__ import annotations

import json
import time

import requests


BASE_URL = "http://127.0.0.1:8765/execute"


PASS = 0
FAIL = 0


def run_test(title: str, tool: str, args: dict):

    global PASS, FAIL

    print("=" * 70)
    print(title)

    try:

        response = requests.post(
            BASE_URL,
            json={
                "tool": tool,
                "args": args,
            },
            timeout=20,
        )

        data = response.json()

        if data.get("ok"):
            PASS += 1
            print("[PASS]")
        else:
            FAIL += 1
            print("[FAIL]")

        print(json.dumps(data, indent=2))

    except Exception as e:

        FAIL += 1

        print("[FAIL]")
        print(e)

    time.sleep(1)


def main():

    print("\n" + "=" * 70)
    print("MYRAA KEYBOARD CONTROL TEST")
    print("=" * 70)

    print("\nStarting test in 5 seconds...")
    time.sleep(5)

    run_test(
        "Type Text",
        "typeText",
        {
            "text": "Hello from MYRAA Keyboard Test!"
        },
    )

    run_test(
        "Press Enter",
        "pressKey",
        {
            "key": "enter"
        },
    )

    run_test(
        "Hold Shift",
        "keyDown",
        {
            "key": "shift"
        },
    )

    run_test(
        "Release Shift",
        "keyUp",
        {
            "key": "shift"
        },
    )

    run_test(
        "Hotkey CTRL + A",
        "hotkey",
        {
            "keys": ["ctrl", "a"]
        },
    )

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"PASS : {PASS}")
    print(f"FAIL : {FAIL}")

    if FAIL == 0:
        print("\nALL TESTS PASSED")
    else:
        print("\nSOME TESTS FAILED")


if __name__ == "__main__":
    main()