import sys
sys.path.append('C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA')
from desktop_agent.registry import TOOLS, DESKTOP_TOOL_NAMES, load_all
load_all()

# Define categories
categories = {
    "Applications": [
        "openApplication", "closeApplication"
        # switchApplication moved to Windows as it's primarily a window operation
    ],
    "Websites/Search": [
        "openWebsite", "searchWeb", "searchYouTube", "searchGoogle", "searchGitHub"
    ],
    "Files": [
        "createFile", "readFile", "renameFile", "deleteFile", "moveFile",
        "openFolder", "listFiles", "searchFiles", "copyFile", "openFile", "writeFile"
    ],
    "PC control": [
        "volumeUp", "volumeDown", "setVolume", "muteToggle",
        "brightnessUp", "brightnessDown", "setBrightness",
        "requestPowerAction", "executePowerAction", "_cancelPowerTimer"
    ],
    "Windows": [
        "minimizeWindow", "maximizeWindow", "activateWindow",
        "restoreWindow", "closeWindow", "switchApplication"
    ],
    "Clipboard": [
        "copySelected", "pasteClipboard", "getClipboard", "clearClipboard"
    ],
    "Screen/OCR": [
        "takeScreenshot", "saveScreenshot", "takeRegionScreenshot",
        "analyzeScreenshot", "readScreen"
    ],
    "Browser": [
        "desktopBrowserOpen", "desktopBrowserNavigate", "desktopBrowserOpenTab",
        "desktopBrowserCloseTab", "desktopBrowserSearch"
        # Note: Click, Type, FillForm, GoBack, GoForward, Scroll were removed in browser-agnostic mode
    ],
    "Coding": [
        "createPythonFile", "runPythonScript", "createProjectFolder", "writeCodeFile"
    ],
    "System info": [
        "systemInfo", "gpuInfo", "temperatureInfo", "currentDateTime"
    ],
    "Auto-start": [
        "enableAutoStart", "disableAutoStart", "getAutoStartStatus"
    ],
    "Keyboard": [
        "typeText", "pressKey", "keyDown", "keyUp", "hotkey"
    ],
    "Mouse": [
        "moveMouse", "leftClick", "rightClick", "doubleClick", "middleClick",
        "dragMouse", "scrollMouse", "mousePosition"
    ],
    "Terminal": [
        "runShellCommand", "runCommand"
    ],
    "Git": [
        "gitStatus", "gitDiff", "gitLog", "gitAdd", "gitCommit",
        "gitPush", "gitPull", "gitBranch", "gitCheckout"
    ]
}

# Flatten all categorized tools
categorized_tools = []
for category, tools in categories.items():
    categorized_tools.extend(tools)

# Find uncategorized tools
all_tools = set(TOOLS.keys())
categorized_set = set(categorized_tools)
uncategorized = all_tools - categorized_set

print("=== MYRAA CAPABILITY MATRIX ===\n")

for category, tools in categories.items():
    print(f"{category} ({len(tools)} tools):")
    for tool in sorted(tools):
        print(f"  [+] {tool}")
    print()

if uncategorized:
    print(f"UNCATEGORIZED TOOLS ({len(uncategorized)}):")
    for tool in sorted(uncategorized):
        print(f"  [!] {tool}")
    print()

print(f"SUMMARY:")
print(f"  Total tools in registry: {len(TOOLS)}")
print(f"  Categorized tools: {len([t for cat in categories.values() for t in cat])}")  # Count with duplicates for display
print(f"  Unique categorized tools: {len(categorized_set)}")
print(f"  Uncategorized tools: {len(uncategorized)}")