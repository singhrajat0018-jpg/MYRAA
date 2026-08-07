from desktop_agent.desktop.windows.window_manager import WindowManager

for w in WindowManager().list_windows():
    print(w)