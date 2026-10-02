#!/usr/bin/env python3

import sys
sys.path.append(r'C:\Users\singh\OneDrive\Desktop\MYRAA')

from desktop_agent.brain.memory.unified_model import MemoryRecord, MemoryScope, MemoryType, MemoryStatus
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import calculate_memory_similarity

# Test semantic similarity directly
query_record = MemoryRecord(
    content="pizza",
    source="query",
    importance=0.5,
    confidence=0.5,
    scope=MemoryScope.GLOBAL,
    status=MemoryStatus.ACTIVE
)

mem1 = MemoryRecord(
    content="User likes pizza",
    source="test",
    importance=0.5,
    confidence=0.5,
    scope=MemoryScope.USER,
    type=MemoryType.PREFERENCE
)

mem2 = MemoryRecord(
    content="User prefers Hinglish explanations",
    source="test",
    importance=0.5,
    confidence=0.5,
    scope=MemoryScope.USER,
    type=MemoryType.PREFERENCE
)

print(f"Query record: '{query_record.content}'")
print(f"  Type: {query_record.type.value}")
print(f"  Scope: {query_record.scope.value}")
print(f"Memory 1: '{mem1.content}'")
print(f"  Type: {mem1.type.value}")
print(f"  Scope: {mem1.scope.value}")
print(f"Memory 2: '{mem2.content}'")
print(f"  Type: {mem2.type.value}")
print(f"  Scope: {mem2.scope.value}")

sim1 = calculate_memory_similarity(query_record, mem1)
sim2 = calculate_memory_similarity(query_record, mem2)

print(f"\nSimilarity(query, mem1): {sim1:.4f}")
print(f"Similarity(query, mem2): {sim2:.4f}")

# Let's also check what the unified model similarity breakdown looks like
print("\n--- Manual breakdown for mem2 ---")
# Type similarity (0.2 if match)
type_sim = 0.2 if query_record.type == mem2.type else 0.0
print(f"Type similarity: {type_sim} (match: {query_record.type == mem2.type})")

# Scope similarity (0.15 if match)
scope_sim = 0.15 if query_record.scope == mem2.scope else 0.0
print(f"Scope similarity: {scope_sim} (match: {query_record.scope == mem2.scope})")

# Content similarity
content1 = query_record.content.lower().strip()
content2 = mem2.content.lower().strip()
print(f"Content1: '{content1}'")
print(f"Content2: '{content2}'")
if content1 == content2:
    content_sim = 0.3
    print(f"Content similarity: {content_sim} (exact match)")
elif content1 in content2 or content2 in content1:
    overlap = min(len(content1), len(content2))
    total = max(len(content1), len(content2))
    content_sim = 0.3 * (overlap / total if total > 0 else 0)
    print(f"Content similarity: {content_sim} (partial match)")
else:
    # Word overlap approach
    query_words = set(content1.split())
    mem_words = set(content2.split())
    print(f"Query words: {query_words}")
    print(f"Mem2 words: {mem_words}")
    if query_words:
        overlap = len(query_words.intersection(mem_words))
        content_sim = 0.3 * (overlap / len(query_words)) if len(query_words) > 0 else 0.0
        print(f"Content similarity: {content_sim} (word overlap: {overlap}/{len(query_words)})")
    else:
        content_sim = 0.0
        print(f"Content similarity: {content_sim} (no query words)")

# Project/task/context (0.1 each if match)
project_sim = 0.1 if (query_record.project_id == mem2.project_id and query_record.project_id is not None) else 0.0
print(f"Project similarity: {project_sim} (match: {query_record.project_id == mem2.project_id and query_record.project_id is not None})")
task_sim = 0.1 if (query_record.task_id == mem2.task_id and query_record.task_id is not None) else 0.0
print(f"Task similarity: {task_sim} (match: {query_record.task_id == mem2.task_id and query_record.task_id is not None})")
conv_sim = 0.1 if (query_record.conversation_id == mem2.conversation_id and query_record.conversation_id is not None) else 0.0
print(f"Conversation similarity: {conv_sim} (match: {query_record.conversation_id == mem2.conversation_id and query_record.conversation_id is not None})")

# Tags (0.1 if match)
if query_record.tags and mem2.tags:
    tag_overlap = len(query_record.tags.intersection(mem2.tags))
    tag_total = len(query_record.tags.union(mem2.tags))
    tag_sim = 0.1 * (tag_overlap / tag_total if tag_total > 0 else 0) if tag_total > 0 else 0.0
    print(f"Tags similarity: {tag_sim} (overlap: {tag_overlap}/{tag_total})")
else:
    tag_sim = 0.0
    print(f"Tags similarity: {tag_sim} (no tags)")

# Manual total
factors = []
score = 0.0

if query_record.type == mem2.type:
    score += 0.2
    factors.append(0.2)
if query_record.scope == mem2.scope:
    score += 0.15
    factors.append(0.15)
score += content_sim
factors.append(0.3)  # Content factor always applies
if query_record.project_id == mem2.project_id and query_record.project_id is not None:
    score += 0.1
    factors.append(0.1)
if query_record.task_id == mem2.task_id and query_record.task_id is not None:
    score += 0.1
    factors.append(0.1)
if query_record.conversation_id == mem2.conversation_id and query_record.conversation_id is not None:
    score += 0.1
    factors.append(0.1)
if query_record.tags and mem2.tags:
    score += tag_sim
    factors.append(0.1)  # Tag factor applies if both have tags

manual_score = score
manual_factors = sum(factors) if factors else 1.0  # Avoid division by zero
if manual_factors > 0:
    manual_final = manual_score / manual_factors
else:
    manual_final = 0.0

print(f"\nManual calculation:")
print(f"  Score: {manual_score:.4f}")
print(f"  Factors: {manual_factors:.4f}")
print(f"  Final: {manual_final:.4f}")
print(f"  Function result: {sim2:.4f}")

# Now mem1
print("\n--- Manual breakdown for mem1 ---")
# Type similarity (0.2 if match)
type_sim = 0.2 if query_record.type == mem1.type else 0.0
print(f"Type similarity: {type_sim} (match: {query_record.type == mem1.type})")

# Scope similarity (0.15 if match)
scope_sim = 0.15 if query_record.scope == mem1.scope else 0.0
print(f"Scope similarity: {scope_sim} (match: {query_record.scope == mem1.scope})")

# Content similarity
content1 = query_record.content.lower().strip()
content2 = mem1.content.lower().strip()
print(f"Content1: '{content1}'")
print(f"Content2: '{content2}'")
if content1 == content2:
    content_sim = 0.3
    print(f"Content similarity: {content_sim} (exact match)")
elif content1 in content2 or content2 in content1:
    overlap = min(len(content1), len(content2))
    total = max(len(content1), len(content2))
    content_sim = 0.3 * (overlap / total if total > 0 else 0)
    print(f"Content similarity: {content_sim} (partial match)")
else:
    # Word overlap approach
    query_words = set(content1.split())
    mem_words = set(content2.split())
    print(f"Query words: {query_words}")
    print(f"Mem1 words: {mem_words}")
    if query_words:
        overlap = len(query_words.intersection(mem_words))
        content_sim = 0.3 * (overlap / len(query_words)) if len(query_words) > 0 else 0.0
        print(f"Content similarity: {content_sim} (word overlap: {overlap}/{len(query_words)})")
    else:
        content_sim = 0.0
        print(f"Content similarity: {content_sim} (no query words)")

# Project/task/context (0.1 each if match)
project_sim = 0.1 if (query_record.project_id == mem1.project_id and query_record.project_id is not None) else 0.0
print(f"Project similarity: {project_sim} (match: {query_record.project_id == mem1.project_id and query_record.project_id is not None})")
task_sim = 0.1 if (query_record.task_id == mem1.task_id and query_record.task_id is not None) else 0.0
print(f"Task similarity: {task_sim} (match: {query_record.task_id == mem1.task_id and query_record.task_id is not None})")
conv_sim = 0.1 if (query_record.conversation_id == mem1.conversation_id and query_record.conversation_id is not None) else 0.0
print(f"Conversation similarity: {conv_sim} (match: {query_record.conversation_id == mem1.conversation_id and query_record.conversation_id is not None})")

# Tags (0.1 if match)
if query_record.tags and mem1.tags:
    tag_overlap = len(query_record.tags.intersection(mem1.tags))
    tag_total = len(query_record.tags.union(mem1.tags))
    tag_sim = 0.1 * (tag_overlap / tag_total if tag_total > 0 else 0) if tag_total > 0 else 0.0
    print(f"Tags similarity: {tag_sim} (overlap: {tag_overlap}/{tag_total})")
else:
    tag_sim = 0.0
    print(f"Tags similarity: {tag_sim} (no tags)")

# Manual total
factors = []
score = 0.0

if query_record.type == mem1.type:
    score += 0.2
    factors.append(0.2)
if query_record.scope == mem1.scope:
    score += 0.15
    factors.append(0.15)
score += content_sim
factors.append(0.3)  # Content factor always applies
if query_record.project_id == mem1.project_id and query_record.project_id is not None:
    score += 0.1
    factors.append(0.1)
if query_record.task_id == mem1.task_id and query_record.task_id is not None:
    score += 0.1
    factors.append(0.1)
if query_record.conversation_id == mem1.conversation_id and query_record.conversation_id is not None:
    score += 0.1
    factors.append(0.1)
if query_record.tags and mem1.tags:
    score += tag_sim
    factors.append(0.1)  # Tag factor applies if both have tags

manual_score = score
manual_factors = sum(factors) if factors else 1.0  # Avoid division by zero
if manual_factors > 0:
    manual_final = manual_score / manual_factors
else:
    manual_final = 0.0

print(f"\nManual calculation:")
print(f"  Score: {manual_score:.4f}")
print(f"  Factors: {manual_factors:.4f}")
print(f"  Final: {manual_final:.4f}")
print(f"  Function result: {sim1:.4f}")