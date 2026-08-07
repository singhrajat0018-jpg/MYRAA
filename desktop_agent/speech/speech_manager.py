"""
Speech recognition coordinator.

This class will become the single entry point
for every spoken sentence in MYRAA.
"""

from __future__ import annotations

from .audio_queue import AudioQueue


class SpeechManager:

    def __init__(self) -> None:
        self.audio_queue = AudioQueue()

    def enqueue_audio(self, pcm: bytes) -> None:
        """
        Called whenever new microphone audio arrives.
        """
        # Implementation in Part 2
        pass

    def process(self) -> None:
        """
        Background speech processing loop.
        """
        # Implementation in Part 2
        pass