#!/usr/bin/env python3

import sys
sys.path.append(r'C:\Users\singh\OneDrive\Desktop\MYRAA')

from desktop_agent.brain.memory.unified_model import MemoryRecord, MemoryScope, MemoryType
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager

# Create manager and test memories
manager = UnifiedMemoryManager()

memories = [
    MemoryRecord(content="User prefers Hinglish explanations", source="test",
                importance=0.9, confidence=0.95, scope=MemoryScope.USER,
                type=MemoryType.PREFERENCE),
    MemoryRecord(content="User is working on MYRAA project", source="test",
                importance=0.8, confidence=0.9, scope=MemoryScope.PROJECT,
                type=MemoryType.PROJECT, project_id="MYRAA"),
    MemoryRecord(content="User likes pizza", source="test",
                importance=0.5, confidence=0.8, scope=MemoryScope.USER,
                type=MemoryType.PREFERENCE)
]

for mem in memories:
    manager.remember(mem)

print("All memories:")
for i, mem in enumerate(memories):
    print(f"{i}: {mem.content}")

print("\nSearching for 'pizza':")
results = manager.recall_by_content("pizza", limit=5)
print(f"Found {len(results)} results:")
for i, result in enumerate(results):
    print(f"{i}: {result.content}")

print("\nSearching for 'Hinglish':")
results = manager.recall_by_content("Hinglish", limit=5)
print(f"Found {len(results)} results:")
for i, result in enumerate(results):
    print(f"{i}: {result.content}")

print("\nSearching for 'user':")
results = manager.recall_by_content("user", limit=10)
print(f"Found {len(results)} results:")
for i, result in enumerate(results):
    print(f"{i}: {result.content}")