import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from desktop_agent.brain.ai.ai_manager import Intent

def main():
    for idx, (name, member) in enumerate(Intent.__members__.items()):
        print(f"{idx}: {name} ({member.value})")

if __name__ == "__main__":
    main()