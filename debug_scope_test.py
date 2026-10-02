#!/usr/bin/env python3

import sys
import tempfile
import os
sys.path.append(r'C:\Users\singh\OneDrive\Desktop\MYRAA')

from desktop_agent.brain.memory.unified_model import MemoryRecord, MemoryScope, MemoryType
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager

# Replicate the exact test setup
temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
temp_file.close()
manager = UnifiedMemoryManager(temp_file.name)

# Remember the exact memories from the test
memories = [
    MemoryRecord(content="Global memory", source="test",
                importance=0.7, confidence=0.8, scope=MemoryScope.GLOBAL,
                type=MemoryType.SEMANTIC),
    MemoryRecord(content="User preference", source="test",
                importance=0.9, confidence=0.95, scope=MemoryScope.USER,
                type=MemoryType.PREFERENCE),
    MemoryRecord(content="MYRAA project detail", source="test",
                importance=0.8, confidence=0.9, scope=MemoryScope.PROJECT,
                type=MemoryType.PROJECT, project_id="MYRAA"),
    MemoryRecord(content="Task step completed", source="test",
                importance=0.75, confidence=0.85, scope=MemoryScope.TASK,
                type=MemoryType.TASK, task_id="task_123")
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
    print(f"  {i}: {mem.content} (scope={mem.scope.value}, importance={mem.importance:.2f})")

print("\nTesting _calculate_scope_score for GLOBAL scope:")
test_scope = MemoryScope.GLOBAL
for i, mem in enumerate(all_memories):
    score = manager._calculate_scope_score(mem, test_scope)
    print(f"  Memory {i} ('{mem.content}'): scope={mem.scope.value} -> score={score}")

print("\nTesting recall_by_scope(GLOBAL):")
results = manager.recall_by_scope(MemoryScope.GLOBAL)
print(f"Found {len(results)} results:")
for i, result in enumerate(results):
    print(f"  {i}: {result.content} (scope={result.scope.value})")

# Clean up
os.unlink(temp_file.name)