#!/usr/bin/env python3
import sys
import os

# Add the MYRAA directory to the path so desktop_agent can be found as a package
myraa_path = os.path.join(os.path.dirname(__file__), '..')
myraa_path = os.path.normpath(myraa_path)
sys.path.insert(0, myraa_path)

from desktop_agent.brain.ai.ai_manager import AIManager

ai_manager = AIManager()

# Test the working examples from existing tests
working_examples = [
    "Rahul ko message karde, main 10 min late aaunga.",
    "Raj ko WhatsApp kar do",
    "Priya ko email bhej do meeting agenda",
]

# Test my proposed examples
my_examples = [
    "Rahul ko WhatsApp pe message karde",
    "Priya ko bol do ki meeting 5 baje hai",
    "Rahul ko last message ka reply kar do",
    "Family group mein bol do ki main ghar late aaunga",
    "Priya ko email kar do ki meeting 5 baje hai",
    "Professor ko mail karo ki main kal class attend nahi kar paunga",
    "Latest project report Rahul ko email kar do",
    "Is document ko Gmail se send kar do",
]

# Test Phase 10 project-related examples
project_examples = [
    "create a new project",
    "open the project",
    "list all projects",
    "find the project",
    "project ki jankari do",
    "project shuru karo",
    "project kholo",
    "projects dikhao",
    "project dhoondo",
    "search for project",
    "new project banayo",
    "open project karo",
    "show me projects",
    "project details batao",
]

print("=== WORKING EXAMPLES (from existing tests) ===")
for prompt in working_examples:
    route = ai_manager.route(prompt)
    print(f"'{prompt}'")
    print(f"  Intent: {route.intent.name}")
    print(f"  Capability: {route.capability}")
    print()

print("=== MY EXAMPLES (from phase 9 tests) ===")
for prompt in my_examples:
    route = ai_manager.route(prompt)
    print(f"'{prompt}'")
    print(f"  Intent: {route.intent.name}")
    print(f"  Capability: {route.capability}")
    print()

print("=== PROJECT EXAMPLES (Phase 10) ===")
for prompt in project_examples:
    route = ai_manager.route(prompt)
    print(f"'{prompt}'")
    print(f"  Intent: {route.intent.name}")
    print(f"  Capability: {route.capability}")
    print()