from __future__ import annotations


class ServiceRegistry:
    def __init__(self):
        self._services = {}

    def register(self, name: str, service):
        self._services[name] = service

    def get(self, name: str):
        if name not in self._services:
            raise KeyError(f"Service '{name}' is not registered.")
        return self._services[name]

    def has(self, name: str):
        return name in self._services