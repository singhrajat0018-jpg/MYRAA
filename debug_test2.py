#!/usr/bin/env python3

import sys
import tempfile
import os
sys.path.append(r'C:\Users\singh\OneDrive\Desktop\MYRAA')

from desktop_agent.brain.memory.unified_model import MemoryRecord, MemoryScope, MemoryType
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager

# Replicate the test setup
temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
temp_file.close()
manager = UnifiedMemoryManager(temp_file.name)

# Remember the same memories as in the test
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

print("Remembering memories:")
for i, mem in enumerate(memories):
    result = manager.remember(mem)
    print(f"  {i}: {mem.content} -> {result}")

print(f"\nTotal memories in manager: {manager.get_count()}")
print(f"Active memories in manager: {manager.get_active_count()}")

print("\nAll memories in manager:")
all_memories = manager.get_all_active()
for i, mem in enumerate(all_memories):
    print(f"  {i}: {mem.content} (importance={mem.importance:.2f}, confidence={mem.confidence:.2f})")

print("\nSearching for 'pizza':")
results = manager.recall_by_content("pizza", limit=5)
print(f"Found {len(results)} results:")
for i, result in enumerate(results):
    print(f"  {i}: {result.content} (score would be calculated)")

# Clean up
os.unlink(temp_file.name)