"""
Ollama Provider
"""

from __future__ import annotations
import time
import requests

from ..provider import AIProvider


class OllamaProvider(AIProvider):

    def __init__(
        self,
        model: str = "qwen3:8b",
        host: str = "http://127.0.0.1:11434",
    ):

        self.model = model
        self.host = host
        self.session = requests.Session()
    @property
    def name(self):

        return "ollama"

    def available(self):

        try:

            r = requests.get(
                f"{self.host}/api/tags",
                timeout=2,
            )

            return r.status_code == 200

        except Exception:

            return False

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ):

        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": kwargs.get("stream", False),
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_ctx": kwargs.get("num_ctx", 4096),
            },
        }

        print("[OLLAMA] Sending request")

        start = time.perf_counter()

        response = self.session.post(
            f"{self.host}/api/generate",
            json=payload,
            timeout=120,
        )

        print(
            f"[OLLAMA] HTTP returned in {time.perf_counter()-start:.2f}s"
        )

        response.raise_for_status()

        data = response.json()

        print("[OLLAMA] JSON parsed")

        return data["response"]