from desktop_agent.desktop.windows.process_manager import ProcessManager

pm = ProcessManager()

print("\n===== PROCESS COUNT =====\n")

processes = pm.list_processes()

print(len(processes))

print("\n===== FIRST 10 =====\n")

for p in processes[:10]:
    print(p)

print("\n===== TESTS =====\n")

print("Chrome Running :", pm.is_running("chrome"))
print("Edge Running   :", pm.is_running("msedge"))
print("VS Code Running:", pm.is_running("Code"))

print("\n===== FIND =====\n")

print(pm.find_process("chrome"))