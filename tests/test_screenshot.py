"""
MYRAA Screenshot Test

Tests:
- takeScreenshot
- saveScreenshot
- analyzeScreenshot
- readScreen
"""

from __future__ import annotations

import json
import time

import requests

BASE_URL = "http://127.0.0.1:8765/execute"

PASS = 0
FAIL = 0


def run_test(title, tool, args):

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
            timeout=60,
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

    print("=" * 70)
    print("MYRAA SCREENSHOT TEST")
    print("=" * 70)

    run_test(
        "Take Screenshot",
        "takeScreenshot",
        {
            "include_image": False
        },
    )

    run_test(
        "Save Screenshot",
        "saveScreenshot",
        {},
    )

    run_test(
        "Analyze Screenshot",
        "analyzeScreenshot",
        {},
    )

    run_test(
        "Read Screen",
        "readScreen",
        {},
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