"""FastCore dataset expansion — generates additional examples via random variations."""
import json, random, re, hashlib, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from desktop_agent.fastcore.classifier import FastCoreClassifier
from desktop_agent.fastcore.large_dataset_builder import LargeDatasetBuilder

# Additional slot values for expansion
TOPICS = ["Python", "Java", "JavaScript", "TypeScript", "C++", "Rust", "Go", "Ruby", "PHP", "Swift", "Kotlin",
          "machine learning", "deep learning", "AI", "neural networks", "NLP", "computer vision",
          "recursion", "OOP", "inheritance", "polymorphism", "encapsulation",
          "data structures", "algorithms", "databases", "cloud computing", "DevOps",
          "blockchain", "cybersecurity", "quantum computing", "5G", "IoT"]

APPS = ["Notepad", "Chrome", "Firefox", "Edge", "VS Code", "Visual Studio", "PyCharm",
        "IntelliJ", "Eclipse", "Sublime Text", "Word", "Excel", "PowerPoint",
        "Calculator", "Paint", "Terminal", "Command Prompt", "File Explorer",
        "Task Manager", "Settings", "Photoshop", "Illustrator", "Figma",
        "Slack", "Discord", "Zoom", "Teams", "Spotify", "VLC"]

SITES = ["YouTube", "Google", "GitHub", "Gmail", "Google Maps", "Netflix", "Spotify",
         "Twitter", "Instagram", "Facebook", "Reddit", "Wikipedia", "Stack Overflow",
         "LinkedIn", "Medium", "Dev.to", "Hacker News", "Product Hunt"]

STOCKS = ["Reliance", "TCS", "HDFC", "Infosys", "Wipro", "Adani", "Tata", "ITC",
          "SBI", "Bharti Airtel", "HCL Tech", "Tech Mahindra", "Bajaj Finance",
          "Asian Paints", "Maruti Suzuki", "Sun Pharma", "Dr Reddy", "Cipla"]

CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Hyderabad",
          "Pune", "Ahmedabad", "Jaipur", "Lucknow", "New York", "London",
          "Tokyo", "Singapore", "Dubai", "San Francisco"]

PERSONS = ["Alan Turing", "Albert Einstein", "Isaac Newton", "Nikola Tesla",
           "Steve Jobs", "Bill Gates", "Elon Musk", "Jeff Bezos",
           "Mark Zuckerberg", "Tim Berners-Lee", "Guido van Rossum",
           "Linus Torvalds", "Andrew Ng", "Yann LeCun", "Sam Altman"]

RANDOM_TEXTS = [
    "the quick brown fox jumps over the lazy dog",
    "hello world this is a test",
    "please help me with this task",
    "can you do this for me",
    "I need assistance with something",
    "this is important please help",
    "quick question about coding",
    "how do I fix this error",
    "what's the best approach here",
    "I'm stuck on this problem",
]

ASR_ERRORS = [
    ("open you tube", "Open YouTube"),
    ("what is on my screan", "What is on my screen"),
    ("myraa open not pad", "Myraa open Notepad"),
    ("close chrom", "Close Chrome"),
    ("volme up", "Volume up"),
    ("shutdonw", "Shutdown"),
    ("screen shot", "Screenshot"),
    ("pythn", "Python"),
    ("machne learning", "Machine learning"),
    ("nvidya", "NVIDIA"),
    ("my nfty", "My NIFTY"),
    ("recusrion", "Recursion"),
    ("polymrphism", "Polymorphism"),
    ("algoritm", "Algorithm"),
    ("databse", "Database"),
    ("frambwork", "Framework"),
    ("funtion", "Function"),
    ("varialbe", "Variable"),
    ("contianer", "Container"),
    ("kuberntes", "Kubernetes"),
]

HINGLISH_PHRASES = [
    ("notepad kholo", "desktop_action"),
    ("chrome band karo", "desktop_action"),
    ("volume badhao", "desktop_action"),
    ("volume kam karo", "desktop_action"),
    ("screenshot le lo", "desktop_action"),
    ("python kya hai", "direct_knowledge"),
    ("aaj ka news batao", "current_information"),
    ("nifty ka analysis karo", "trading_task"),
    ("mere portfolio mein kya hai", "trading_task"),
    ("youtube kholo", "browser_action"),
    ("google pe search karo", "browser_action"),
    ("file banao", "file_task"),
    ("folder banao", "file_task"),
    ("screen pe kya hai", "vision_task"),
    ("mere screen pe kya hai", "vision_task"),
    ("code likho", "coding_task"),
    ("script banao", "coding_task"),
    ("design banao", "design_task"),
    ("band karo", "desktop_action"),
    ("chalu karo", "desktop_action"),
    ("kya kar rahe ho", "conversation"),
    ("kaisa hai tu", "conversation"),
    ("namaste", "conversation"),
    ("shukriya", "conversation"),
    ("alvida", "conversation"),
    ("mere laptop mein kya hai", "vision_task"),
    ("screen check karo", "vision_task"),
    ("market kaisa hai", "trading_task"),
    ("stock price batao", "trading_task"),
    ("research karo ispe", "web_research"),
    ("search karo iske baare mein", "web_research"),
    ("file padho", "file_task"),
    ("folder kholo", "file_task"),
    ("app band karo", "desktop_action"),
    ("application kholo", "desktop_action"),
    ("brightness kam karo", "desktop_action"),
    ("brightness badhao", "desktop_action"),
    ("mute karo", "desktop_action"),
    ("unmute karo", "desktop_action"),
]

EXTRA_TEMPLATES = [
    ("Can you {action} {target}", [("open", "Notepad"), ("close", "Chrome"), ("search", "Python docs"), ("read", "the screen"), ("analyze", "NIFTY"), ("explain", "recursion"), ("create", "a file"), ("delete", "the old file")]),
    ("Please {action} {target}", [("open", "YouTube"), ("close", "Firefox"), ("search", "machine learning"), ("explain", "OOP"), ("create", "a script")]),
    ("I want to {action} {target}", [("open", "VS Code"), ("search", "Python documentation"), ("read", "the config file"), ("analyze", "the market"), ("learn", "Python")]),
    ("Help me {action} {target}", [("open", "Chrome"), ("fix", "this code"), ("create", "a project"), ("understand", "recursion"), ("find", "the error")]),
    ("Could you {action} {target}", [("open", "Notepad"), ("search", "for documentation"), ("explain", "how this works"), ("create", "a file")]),
    ("Would you {action} {target}", [("open", "YouTube"), ("search", "for tutorials"), ("explain", "the concept"), ("create", "a script")]),
    ("I need to {action} {target}", [("open", "Terminal"), ("create", "a file"), ("search", "for information"), ("fix", "the bug"), ("analyze", "the data")]),
    ("Can you tell me about {topic}", TOPICS),
    ("What do you know about {topic}", TOPICS),
    ("How do I {action} {target}", [("use", "Python"), ("install", "Docker"), ("run", "the script"), ("fix", "the error"), ("create", "a project")]),
    ("What is the best way to {action} {target}", [("learn", "Python"), ("study", "machine learning"), ("practice", "coding"), ("build", "a website")]),
]


def build_extra():
    """Build additional examples."""
    classifier = FastCoreClassifier()
    examples = []

    # Extra templates
    for template, slots in EXTRA_TEMPLATES:
        for slot_vals in slots:
            if isinstance(slot_vals, tuple):
                text = template
                for i, slot in enumerate(re.findall(r'\{(\w+)\}', template)):
                    if i < len(slot_vals):
                        text = text.replace('{' + slot + '}', slot_vals[i])
            else:
                text = template.replace('{target}', str(slot_vals)).replace('{topic}', str(slot_vals)).replace('{action}', 'do')
            pred = classifier.classify(text)
            examples.append({
                "input_text": text,
                "input_type": "user_message",
                "task_type": pred.task_type.value,
                "response_mode": {"conversation": "fast_answer", "direct_knowledge": "fast_answer", "local_reasoning": "reasoning", "current_information": "research", "web_research": "research", "desktop_action": "action", "browser_action": "action", "vision_task": "vision", "file_task": "action", "trading_task": "trading", "coding_task": "coding", "design_task": "design", "multimodal_task": "multimodal"}.get(pred.task_type.value, "reasoning"),
                "information_source": pred.information_source.value,
                "complexity": pred.complexity.value,
                "model_route": pred.model_route.value,
                "safety_class": pred.safety_class.value,
                "tools_required": pred.tools_required,
                "tool_names": pred.tool_names,
                "freshness_required": pred.freshness_required,
                "confidence": 0.9,
                "dataset_family": "extra",
            })

    # Random text variations
    for _ in range(500):
        text = random.choice(RANDOM_TEXTS) + " " + random.choice(TOPICS).lower()
        pred = classifier.classify(text)
        examples.append({
            "input_text": text,
            "input_type": "user_message",
            "task_type": pred.task_type.value,
            "response_mode": "reasoning",
            "information_source": pred.information_source.value,
            "complexity": pred.complexity.value,
            "model_route": pred.model_route.value,
            "safety_class": pred.safety_class.value,
            "tools_required": pred.tools_required,
            "tool_names": pred.tool_names,
            "freshness_required": pred.freshness_required,
            "confidence": 0.85,
            "dataset_family": "random",
        })

    # ASR errors
    for asr, correct in ASR_ERRORS:
        pred = classifier.classify(correct)
        examples.append({
            "input_text": asr,
            "input_type": "voice_transcript",
            "task_type": pred.task_type.value,
            "response_mode": "reasoning",
            "information_source": pred.information_source.value,
            "complexity": pred.complexity.value,
            "model_route": pred.model_route.value,
            "safety_class": pred.safety_class.value,
            "tools_required": pred.tools_required,
            "tool_names": pred.tool_names,
            "freshness_required": pred.freshness_required,
            "confidence": 0.85,
            "dataset_family": "asr_error",
        })

    # Hinglish
    for text, expected_task in HINGLISH_PHRASES:
        examples.append({
            "input_text": text,
            "input_type": "user_message",
            "task_type": expected_task,
            "response_mode": {"conversation": "fast_answer", "direct_knowledge": "fast_answer", "current_information": "research", "desktop_action": "action", "browser_action": "action", "vision_task": "vision", "file_task": "action", "trading_task": "trading", "coding_task": "coding", "design_task": "design", "web_research": "research"}.get(expected_task, "reasoning"),
            "information_source": "tool_execution" if expected_task in ["desktop_action", "browser_action", "file_task"] else "local_model",
            "complexity": "simple" if expected_task in ["conversation", "desktop_action", "browser_action"] else "moderate",
            "model_route": "deterministic" if expected_task in ["desktop_action", "browser_action", "file_task"] else "local_small",
            "safety_class": "financial" if expected_task == "trading_task" else "safe",
            "tools_required": expected_task not in ["conversation", "direct_knowledge"],
            "tool_names": [],
            "freshness_required": expected_task == "current_information",
            "confidence": 0.9,
            "dataset_family": "hinglish",
        })

    return examples


if __name__ == "__main__":
    print("Building extra examples...")
    extra = build_extra()
    print(f"Extra examples: {len(extra)}")

    # Load existing dataset
    ds_path = Path("desktop_agent/fastcore/dataset/fastcore_v0.2.0.json")
    if ds_path.exists():
        with open(ds_path) as f:
            existing = json.load(f)
        all_examples = existing["examples"] + extra
    else:
        all_examples = extra

    # Dedup
    seen = set()
    unique = []
    for ex in all_examples:
        key = hashlib.md5(ex["input_text"].lower().encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            unique.append(ex)

    # Stats
    families = {}
    task_types = {}
    for ex in unique:
        fam = ex.get("dataset_family", "unknown")
        families[fam] = families.get(fam, 0) + 1
        tt = ex.get("task_type", "unknown")
        task_types[tt] = task_types.get(tt, 0) + 1

    # Save
    dataset = {
        "version": "0.2.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_examples": len(unique),
        "schema_version": "1.0",
        "examples": unique,
    }
    with open(ds_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"\nTotal: {len(unique)}")
    print(f"Families: {families}")
    print(f"Task types: {task_types}")
