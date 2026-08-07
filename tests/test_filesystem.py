"""
MYRAA File System Integration Test

Runs end-to-end tests against the FastAPI execute endpoint.

Run:

    python tests/test_filesystem.py
"""

from __future__ import annotations

import requests
from test_config import *

PASS = 0
FAIL = 0

import os

def cleanup():

    files = [
        TEST_FILE,
        COPY_FILE,
        RENAMED_FILE,
        DOCUMENT_FILE,
    ]

    for file in files:

        try:

            if os.path.exists(file):

                os.remove(file)

                print(f"[CLEAN] Removed {file}")

        except Exception:

            pass


def execute(tool, args):

    response = requests.post(
        f"{BASE_URL}/execute",
        json={
            "tool": tool,
            "args": args,
        },
        timeout=30,
    )

    return response.json()


def test(name, tool, args):

    global PASS
    global FAIL

    print("=" * 70)
    print(name)

    try:

        result = execute(tool, args)

        if result.get("ok"):

            PASS += 1

            print("[PASS]")
            print(result["result"])

        else:

            FAIL += 1

            print("[FAIL]")
            print(result)

    except Exception as e:

        FAIL += 1

        print("[EXCEPTION]")
        print(e)


def main():

    cleanup()

    print("\n")
    print("=" * 70)
    print("MYRAA FILE SYSTEM TEST")
    print("=" * 70)

    # --------------------------------------------------
    # Create
    # --------------------------------------------------

    test(
        "Create File",
        "createFile",
        {
            "path": TEST_FILE,
            "content": "Hello from MYRAA!",
            "overwrite": True,
        },
    )

    # --------------------------------------------------
    # Read
    # --------------------------------------------------

    test(
        "Read File",
        "readFile",
        {
            "path": TEST_FILE,
        },
    )

    # --------------------------------------------------
    # Copy
    # --------------------------------------------------

    test(
        "Copy File",
        "copyFile",
        {
            "path": TEST_FILE,
            "destination": COPY_FILE,
        },
    )

    # --------------------------------------------------
    # Rename
    # --------------------------------------------------

    test(
        "Rename File",
        "renameFile",
        {
            "path": COPY_FILE,
            "new_name": "MYRAA_Renamed.txt",
        },
    )

    # --------------------------------------------------
    # Move
    # --------------------------------------------------

    test(
        "Move File",
        "moveFile",
        {
            "path": RENAMED_FILE,
            "destination": DOCUMENT_FILE,
        },
    )

    # --------------------------------------------------
    # Open
    # --------------------------------------------------

    test(
        "Open File",
        "openFile",
        {
            "path": DOCUMENT_FILE,
        },
    )

    # --------------------------------------------------
    # Search
    # --------------------------------------------------

    test(
        "Search Files",
        "searchFiles",
        {
            "folder": r"C:\Users\singh\OneDrive\Documents",
            "name": "MYRAA*",
        },
    )

    # --------------------------------------------------
    # Delete
    # --------------------------------------------------

    test(
        "Delete File",
        "deleteFile",
        {
            "path": DOCUMENT_FILE,
        },
    )

    print("\n")
    print("=" * 70)
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