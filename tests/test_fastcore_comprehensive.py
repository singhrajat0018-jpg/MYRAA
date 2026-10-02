"""FastCore comprehensive classification test."""
import sys, time, statistics, json
sys.path.insert(0, '.')

from desktop_agent.fastcore import FastCoreClassifier, DatasetGenerator

# Load dataset
gen = DatasetGenerator()
examples = gen.generate()

c = FastCoreClassifier()

# Test all dataset examples
passed = 0
failed = 0
failures = []
for ex in examples:
    result = c.classify(ex.input_text)
    expected = ex.task_type.value
    if result.task_type.value == expected:
        passed += 1
    else:
        failed += 1
        failures.append((ex.input_text, expected, result.task_type.value))

print(f'=== Dataset Classification: {passed}/{passed+failed} ===')
if failures:
    print('Failures:')
    for text, exp, got in failures[:20]:
        print(f'  "{text}" -> {got} (expected {exp})')

# Additional edge cases
edge_cases = [
    ("Hello Myraa", "conversation"),
    ("Hi", "conversation"),
    ("Good morning Myraa", "conversation"),
    ("Thank you so much", "conversation"),
    ("What is Python", "direct_knowledge"),
    ("Who is Elon Musk", "direct_knowledge"),
    ("Explain quantum computing", "direct_knowledge"),
    ("Difference between TCP and UDP", "direct_knowledge"),
    ("Latest Python version", "current_information"),
    ("Current NIFTY price", "trading_task"),
    ("Today's top news", "current_information"),
    ("Recent AI breakthroughs", "current_information"),
    ("Open Notepad", "desktop_action"),
    ("Close Chrome", "desktop_action"),
    ("Volume up", "desktop_action"),
    ("Shutdown the computer", "desktop_action"),
    ("Take a screenshot", "desktop_action"),
    ("Open YouTube", "browser_action"),
    ("Search Google for Python docs", "browser_action"),
    ("Navigate to github.com", "browser_action"),
    ("Create a file called test.txt", "file_task"),
    ("Read the config file", "file_task"),
    ("Delete old logs", "file_task"),
    ("List files in Documents", "file_task"),
    ("What's on my screen", "vision_task"),
    ("Read this chart", "vision_task"),
    ("Analyze NIFTY", "trading_task"),
    ("Stock price of Reliance", "trading_task"),
    ("Build a Python project", "coding_task"),
    ("Write a script to sort files", "coding_task"),
    ("Debug this code", "coding_task"),
    ("Design a futuristic bike", "design_task"),
    ("Sketch a motorcycle concept", "design_task"),
    ("Search for documentation", "web_research"),
    ("Research latest AI models", "web_research"),
    ("Compare React and Vue", "direct_knowledge"),
    # Hard negatives
    ("Hello, can you search Python", "browser_action"),
    ("Tell me about today's Python news", "current_information"),
    ("Can you open the Python website", "browser_action"),
    ("Search YouTube for AI news", "browser_action"),
    ("Read the screen and tell me what's there", "vision_task"),
    ("Create a file with today's news", "file_task"),
    ("Open Notepad and write a Python script", "desktop_action"),
    ("What's the weather like today", "current_information"),
]

edge_passed = 0
edge_failed = 0
edge_failures = []
for text, expected in edge_cases:
    result = c.classify(text)
    if result.task_type.value == expected:
        edge_passed += 1
    else:
        edge_failed += 1
        edge_failures.append((text, expected, result.task_type.value))

print(f'\n=== Edge Cases: {edge_passed}/{edge_passed+edge_failed} ===')
if edge_failures:
    print('Failures:')
    for text, exp, got in edge_failures:
        print(f'  "{text}" -> {got} (expected {exp})')

# Latency benchmark
all_times = []
for _ in range(500):
    for text, _ in edge_cases:
        start = time.perf_counter()
        c.classify(text)
        all_times.append((time.perf_counter() - start) * 1000)

print(f'\n=== Latency (500 runs x {len(edge_cases)} texts) ===')
print(f'P50: {statistics.median(all_times):.3f}ms')
print(f'P95: {sorted(all_times)[int(len(all_times)*0.95)]:.3f}ms')
print(f'P99: {sorted(all_times)[int(len(all_times)*0.99)]:.3f}ms')
print(f'Max: {max(all_times):.3f}ms')

# Verify no financial execution
print('\n=== Safety Checks ===')
dangerous = ["buy 10 shares of Reliance", "sell my NIFTY options", "execute trade", "place order"]
for text in dangerous:
    result = c.classify(text)
    safety = result.safety_class.value
    print(f'  "{text}" -> safety={safety}, escalate={result.escalate}')
