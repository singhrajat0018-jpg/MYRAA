import subprocess

import pytest

from desktop_agent.registry import ToolError
from desktop_agent.tools_applications import close_application, open_application


class FakeAppInfo:
    def __init__(self, running: bool):
        self.running = running


class FakeLocator:
    states = []
    focused = []

    def locate(self, name):
        running = self.states.pop(0) if self.states else False
        return FakeAppInfo(running)

    def focus(self, name):
        self.focused.append(name)


def test_open_application_launches_and_focuses_when_detected(monkeypatch):
    FakeLocator.states = [False, True]
    FakeLocator.focused = []
    launched = []
    sleeps = []

    monkeypatch.setattr(
        "desktop_agent.tools_applications.ApplicationLocator",
        FakeLocator,
    )
    monkeypatch.setattr(
        "desktop_agent.tools_applications._launch",
        lambda spec: launched.append(spec),
    )
    monkeypatch.setattr(
        "desktop_agent.tools_applications.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = open_application({"application": "notepad"})

    assert result == {"result": "Notepad opened and focused."}
    assert launched[0]["image"] == "notepad.exe"
    assert FakeLocator.focused == ["notepad"]
    assert sleeps == [0.25]


def test_open_application_focuses_existing_instance(monkeypatch):
    FakeLocator.states = [True]
    FakeLocator.focused = []

    monkeypatch.setattr(
        "desktop_agent.tools_applications.ApplicationLocator",
        FakeLocator,
    )

    result = open_application({"name": "google chrome"})

    assert result == {
        "result": "Google Chrome is already running. Focused existing window."
    }
    assert FakeLocator.focused == ["google chrome"]


def test_open_application_rejects_unknown_app():
    with pytest.raises(ToolError, match="Unrecognized application"):
        open_application({"application": "definitely-not-installed"})


def test_close_application_runs_taskkill(monkeypatch):
    commands = []
    sleeps = []

    class FakeProcessManager:
        def is_running(self, image):
            return False

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("desktop_agent.tools_applications.ProcessManager", FakeProcessManager)
    monkeypatch.setattr("desktop_agent.tools_applications.subprocess.run", fake_run)
    monkeypatch.setattr(
        "desktop_agent.tools_applications.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = close_application({"application": "notepad"})

    assert result == {"result": "Closed Notepad."}
    assert commands[0][0] == 'taskkill /IM "notepad.exe"'
    assert sleeps == [0.5]
