import cv2

from desktop_agent.desktop.vision.image_processor import ImageProcessor
from desktop_agent.desktop.vision.screenshot_engine import ScreenshotEngine

capture = ScreenshotEngine()
processor = ImageProcessor()

shot = capture.capture_screen()
img = capture.to_opencv(shot)

# ---------- Part 1 ----------
gray = processor.grayscale(img)
small = processor.scale(gray, 0.5)
crop = processor.crop(img, 300, 300, 500, 300)
rotated = processor.rotate(img, 15)

# ---------- Part 2 ----------
blur = processor.gaussian_blur(img)
median = processor.median_blur(img)
sharp = processor.sharpen(img)
denoise = processor.denoise(img)
binary = processor.threshold(img)
adaptive = processor.adaptive_threshold(img)
otsu = processor.otsu_threshold(img)

# ---------- Save ----------
cv2.imwrite("gray.png", gray)
cv2.imwrite("small.png", small)
cv2.imwrite("crop.png", crop)
cv2.imwrite("rotated.png", rotated)

cv2.imwrite("blur.png", blur)
cv2.imwrite("median.png", median)
cv2.imwrite("sharp.png", sharp)
cv2.imwrite("denoise.png", denoise)
cv2.imwrite("binary.png", binary)
cv2.imwrite("adaptive.png", adaptive)
cv2.imwrite("otsu.png", otsu)

print("Image Processor Complete")