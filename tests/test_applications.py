import requests
import time

BASE_URL = "http://127.0.0.1:8000/execute"


def execute(tool, args):
    r = requests.post(
        BASE_URL,
        json={
            "tool": tool,
            "args": args,
        },
    )
    return r.json()


print("=" * 60)
print("APPLICATION TEST")
print("=" * 60)

print("\nOpen Notepad")
print(execute("openApplication", {"application": "notepad"}))
time.sleep(2)

print("\nClose Notepad")
print(execute("closeApplication", {"application": "notepad"}))