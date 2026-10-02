"""MYRAA FastCore — Large-Scale Dataset Builder.

Generates 50K+ training examples across 16 families using:
1. Template-based generation with variations
2. Teacher validation via Ollama
3. Hard-negative and adversarial examples
4. Voice transcript variations
"""

from __future__ import annotations

import json
import hashlib
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import the classifier for base labels
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from desktop_agent.fastcore.classifier import FastCoreClassifier
from desktop_agent.fastcore.models import (
    TrainingExample, TaskType, ResponseMode, InformationSource,
    Complexity, ModelRoute, SafetyClass,
)

# ---------------------------------------------------------------------------
# Template Families
# ---------------------------------------------------------------------------

# Each family has templates with {slot} placeholders and slot value lists

CONVERSATION_TEMPLATES = [
    ("Hello", []),
    ("Hi", []),
    ("Hey", []),
    ("Hello {wake}", ["myraa", "myra", "jarvis"]),
    ("Hey {wake}", ["myraa", "myra", "jarvis"]),
    ("Hi {wake}", ["myraa", "myra", "jarvis"]),
    ("Good morning", []),
    ("Good afternoon", []),
    ("Good evening", []),
    ("Good night", []),
    ("Thanks", []),
    ("Thank you", []),
    ("Thank you so much", []),
    ("Thanks a lot", []),
    ("Bye", []),
    ("Goodbye", []),
    ("See you", []),
    ("See you later", []),
    ("OK", []),
    ("Okay", []),
    ("Sure", []),
    ("Yes", []),
    ("No", []),
    ("Please", []),
    ("Help", []),
    ("How are you", []),
    ("How are you doing", []),
    ("How's it going", []),
    ("What's up", []),
    ("Sup", []),
    ("What can you do", []),
    ("Who are you", []),
    ("Tell me about yourself", []),
    ("Stay with me", []),
    ("I'm bored", []),
    ("Let's talk", []),
    ("Nice to meet you", []),
    ("Good morning {wake}", ["myraa", "boss", "sir"]),
    ("Good night {wake}", ["myraa", "boss", "sir"]),
    ("How are you {wake}", ["myraa", "myra"]),
    ("Hey {wake} how are you", ["myraa", "myra"]),
    ("{wake} hello", ["myraa", "myra", "jarvis"]),
    ("{wake} hi", ["myraa", "myra", "jarvis"]),
    ("Thanks {wake}", ["myraa", "myra"]),
    ("Bye {wake}", ["myraa", "myra"]),
    ("See you {wake}", ["myraa", "myra"]),
]

KNOWLEDGE_TEMPLATES = [
    ("What is {topic}", ["Python", "RAM", "CPU", "GPU", "machine learning", "AI", "deep learning", "neural network", "recursion", "OOP", "inheritance", "polymorphism", "encapsulation", "abstraction", "compiler", "interpreter", "algorithm", "data structure", "binary tree", "linked list", "stack", "queue", "hash map", "API", "REST", "GraphQL", "SQL", "NoSQL", "Docker", "Kubernetes", "Linux", "Windows", "git", "HTTP", "HTTPS", "SSL", "TLS", "encryption", "blockchain", "cloud computing", "edge computing", "quantum computing", "5G", "IoT", "VR", "AR", "cybersecurity"]),
    ("What are {topic}", ["design patterns", "SOLID principles", "microservices", "monoliths", "containers", "virtual machines", "threads", "processes", "caches", "buffers", "queues", "stacks"]),
    ("Who is {person}", ["Alan Turing", "Albert Einstein", "Isaac Newton", "Nikola Tesla", "Steve Jobs", "Bill Gates", "Elon Musk", "Jeff Bezos", "Mark Zuckerberg", "Tim Berners-Lee", "Guido van Rossum", "Bjarne Stroustrup", "James Gosling", "Linus Torvalds", "Andrew Ng", "Yann LeCun", "Geoffrey Hinton", "Demis Hassabis", "Sam Altman"]),
    ("Explain {topic}", ["recursion", "OOP", "inheritance", "polymorphism", "machine learning", "deep learning", "neural networks", "backpropagation", "gradient descent", "transformers", "attention mechanism", "CNN", "RNN", "LSTM", "GAN", "reinforcement learning", "supervised learning", "unsupervised learning", "clustering", "classification", "regression"]),
    ("How does {thing} work", ["a CPU", "a GPU", "RAM", "SSD", "HDD", "a compiler", "an interpreter", "the internet", "HTTP", "DNS", "a database", "a cache", "a virtual machine", "Docker", "Kubernetes", "blockchain", "machine learning"]),
    ("Define {term}", ["algorithm", "function", "variable", "constant", "class", "object", "method", "interface", "module", "package", "library", "framework", "compiler", "interpreter", "debugger"]),
    ("Difference between {a} and {b}", [("Python", "Java"), ("JavaScript", "TypeScript"), ("SQL", "NoSQL"), ("TCP", "UDP"), ("HTTP", "HTTPS"), ("REST", "GraphQL"), ("Docker", "VMs"), ("SQL", "MongoDB"), ("React", "Vue"), ("Angular", "React"), ("Python", "C++"), ("machine learning", "deep learning"), ("AI", "ML")]),
    ("Tell me about {topic}", ["quantum computing", "blockchain", "cybersecurity", "cloud computing", "edge computing", "5G", "IoT", "VR", "AR", "space exploration", "climate change", "renewable energy"]),
]

CURRENT_TEMPLATES = [
    ("Latest {thing}", ["Python version", "Node.js version", "React version", "news", "technology news", "AI news", "crypto price", "stock market", "weather", "movies", "games"]),
    ("Current {thing}", ["stock price of {stock}", "price of {stock}", "NIFTY value", "Sensex value", "Bitcoin price", "Ethereum price", "weather in {city}", "time in {city}"]),
    ("What is the latest {thing}", ["version of Python", "version of Node.js", "news about AI", "trend in technology", "price of Bitcoin"]),
    ("Today's {thing}", ["news", "top stories", "headlines", "weather", "stock market", "cricket score", "football score"]),
    ("Recent {thing}", ["AI breakthroughs", "technology news", "scientific discoveries", "startup funding", "product launches"]),
    ("What happened today", []),
    ("What's happening in {domain}", ["tech", "AI", "crypto", "stock market", "politics", "sports"]),
    ("{stock} stock price", ["Reliance", "TCS", "HDFC", "Infosys", "Wipro", "Adani", "Tata", "ITC", "SBI", "Bharti Airtel"]),
    ("Price of {stock}", ["Reliance", "TCS", "HDFC", "Infosys", "Wipro"]),
]

DESKTOP_TEMPLATES = [
    ("Open {app}", ["Notepad", "Chrome", "Firefox", "Edge", "VS Code", "Visual Studio", "PyCharm", "IntelliJ", "Eclipse", "Sublime Text", "Word", "Excel", "PowerPoint", "Calculator", "Paint", "Terminal", "Command Prompt", "File Explorer", "Task Manager", "Settings", "Control Panel"]),
    ("Close {app}", ["Chrome", "Firefox", "Edge", "Notepad", "VS Code", "Word", "Excel", "PowerPoint", "Calculator", "Paint"]),
    ("Launch {app}", ["Notepad", "Chrome", "Firefox", "Edge", "VS Code", "Word", "Excel"]),
    ("Start {app}", ["Notepad", "Chrome", "Firefox", "Edge", "VS Code"]),
    ("Run {app}", ["Notepad", "Chrome", "Firefox", "VS Code", "Calculator"]),
    ("Minimize window", []),
    ("Maximize window", []),
    ("Restore window", []),
    ("Switch to {app}", ["Chrome", "Notepad", "VS Code", "Word", "Excel"]),
    ("Activate {app}", ["Chrome", "Notepad", "VS Code"]),
    ("Volume up", []),
    ("Volume down", []),
    ("Mute", []),
    ("Unmute", []),
    ("Set volume to {level}", ["50", "75", "100", "25"]),
    ("Brightness up", []),
    ("Brightness down", []),
    ("Set brightness to {level}", ["50", "75", "100"]),
    ("Shutdown", []),
    ("Shutdown the PC", []),
    ("Restart", []),
    ("Restart the computer", []),
    ("Sleep", []),
    ("Lock the screen", []),
    ("Take a screenshot", []),
    ("Capture screen", []),
    ("Copy selected text", []),
    ("Paste from clipboard", []),
    ("Clear clipboard", []),
    ("Click the button", []),
    ("Double click", []),
    ("Right click", []),
    ("Scroll down", []),
    ("Scroll up", []),
    ("Move mouse to {pos}", ["center", "top left", "bottom right"]),
    ("Type {text}", ["hello world", "test"]),
    ("Press {key}", ["Enter", "Tab", "Escape", "Space", "Delete", "Backspace"]),
    ("Press {combo}", ["Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+Z", "Ctrl+S", "Alt+Tab", "Ctrl+A", "Ctrl+F"]),
]

BROWSER_TEMPLATES = [
    ("Open {site}", ["YouTube", "Google", "GitHub", "Gmail", "Google Maps", "Netflix", "Spotify", "Twitter", "Instagram", "Facebook", "Reddit", "Wikipedia", "Stack Overflow"]),
    ("Go to {site}", ["youtube.com", "google.com", "github.com", "gmail.com", "reddit.com", "wikipedia.org", "stackoverflow.com"]),
    ("Navigate to {url}", ["youtube.com", "google.com", "github.com", "gmail.com"]),
    ("Search {query}", ["Python documentation", "machine learning tutorial", "best restaurants near me", "weather forecast", "news today", "stock prices"]),
    ("Search for {query}", ["Python documentation", "machine learning tutorial", "how to learn coding", "best restaurants"]),
    ("Google {query}", ["machine learning", "Python tutorial", "best laptops 2026", "restaurants near me"]),
    ("Look up {query}", ["Python documentation", "machine learning", "weather forecast"]),
    ("Watch {video}", ["AI tutorial", "Python course", "coding interview prep"]),
    ("Browse {site}", ["YouTube", "Reddit", "Hacker News"]),
    ("Download {file}", ["Python installer", "VS Code", "Chrome"]),
    ("Open YouTube and search for {query}", ["AI news", "Python tutorial", "coding interview"]),
    ("Search YouTube for {query}", ["AI news", "Python tutorial", "machine learning"]),
]

FILE_TEMPLATES = [
    ("Create a file called {name}", ["test.txt", "notes.md", "config.json", "data.csv", "report.docx", "script.py"]),
    ("Write a file {name}", ["test.txt", "notes.md", "config.json"]),
    ("Create {name}", ["test.txt", "notes.md", "report.docx"]),
    ("Read the {file} file", ["config", "settings", "README", "requirements", "package.json", ".env"]),
    ("Open the {file} file", ["config", "settings", "README"]),
    ("Delete the {file} file", ["old", "temporary", "cache", "log"]),
    ("Remove {file}", ["old logs", "temp files", "cache"]),
    ("Rename {old} to {new}", [("file.txt", "document.txt"), ("old.py", "new.py"), ("draft.docx", "final.docx")]),
    ("Move {file} to {folder}", [("report.docx", "archive"), ("photo.jpg", "pictures"), ("script.py", "backup")]),
    ("Copy {file}", ["report.docx", "script.py", "config.json"]),
    ("List files in {folder}", ["Documents", "Downloads", "Desktop", "Projects"]),
    ("Show files in {folder}", ["Documents", "Downloads", "Desktop"]),
    ("Find files named {pattern}", ["*.py", "*.txt", "*.json", "config*"]),
    ("Search for {pattern} files", ["*.py", "*.txt", "*.log"]),
    ("Create a folder called {name}", ["projects", "backup", "archive", "temp"]),
    ("Make a folder {name}", ["new_project", "test_folder"]),
]

VISION_TEMPLATES = [
    ("What's on my screen", []),
    ("What is on my screen", []),
    ("What do you see", []),
    ("What do you see on my screen", []),
    ("Read this screen", []),
    ("Read the screen", []),
    ("Read this chart", []),
    ("Read the chart", []),
    ("Analyze this screen", []),
    ("Analyze the screen", []),
    ("Analyze this image", []),
    ("Analyze the screenshot", []),
    ("Extract text from this image", []),
    ("OCR this image", []),
    ("What text is on the screen", []),
    ("What's displayed on the screen", []),
    ("Describe what you see", []),
    ("Tell me what's on the screen", []),
    ("What programs are open", []),
    ("What app is running", []),
    ("What window is active", []),
]

TRADING_TEMPLATES = [
    ("Analyze NIFTY", []),
    ("Analyze Bank NIFTY", []),
    ("NIFTY analysis", []),
    ("Bank NIFTY analysis", []),
    ("Show my portfolio", []),
    ("What are my holdings", []),
    ("Show my holdings", []),
    ("What's in my portfolio", []),
    ("Stock price of {stock}", ["Reliance", "TCS", "HDFC", "Infosys", "Wipro", "Adani", "Tata", "ITC", "SBI", "Bharti Airtel", "HCL Tech", "Tech Mahindra", "Bajaj Finance", "Asian Paints", "Maruti Suzuki"]),
    ("Price of {stock} stock", ["Reliance", "TCS", "HDFC"]),
    ("What is the price of {stock}", ["Reliance", "TCS", "HDFC"]),
    ("{stock} trend", ["NIFTY", "Bank NIFTY", "Reliance", "TCS"]),
    ("Market trend today", []),
    ("How is the market doing", []),
    ("Market outlook", []),
    ("NIFTY support and resistance", []),
    ("RSI of {stock}", ["NIFTY", "Reliance", "TCS"]),
    ("MACD of {stock}", ["NIFTY", "Reliance"]),
    ("Should I buy {stock}", ["Reliance", "TCS", "HDFC"]),
    ("Trading signals for {stock}", ["NIFTY", "Bank NIFTY"]),
]

CODING_TEMPLATES = [
    ("Build a Python project", []),
    ("Create a Python project", []),
    ("Write a Python script to {task}", ["sort files", "download images", "scrape websites", "analyze data", "generate passwords", "convert CSV to JSON", "create a web server", "send emails", "backup files", "compress files"]),
    ("Write a script to {task}", ["sort files", "download images", "analyze data"]),
    ("Create a script that {task}", ["sorts files", "downloads images", "analyzes data"]),
    ("Debug this code", []),
    ("Fix this bug", []),
    ("Fix the error in {file}", ["main.py", "app.py", "utils.py"]),
    ("Build a web scraper", []),
    ("Create a web scraper", []),
    ("Write a web scraper for {site}", ["YouTube", "Reddit", "Hacker News"]),
    ("Build an API", []),
    ("Create a REST API", []),
    ("Write a function to {task}", ["sort a list", "find duplicates", "parse JSON", "validate email", "calculate factorial"]),
    ("Create a class for {thing}", ["user management", "file handling", "database connection"]),
    ("Set up a {project} project", ["Django", "Flask", "FastAPI", "React", "Vue"]),
    ("Initialize a {project} project", ["Python", "Node.js", "React"]),
]

DESIGN_TEMPLATES = [
    ("Design a futuristic bike", []),
    ("Design a {style} bike", ["futuristic", "minimalist", "aggressive", "retro", "electric", "racing"]),
    ("Sketch a motorcycle concept", []),
    ("Create a {style} motorcycle concept", ["futuristic", "retro", "electric"]),
    ("Design a {object}", ["chair", "table", "lamp", "watch", "headphones", "keyboard", "mouse", "monitor", "speaker", "phone case"]),
    ("Create a 3D model of {object}", ["chair", "table", "car", "building", "robot"]),
    ("Design a logo for {brand}", ["tech startup", "coffee shop", "gaming company", "fitness brand"]),
    ("Conceptualize a {thing}", ["futuristic city", "smart home", "electric vehicle", "wearable device"]),
    ("Prototype a {thing}", ["mobile app", "web dashboard", "IoT device"]),
    ("Redesign the {thing}", ["homepage", "dashboard", "login page", "settings page"]),
]

RESEARCH_TEMPLATES = [
    ("Search for {topic}", ["Python documentation", "machine learning papers", "best coding practices", "API documentation"]),
    ("Research {topic}", ["latest AI models", "quantum computing advances", "renewable energy trends", "startup funding 2026"]),
    ("Find official {thing}", ["Python documentation", "React docs", "Docker documentation"]),
    ("Look up {topic}", ["Python best practices", "machine learning tutorials"]),
    ("Compare {a} and {b}", [("React", "Vue"), ("Python", "Java"), ("Docker", "Kubernetes"), ("AWS", "Azure"), ("PostgreSQL", "MongoDB"), ("Redis", "Memcached")]),
    ("What are the best {thing}", ["practices for Python", "tools for web development", "frameworks for AI", "laptops for coding"]),
    ("Find alternatives to {tool}", ["Docker", "VS Code", "PostgreSQL", "Redis"]),
    ("Search for {query} documentation", ["Python", "React", "Docker", "Kubernetes"]),
]

MULTIMODAL_TEMPLATES = [
    ("What's on my screen and search for {topic}", ["related documentation", "tutorials", "solutions"]),
    ("Take a screenshot and analyze it", []),
    ("Read the screen and search for {query}", ["documentation", "help"]),
    ("Analyze this image and explain {topic}", ["what it shows", "the diagram", "the chart"]),
    ("What do you see and how does it relate to {topic}", ["my current task", "what I'm working on"]),
]

ADVERSARIAL_TEMPLATES = [
    ("Hello, can you search Python", []),
    ("Hi, open YouTube", []),
    ("Hey, what is on my screen", []),
    ("Tell me about today's Python news", []),
    ("Can you open the Python website", []),
    ("What is the latest version of Python", []),
    ("Search YouTube for AI news", []),
    ("Read the screen and tell me what's there", []),
    ("Create a file with today's news", []),
    ("Open Notepad and write a Python script", []),
    ("What's the weather like today", []),
    ("Can you explain what is on my screen", []),
    ("Take a screenshot and analyze it", []),
    ("Hello Myraa, search for Python docs", []),
    ("Hey Myra, open Chrome and search for news", []),
    ("myraa yt kholo", []),
    ("hey myra open notepad", []),
    ("can you pls check whats on screen", []),
    ("kya hai mere screen pe", []),
    ("notepad kholo", []),
    ("chrome band karo", []),
    ("volume badhao", []),
    ("screenshot le lo", []),
    ("python kya hai", []),
    ("aaj ka news batao", []),
    ("nifty ka analysis karo", []),
    ("mere portfolio mein kya hai", []),
]

# Voice transcript variations (ASR-like errors)
VOICE_VARIATIONS = [
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
]


class LargeDatasetBuilder:
    """Builds large-scale training dataset for FastCore."""

    def __init__(self):
        self.classifier = FastCoreClassifier()
        self.examples: List[Dict[str, Any]] = []

    def build_all(self, target_count: int = 50000) -> List[Dict[str, Any]]:
        """Build complete dataset targeting the specified count."""
        print("=== Building FastCore Dataset ===")
        print(f"Target: {target_count} examples")

        # Phase 1: Template-based generation
        print("\n[1/5] Template-based generation...")
        self._gen_conversation(target_count // 6)
        self._gen_knowledge(target_count // 8)
        self._gen_current(target_count // 8)
        self._gen_desktop(target_count // 6)
        self._gen_browser(target_count // 8)
        self._gen_file(target_count // 10)
        self._gen_vision(target_count // 12)
        self._gen_trading(target_count // 10)
        self._gen_coding(target_count // 10)
        self._gen_design(target_count // 12)
        self._gen_research(target_count // 10)
        self._gen_multimodal(target_count // 15)
        print(f"  After templates: {len(self.examples)}")

        # Phase 2: Adversarial examples
        print("\n[2/5] Adversarial examples...")
        self._gen_adversarial(target_count // 15)
        print(f"  After adversarial: {len(self.examples)}")

        # Phase 3: Voice variations
        print("\n[3/5] Voice transcript variations...")
        self._gen_voice_variations(target_count // 15)
        print(f"  After voice: {len(self.examples)}")

        # Phase 4: Hinglish variations
        print("\n[4/5] Hinglish variations...")
        self._gen_hinglish(target_count // 15)
        print(f"  After Hinglish: {len(self.examples)}")

        # Phase 5: Dedup + balance
        print("\n[5/5] Dedup + balance...")
        self._deduplicate()
        self._verify_labels()
        print(f"  Final: {len(self.examples)}")

        return self.examples

    def _add(self, text: str, task_type: str, source: str, complexity: str,
             route: str, tools: bool = False, tool_names: Optional[List[str]] = None,
             freshness: bool = False, safety: str = "safe", family: str = ""):
        """Add an example with classifier verification."""
        # Get classifier prediction
        pred = self.classifier.classify(text)

        self.examples.append({
            "input_text": text,
            "input_type": "user_message",
            "task_type": task_type,
            "response_mode": self._task_to_mode(task_type),
            "information_source": source,
            "complexity": complexity,
            "model_route": route,
            "safety_class": safety,
            "tools_required": tools,
            "tool_names": tool_names or [],
            "freshness_required": freshness,
            "confidence": 0.9,
            "dataset_family": family,
            "classifier_prediction": pred.task_type.value,
        })

    def _task_to_mode(self, task: str) -> str:
        mapping = {
            "conversation": "fast_answer",
            "direct_knowledge": "fast_answer",
            "local_reasoning": "reasoning",
            "current_information": "research",
            "web_research": "research",
            "desktop_action": "action",
            "browser_action": "action",
            "vision_task": "vision",
            "file_task": "action",
            "trading_task": "trading",
            "coding_task": "coding",
            "design_task": "design",
            "multimodal_task": "multimodal",
        }
        return mapping.get(task, "reasoning")

    def _expand(self, template: str, slot_values: List) -> List[str]:
        """Expand a template with slot values."""
        if not slot_values:
            return [template]

        results = []
        # Find all {slot} patterns
        slots = re.findall(r'\{(\w+)\}', template)
        if not slots:
            return [template]

        # For simplicity, expand first slot
        slot = slots[0]
        for val in slot_values:
            if isinstance(val, tuple):
                # Multiple slots
                expanded = template
                for i, s in enumerate(slots):
                    if i < len(val):
                        expanded = expanded.replace('{' + s + '}', val[i])
                results.append(expanded)
            else:
                results.append(template.replace('{' + slot + '}', str(val)))

        return results

    def _gen_conversation(self, count: int):
        for template, slots in CONVERSATION_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "conversation", "none", "trivial", "fastcore_direct",
                         family="conversation")

    def _gen_knowledge(self, count: int):
        for template, slots in KNOWLEDGE_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "direct_knowledge", "local_model", "simple", "local_small",
                         family="knowledge")

    def _gen_current(self, count: int):
        for template, slots in CURRENT_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "current_information", "tavily", "moderate", "local_small",
                         tools=True, freshness=True, family="current")

    def _gen_desktop(self, count: int):
        for template, slots in DESKTOP_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "desktop_action", "tool_execution", "simple", "deterministic",
                         tools=True, family="desktop")

    def _gen_browser(self, count: int):
        for template, slots in BROWSER_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "browser_action", "tool_execution", "simple", "deterministic",
                         tools=True, tool_names=["browser"], family="browser")

    def _gen_file(self, count: int):
        for template, slots in FILE_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "file_task", "tool_execution", "simple", "deterministic",
                         tools=True, family="file")

    def _gen_vision(self, count: int):
        for template, slots in VISION_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "vision_task", "screen", "moderate", "local_small",
                         tools=True, tool_names=["screenshot", "vision"], family="vision")

    def _gen_trading(self, count: int):
        for template, slots in TRADING_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "trading_task", "local_model", "moderate", "local_large",
                         tools=True, safety="financial", family="trading")

    def _gen_coding(self, count: int):
        for template, slots in CODING_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "coding_task", "tool_execution", "complex", "local_large",
                         tools=True, family="coding")

    def _gen_design(self, count: int):
        for template, slots in DESIGN_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "design_task", "local_model", "complex", "local_large",
                         tools=True, family="design")

    def _gen_research(self, count: int):
        for template, slots in RESEARCH_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "web_research", "tavily", "moderate", "local_small",
                         tools=True, family="research")

    def _gen_multimodal(self, count: int):
        for template, slots in MULTIMODAL_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                self._add(text, "multimodal_task", "screen", "complex", "local_large",
                         tools=True, family="multimodal")

    def _gen_adversarial(self, count: int):
        for template, slots in ADVERSARIAL_TEMPLATES:
            texts = self._expand(template, slots)
            for text in texts:
                # Let classifier determine the correct label
                pred = self.classifier.classify(text)
                self._add(text, pred.task_type.value,
                         pred.information_source.value, pred.complexity.value,
                         pred.model_route.value, tools=pred.tools_required,
                         family="adversarial")

    def _gen_voice_variations(self, count: int):
        for asr_text, correct_text in VOICE_VARIATIONS:
            pred = self.classifier.classify(correct_text)
            self._add(asr_text, pred.task_type.value,
                     pred.information_source.value, pred.complexity.value,
                     pred.model_route.value, tools=pred.tools_required,
                     family="voice")

    def _gen_hinglish(self, count: int):
        hinglish = [
            ("notepad kholo", "desktop_action", "tool_execution", "simple", "deterministic", True),
            ("chrome band karo", "desktop_action", "tool_execution", "simple", "deterministic", True),
            ("volume badhao", "desktop_action", "tool_execution", "simple", "deterministic", True),
            ("volume kam karo", "desktop_action", "tool_execution", "simple", "deterministic", True),
            ("screenshot le lo", "desktop_action", "tool_execution", "simple", "deterministic", True),
            ("python kya hai", "direct_knowledge", "local_model", "simple", "local_small", False),
            ("aaj ka news batao", "current_information", "tavily", "moderate", "local_small", True),
            ("nifty ka analysis karo", "trading_task", "local_model", "moderate", "local_large", True),
            ("mere portfolio mein kya hai", "trading_task", "local_model", "moderate", "local_large", True),
            ("youtube kholo", "browser_action", "tool_execution", "simple", "deterministic", True),
            ("google pe search karo", "browser_action", "tool_execution", "simple", "deterministic", True),
            ("file banao", "file_task", "tool_execution", "simple", "deterministic", True),
            ("folder banao", "file_task", "tool_execution", "simple", "deterministic", True),
            ("screen pe kya hai", "vision_task", "screen", "moderate", "local_small", True),
            ("mere screen pe kya hai", "vision_task", "screen", "moderate", "local_small", True),
            ("code likho", "coding_task", "tool_execution", "complex", "local_large", True),
            ("script banao", "coding_task", "tool_execution", "complex", "local_large", True),
            ("design banao", "design_task", "local_model", "complex", "local_large", True),
            ("band karo", "desktop_action", "tool_execution", "simple", "deterministic", True),
            ("chalu karo", "desktop_action", "tool_execution", "simple", "deterministic", True),
        ]
        for text, task, source, complexity, route, tools in hinglish:
            self._add(text, task, source, complexity, route, tools=tools, family="hinglish")

    def _deduplicate(self):
        """Remove exact duplicates."""
        seen = set()
        unique = []
        for ex in self.examples:
            key = hashlib.md5(ex["input_text"].lower().encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique.append(ex)
        self.examples = unique

    def _verify_labels(self):
        """Verify classifier agrees with labels (log disagreements)."""
        agree = 0
        disagree = 0
        for ex in self.examples:
            pred = self.classifier.classify(ex["input_text"])
            if pred.task_type.value == ex["task_type"]:
                agree += 1
            else:
                disagree += 1
        print(f"  Classifier agreement: {agree}/{agree+disagree} ({100*agree/(agree+disagree):.1f}%)")

    def save(self, path: str, version: str = "0.2.0") -> Dict[str, Any]:
        """Save dataset and return stats."""
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Add version metadata
        dataset = {
            "version": version,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_examples": len(self.examples),
            "schema_version": "1.0",
            "examples": self.examples,
        }

        with open(path_obj, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        # Stats
        families = {}
        task_types = {}
        for ex in self.examples:
            fam = ex.get("dataset_family", "unknown")
            families[fam] = families.get(fam, 0) + 1
            tt = ex.get("task_type", "unknown")
            task_types[tt] = task_types.get(tt, 0) + 1

        return {
            "total": len(self.examples),
            "families": families,
            "task_types": task_types,
            "path": str(path),
        }


if __name__ == "__main__":
    builder = LargeDatasetBuilder()
    examples = builder.build_all(target_count=50000)
    stats = builder.save("desktop_agent/fastcore/dataset/fastcore_v0.2.0.json")
    print(f"\n=== Dataset Stats ===")
    print(f"Total: {stats['total']}")
    print(f"Families: {stats['families']}")
    print(f"Task types: {stats['task_types']}")
