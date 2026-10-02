import sys
sys.path.append('C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA')
from desktop_agent.registry import TOOLS, DESKTOP_TOOL_NAMES, load_all
load_all()
print('Total tools:', len(TOOLS))
print('Desktop tool names:', len(DESKTOP_TOOL_NAMES))
print('\nAll tools:')
for name in sorted(TOOLS.keys()):
    print(f'  {name}')