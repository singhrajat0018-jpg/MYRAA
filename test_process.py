from desktop_agent.desktop.windows.process_manager import ProcessManager

pm = ProcessManager()

print(pm.find_process("notepad"))