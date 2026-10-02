#!/usr/bin/env python3

import sys
sys.path.append(r'C:\Users\singh\OneDrive\Desktop\MYRAA')

from desktop_agent.brain.memory.unified_model import MemoryRecord, MemoryScope, MemoryType, MemoryStatus
from desktop_agent.brain.memory.unified_model import calculate_memory_similarity

# Exactly replicate what happens in _semantic_retrieval
query = "pizza"
query_record = MemoryRecord(
    content=query,
    source="query",
    importance=0.5,
    confidence=0.5,
    scope=MemoryScope.GLOBAL,
    status=MemoryStatus.ACTIVE
)

mem2 = MemoryRecord(
    content="User prefers Hinglish explanations",
    source="test",
    importance=0.5,
    confidence=0.5,
    scope=MemoryScope.USER,
    type=MemoryType.PREFERENCE
)

print("=== Query Record ===")
print(f"id: {query_record.id}")
print(f"content: '{query_record.content}'")
print(f"type: {query_record.type.value}")
print(f"scope: {query_record.scope.value}")
print(f"fingerprint: {query_record.fingerprint}")

print("\n=== Memory 2 Record ===")
print(f"id: {mem2.id}")
print(f"content: '{mem2.content}'")
print(f"type: {mem2.type.value}")
print(f"scope: {mem2.scope.value}")
print(f"fingerprint: {mem2.fingerprint}")

# Calculate similarity step by step to see what's happening
print("\n=== Similarity Calculation Steps ===")

# Check fingerprint
if query_record.fingerprint == mem2.fingerprint:
    print("Fingerprints match - returning 1.0")
else:
    print("Fingerprints do NOT match")

score = 0.0
factors = 0
print(f"Initial: score={score}, factors={factors}")

# Type similarity
type_match = query_record.type == mem2.type
if type_match:
    score += 0.2
    print(f"Type match: YES -> score += 0.2")
else:
    print(f"Type match: NO ({query_record.type.value} != {mem2.type.value}) -> score += 0.0")
factors += 0.2
print(f"After type: score={score}, factors={factors}")

# Scope similarity
scope_match = query_record.scope == mem2.scope
if scope_match:
    score += 0.15
    print(f"Scope match: YES -> score += 0.15")
else:
    print(f"Scope match: NO ({query_record.scope.value} != {mem2.scope.value}) -> score += 0.0")
factors += 0.15
print(f"After scope: score={score}, factors={factors}")

# Content similarity
content1 = query_record.content.lower().strip()
content2 = mem2.content.lower().strip()
print(f"Content 1: '{content1}'")
print(f"Content 2: '{content2}'")

if content1 == content2:
    score += 0.3
    print(f"Content exact match: YES -> score += 0.3")
elif content1 in content2 or content2 in content1:
    overlap = min(len(content1), len(content2))
    total = max(len(content1), len(content2))
    score += 0.3 * (overlap / total)
    print(f"Content partial match: YES -> score += 0.3 * ({overlap}/{total})")
else:
    # Word overlap
    query_words = set(content1.split())
    mem2_words = set(content2.split())
    overlap = len(query_words.intersection(mem2_words))
    if len(query_words) > 0:
        score += 0.3 * (overlap / len(query_words))
        print(f"Content word overlap: YES -> score += 0.3 * ({overlap}/{len(query_words)})")
    else:
        print(f"Content word overlap: NO query words -> score += 0.0")
factors += 0.3
print(f"After content: score={score}, factors={factors}")

# Project/task/context alignment
project_match = query_record.project_id == mem2.project_id
if project_match and query_record.project_id is not None:
    score += 0.1
    print(f"Project match: YES -> score += 0.1")
else:
    print(f"Project match: NO -> score += 0.0")
factors += 0.1
print(f"After project: score={score}, factors={factors}")

task_match = query_record.task_id == mem2.task_id
if task_match and query_record.task_id is not None:
    score += 0.1
    print(f"Task match: YES -> score += 0.1")
else:
    print(f"Task match: NO -> score += 0.0")
factors += 0.1
print(f"After task: score={score}, factors={factors}")

conv_match = query_record.conversation_id == mem2.conversation_id
if conv_match and query_record.conversation_id is not None:
    score += 0.1
    print(f"Conversation match: YES -> score += 0.1")
else:
    print(f"Conversation match: NO -> score += 0.0")
factors += 0.1
print(f"After conversation: score={score}, factors={factors}")

# Tags overlap
if query_record.tags and mem2.tags:
    tag_overlap = len(query_record.tags.intersection(mem2.tags))
    tag_total = len(query_record.tags.union(mem2.tags))
    if tag_total > 0:
        score += 0.1 * (tag_overlap / tag_total)
        print(f"Tags overlap: YES -> score += 0.1 * ({tag_overlap}/{tag_total})")
    else:
        print(f"Tags overlap: YES but zero total -> score += 0.0")
else:
    print(f"Tags overlap: NO (one or both empty) -> score += 0.0")
factors += 0.1
print(f"After tags: score={score}, factors={factors}")

# Normalize
if factors > 0:
    final_score = score / factors
    print(f"Final: score({score}) / factors({factors}) = {final_score}")
else:
    final_score = 0.0
    print(f"Final: factors <= 0 -> 0.0")

print(f"\nFunction result: {calculate_memory_similarity(query_record, mem2)}")

# Let's also test mem1 for comparison
print("\n" + "="*50)
print("COMPARISON WITH MEM1")
mem1 = MemoryRecord(
    content="User likes pizza",
    source="test",
    importance=0.5,
    confidence=0.5,
    scope=MemoryScope.USER,
    type=MemoryType.PREFERENCE
)

print(f"Memory 1: '{mem1.content}' (type: {mem1.type.value}, scope: {mem1.scope.value})")

# Quick similarity
sim1 = calculate_memory_similarity(query_record, mem1)
sim2 = calculate_memory_similarity(query_record, mem2)
print(f"Similarity with mem1: {sim1:.4f}")
print(f"Similarity with mem2: {sim2:.4f}")