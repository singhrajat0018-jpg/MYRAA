from desktop_agent.desktop.input.mouse import MouseController
import time

mouse = MouseController()

print("Current:", mouse.position())

time.sleep(2)

print("Moving...")
mouse.move(800, 500)

time.sleep(1)

print("Left Click")
mouse.left_click()

time.sleep(1)

print("Right Click")
mouse.right_click()

time.sleep(1)

print("Double Click")
mouse.double_click()

time.sleep(1)

print("Scrolling Down")
mouse.scroll_down(800)

time.sleep(1)

print("Scrolling Up")
mouse.scroll_up(800)

print("Done!")