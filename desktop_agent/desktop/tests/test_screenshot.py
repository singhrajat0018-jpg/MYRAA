from desktop_agent.desktop.vision.screenshot_engine import ScreenshotEngine

with ScreenshotEngine() as engine:

    print("Monitor Count:", engine.monitor_count())

    result = engine.capture_screen()

    print("Resolution:", engine.resolution(result))

    cropped = engine.crop(
        result,
        100,
        100,
        500,
        400,
    )

    engine.save_timestamped(cropped)

    resized = engine.resize(
        cropped,
        300,
        200,
    )

    print(engine.image_size(resized))

    print(type(engine.capture_for_opencv()))

print("Screenshot Engine Complete")