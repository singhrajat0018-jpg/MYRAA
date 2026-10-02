#!/usr/bin/env python3

import sys
sys.path.append(r'C:\Users\singh\OneDrive\Desktop\MYRAA')

from desktop_agent.brain.memory.unified_model import MemoryRecord, MemoryScope, MemoryType
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager

# Test scope filtering directly
manager = UnifiedMemoryManager()

# Create test memories
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

for mem in memories:
    manager.remember(mem)

print("Testing _calculate_scope_score directly:")
test_scope = MemoryScope.GLOBAL
print(f"Testing scope: {test_scope.value}")

for i, mem in enumerate([memories[0], memories[1], memories[2], memories[3]]):
    score = manager._calculate_scope_score(mem, test_scope)
    print(f"  Memory {i} ('{mem.content}'): scope={mem.scope.value} -> score={score}")

print("\nTesting recall_by_scope:")
results = manager.recall_by_scope(MemoryScope.GLOBAL)
print(f"Found {len(results)} results:")
for i, result in enumerate(results):
    print(f"  {i}: {result.content} (scope={result.scope.value})")