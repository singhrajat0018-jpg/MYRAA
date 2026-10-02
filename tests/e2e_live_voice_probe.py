"""E2E: connect to MYRAA /live and verify the Gemini Live session opens
with a supported voice (no 1007 'No matching speaker voice')."""
import asyncio
import json
import sys

import websockets


async def main():
    statuses = []
    async with websockets.connect("ws://127.0.0.1:3000/live",
                                  open_timeout=10, close_timeout=5) as ws:
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                if msg.get("type") == "status":
                    statuses.append(msg)
                    print("STATUS:", msg)
                    if msg.get("status") == "connected":
                        voice = msg.get("voice", "?")
                        print(f"RESULT: GEMINI LIVE CONNECTED (voice={voice})")
                        return 0 if voice in {"Leda", "Aoede", "Kore",
                                              "Zephyr", "Puck"} else 1
                    if msg.get("status") == "voice_degraded":
                        print("RESULT: VOICE DEGRADED")
                        return 1
                    if msg.get("status") == "session_closed":
                        print("RESULT: SESSION CLOSED EARLY")
                        return 1
                elif msg.get("type") == "error":
                    print("ERROR MSG:", str(msg.get("error"))[:200])
        except asyncio.TimeoutError:
            print("STATUS SEQUENCE:", [s.get("status") for s in statuses])
            print("RESULT: TIMEOUT waiting for connected status")
            return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
