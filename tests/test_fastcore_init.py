"""FastCore initial test — generate dataset + benchmark classifier."""
import sys, time, statistics
sys.path.insert(0, '.')

from desktop_agent.fastcore import DatasetGenerator, FastCoreClassifier

# Generate dataset
gen = DatasetGenerator()
examples = gen.generate()
stats = gen.save(examples, 'desktop_agent/fastcore/dataset/fastcore_v0.1.0.json')

print('=== FastCore Dataset ===')
print(f'Total examples: {stats["total"]}')
print(f'Families: {stats["families"]}')
print(f'Task types: {stats["task_types"]}')

# Test classifier latency
c = FastCoreClassifier()
texts = [
    'Hello', 'What is Python', 'Open Notepad', 'Analyze NIFTY',
    'Design a bike', 'Latest news', 'What is on my screen', 'Build a project',
    'Close Chrome', 'Who is Alan Turing', 'Read the config file',
    'Navigate to github.com', 'Create a file', 'Search YouTube for AI',
]
all_times = []
for _ in range(100):
    for t in texts:
        start = time.perf_output() if hasattr(time, 'perf_output') else time.perf_counter()
        result = c.classify(t)
        elapsed = (time.perf_counter() - start) * 1000
        all_times.append(elapsed)

print(f'\n=== Classifier Latency ({100} runs x {len(texts)} texts) ===')
print(f'P50: {statistics.median(all_times):.3f}ms')
print(f'P95: {sorted(all_times)[int(len(all_times)*0.95)]:.3f}ms')
print(f'P99: {sorted(all_times)[int(len(all_times)*0.99)]:.3f}ms')
print(f'Max: {max(all_times):.3f}ms')
print(f'Total: {sum(all_times):.1f}ms')

# Verify classifications
print('\n=== Sample Classifications ===')
test_cases = [
    ('Hello', 'conversation'),
    ('What is Python', 'direct_knowledge'),
    ('Open Notepad', 'desktop_action'),
    ('Analyze NIFTY', 'trading_task'),
    ('Design a bike', 'design_task'),
    ('Latest Python version', 'current_information'),
    ('What is on my screen', 'vision_task'),
    ('Build a Python project', 'coding_task'),
    ('Search for documentation', 'web_research'),
    ('Read the config file', 'file_task'),
]
passed = 0
for text, expected in test_cases:
    result = c.classify(text)
    status = 'PASS' if result.task_type.value == expected else 'FAIL'
    if status == 'PASS':
        passed += 1
    print(f'  {status}: "{text}" -> {result.task_type.value} (expected {expected})')

print(f'\nAccuracy: {passed}/{len(test_cases)}')
