"""
MYRAA Mouse Control Test

Tests:
- mousePosition
- moveMouse
- leftClick
- rightClick
- doubleClick
- middleClick
- scrollMouse
- dragMouse

WARNING:
This test will MOVE YOUR MOUSE.
Do not touch the mouse while the test is running.
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
    print("MYRAA MOUSE CONTROL TEST")
    print("=" * 70)

    print("\nStarting test in 5 seconds...")
    print("Please do NOT move the mouse.")

    time.sleep(5)

    # -------------------------------------------------

    run_test(
        "Get Mouse Position",
        "mousePosition",
        {},
    )

    run_test(
        "Move Mouse",
        "moveMouse",
        {
            "x": 500,
            "y": 300,
        },
    )

    run_test(
        "Left Click",
        "leftClick",
        {},
    )

    run_test(
        "Right Click",
        "rightClick",
        {},
    )

    run_test(
        "Double Click",
        "doubleClick",
        {},
    )

    run_test(
        "Middle Click",
        "middleClick",
        {},
    )

    run_test(
        "Scroll Mouse",
        "scrollMouse",
        {
            "clicks": -500
        },
    )

    run_test(
        "Drag Mouse",
        "dragMouse",
        {
            "x": 700,
            "y": 500,
            "duration": 0.5
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