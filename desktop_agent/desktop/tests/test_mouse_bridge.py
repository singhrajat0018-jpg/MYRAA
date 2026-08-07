import asyncio

from desktop_agent.desktop.input.mouse_bridge import MouseToolBridge


async def test_mouse():

    mouse = MouseToolBridge()

    print("Moving mouse...")

    await mouse.move_mouse(
        500,
        300
    )

    print("Clicking...")

    await mouse.click(
        500,
        300
    )

    print("MOUSE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(
        test_mouse()
    )