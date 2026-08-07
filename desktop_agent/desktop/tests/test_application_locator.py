from desktop_agent.desktop.windows.application_locator import ApplicationLocator

locator = ApplicationLocator()

apps = [
    "chrome",
    "code",
    "msedge",
    "spotify",
]

for app in apps:

    print("\n==========================")
    print(app.upper())
    print("==========================")

    info = locator.locate(app)

    print(info)