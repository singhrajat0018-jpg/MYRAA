from desktop_agent.desktop.windows.application_locator import ApplicationLocator

locator = ApplicationLocator()

info = locator.locate("notepad")

print(info)