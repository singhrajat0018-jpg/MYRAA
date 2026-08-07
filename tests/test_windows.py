import requests
import time

BASE_URL = "http://127.0.0.1:8000/execute"

PASS = 0
FAIL = 0


def execute(tool, args):

    response = requests.post(
        BASE_URL,
        json={
            "tool": tool,
            "args": args,
        },
    )

    return response.json()


def test(title, tool, args):

    global PASS, FAIL

    print("=" * 70)
    print(title)

    try:

        result = execute(tool, args)

        if result.get("ok"):

            PASS += 1
            print("[PASS]")
            print(result)

        else:

            FAIL += 1
            print("[FAIL]")
            print(result)

    except Exception as e:

        FAIL += 1
        print("[ERROR]")
        print(e)


print()
print("=" * 70)
print("MYRAA WINDOW CONTROL TEST")
print("=" * 70)


# ---------------------------------------------------
# Open Notepad
# ---------------------------------------------------

test(
    "Open Notepad",
    "openApplication",
    {
        "application": "notepad"
    }
)

time.sleep(2)


# ---------------------------------------------------
# Minimize
# ---------------------------------------------------

test(
    "Minimize Window",
    "minimizeWindow",
    {
        "application": "notepad"
    }
)

time.sleep(2)


# ---------------------------------------------------
# Restore
# ---------------------------------------------------

test(
    "Restore Window",
    "restoreWindow",
    {
        "application": "notepad"
    }
)

time.sleep(2)


# ---------------------------------------------------
# Maximize
# ---------------------------------------------------

test(
    "Maximize Window",
    "maximizeWindow",
    {
        "application": "notepad"
    }
)

time.sleep(2)


# ---------------------------------------------------
# Activate
# ---------------------------------------------------

test(
    "Activate Window",
    "activateWindow",
    {
        "application": "notepad"
    }
)

time.sleep(2)


# ---------------------------------------------------
# Close
# ---------------------------------------------------

test(
    "Close Window",
    "closeWindow",
    {
        "application": "notepad"
    }
)

time.sleep(2)


print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

print(f"PASS : {PASS}")
print(f"FAIL : {FAIL}")

if FAIL == 0:

    print("\nALL TESTS PASSED")

else:

    print("\nSOME TESTS FAILED")