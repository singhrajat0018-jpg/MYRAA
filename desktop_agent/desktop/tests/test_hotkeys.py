from desktop_agent.desktop.input.hotkeys import HotkeyManager

hotkeys = HotkeyManager()

print("Available Actions:")
print(hotkeys.available_actions())

print()

print("Executing Run Dialog...")

hotkeys.safe_execute("run")

print("Done")