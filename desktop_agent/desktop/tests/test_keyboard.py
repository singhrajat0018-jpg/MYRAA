from desktop_agent.desktop.input.keyboard import KeyboardController
import subprocess
import time

# Open Notepad
subprocess.Popen("notepad.exe")

time.sleep(2)

kbd = KeyboardController()

kbd.type_text("Hello MYRAA!")
kbd.enter()
kbd.type_text("Keyboard Controller Working")

print("✅ Test Complete")