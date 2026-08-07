import time
import cv2

from desktop_agent.desktop.vision.frame_difference import FrameDifference
from desktop_agent.desktop.vision.screenshot_engine import ScreenshotEngine

engine = ScreenshotEngine()

detector = FrameDifference()

print("Capture First Screen")
first = engine.capture_screen()

time.sleep(5)

print("Capture Second Screen")
second = engine.capture_screen()

img1 = engine.to_opencv(first)
img2 = engine.to_opencv(second)

result = detector.compare(img1, img2)

print(result)

debug = detector.draw_regions(
    img2,
    result.regions,
)

cv2.imwrite(
    "frame_difference_debug.png",
    debug,
)

print("Debug image saved.")