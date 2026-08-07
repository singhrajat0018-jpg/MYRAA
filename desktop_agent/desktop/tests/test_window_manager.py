from desktop_agent.desktop.windows.window_manager import WindowManager

wm = WindowManager()

print("\n========== ACTIVE WINDOW ==========\n")
print(wm.get_active_window())

print("\n========== WINDOW LIST ==========\n")

for window in wm.list_windows():
    print(window)

print("\n========== TESTS ==========\n")

print("Chrome Exists :", wm.window_exists("chrome"))
print("VS Code Exists:", wm.window_exists("Visual Studio"))