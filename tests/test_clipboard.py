"""
MYRAA Clipboard Test

Tests:
- clearClipboard
- getClipboard
- pasteClipboard
- copySelected

NOTE:
This test will open Notepad automatically.
"""

from __future__ import annotations

import json
import subprocess
import time

import pyautogui
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

        return data

    except Exception as e:

        FAIL += 1
        print("[FAIL]")
        print(e)

        return None


def main():

    print("=" * 70)
    print("MYRAA CLIPBOARD TEST")
    print("=" * 70)

    print("\nOpening Notepad...")

    subprocess.Popen("notepad.exe")

    time.sleep(2)

    TEST_TEXT = "Hello from MYRAA Clipboard Test!"

    # ---------------------------------------------------------

    run_test(
        "Clear Clipboard",
        "clearClipboard",
        {},
    )

    run_test(
        "Read Empty Clipboard",
        "getClipboard",
        {},
    )

    run_test(
        "Paste Clipboard",
        "pasteClipboard",
        {
            "text": TEST_TEXT
        },
    )

    time.sleep(1)

    pyautogui.hotkey("ctrl", "a")

    time.sleep(0.5)

    run_test(
        "Copy Selected",
        "copySelected",
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