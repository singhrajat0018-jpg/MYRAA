from desktop_agent.desktop.vision.live_capture import LiveCaptureEngine

import time


def on_frame(frame):

    print(
        "Frame:",
        frame.width,
        frame.height,
    )


with LiveCaptureEngine(fps=2) as vision:

    vision.set_frame_callback(on_frame)

    time.sleep(5)

    print()

    print(vision.status())