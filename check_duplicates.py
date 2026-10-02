import sys
sys.path.append('C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA')
from desktop_agent.registry import TOOLS, DESKTOP_TOOL_NAMES, load_all
load_all()

all_tools = set(TOOLS.keys())
print(f"Total unique tools: {len(all_tools)}")

# Define categories
categories = {
    "Applications": [
        "openApplication", "closeApplication", "switchApplication"
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

print(f"Total categorized tools (with duplicates): {len(categorized_tools)}")

# Check for duplicates in categorized list
seen = set()
duplicates = []
for tool in categorized_tools:
    if tool in seen:
        duplicates.append(tool)
    else:
        seen.add(tool)

if duplicates:
    print(f"Duplicates found: {duplicates}")
else:
    print("No duplicates in categorized list")

# Get unique categorized tools
unique_categorized = set(categorized_tools)
print(f"Unique categorized tools: {len(unique_categorized)}")

# Find uncategorized tools
uncategorized = all_tools - unique_categorized
print(f"Uncategorized tools: {len(uncategorized)}")
if uncategorized:
    print("Uncategorized tools:", sorted(uncategorized))

# Check if all tools are covered
missing_from_categories = all_tools - unique_categorized
extra_in_categories = unique_categorized - all_tools

if missing_from_categories:
    print(f"Tools missing from categories: {sorted(missing_from_categories)}")
if extra_in_categories:
    print(f"Extra tools in categories (not in registry): {sorted(extra_in_categories)}")