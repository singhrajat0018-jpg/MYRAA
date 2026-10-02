#!/usr/bin/env python3
"""
Simple benchmark generator for AI Manager 3.0 validation.
Creates 500+ test requests with structured labels.
"""

import json
import random
from enum import Enum
from dataclasses import dataclass, asdict
from typing import List

class Intent(Enum):
    GREETING = "greeting"
    THANKS = "thanks"
    SIMPLE_QUESTION = "simple_question"
    EXPLANATION = "explanation"
    ANALYSIS = "analysis"
    COMPARISON = "comparison"
    RELATIONSHIP = "relationship"
    TRADING_ANALYSIS = "trading_analysis"
    TRADING_DECISION = "trading_decision"
    CODING_DEBUG = "coding_debug"
    CODING_BUILD = "coding_build"
    CREATION_DOCUMENT = "creation_document"
    RESEARCHING = "researching"
    INVESTIGATING = "investigating"
    SYSTEM_DIAGNOSTICS = "system_diagnostics"
    APP_CONTROL = "app_control"
    VISION_SCREEN = "vision_screen"
    PHONE_CONTROL = "phone_control"
    TIME_QUERY = "time_query"
    AUDIO_CONTROL = "audio_control"

class Domain(Enum):
    GENERAL = "general"
    CODING = "coding"
    RESEARCH = "research"
    TRADING = "trading"
    CREATIVE = "creative"
    SYSTEM = "system"
    DOCUMENT = "document"
    VISION = "vision"
    PHONE = "phone"

class ExecutionMode(Enum):
    FAST_DETERMINISTIC = "fast_deterministic"
    FAST_MODEL = "fast_model"
    STANDARD_REASONING = "standard_reasoning"
    DEEP_REASONING = "deep_reasoning"
    RESEARCH_PIPELINE = "research_pipeline"
    CREATION_ENGINE = "creation_engine"
    TRADING_ENGINE = "trading_engine"
    CODING_ENGINE = "coding_engine"
    SYSTEM_DIAGNOSTICS = "system_diagnostics"
    VISION = "vision"
    COMPUTER_USE = "computer_use"

class ReasoningDepth(Enum):
    MINIMAL = "minimal"
    BASIC = "basic"
    MODERATE = "moderate"
    DEEP = "deep"

class Freshness(Enum):
    STATIC = "static"
    RECENT = "recent"
    REAL_TIME = "real_time"
    LIVE = "live"

class RiskLevel(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FINANCIAL = "financial"

@dataclass
class BenchmarkItem:
    request: str
    intent: Intent
    topic: str
    entities: List[str]
    domain: Domain
    capability: str
    output_type: str
    execution_mode: ExecutionMode
    reasoning_depth: ReasoningDepth
    freshness: Freshness
    tools_required: List[str]
    risk_level: RiskLevel
    language: str
    complexity: str
    expected_response: str

def create_template_requests() -> List[BenchmarkItem]:
    """Create template requests that we can vary"""
    templates = [
        # Greetings
        ("hello", Intent.GREETING, "greeting", [], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.FAST_DETERMINISTIC, ReasoningDepth.MINIMAL, Freshness.STATIC, [], RiskLevel.NONE, "English", "simple", "Hello! How can I help you?"),
        ("hi there", Intent.GREETING, "greeting", [], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.FAST_DETERMINISTIC, ReasoningDepth.MINIMAL, Freshness.STATIC, [], RiskLevel.NONE, "English", "simple", "Hi! What can I do for you?"),
        ("thanks", Intent.THANKS, "thanks", [], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.FAST_DETERMINISTIC, ReasoningDepth.MINIMAL, Freshness.STATIC, [], RiskLevel.NONE, "English", "simple", "You're welcome!"),

        # Simple questions
        ("what is python", Intent.SIMPLE_QUESTION, "python definition", ["python"], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, [], RiskLevel.NONE, "English", "simple", "Python is a high-level programming language..."),
        ("who is einstein", Intent.SIMPLE_QUESTION, "einstein", ["einstein"], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, [], RiskLevel.NONE, "English", "simple", "Albert Einstein was a theoretical physicist..."),
        ("what time is it", Intent.TIME_QUERY, "current time", ["time"], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.FAST_DETERMINISTIC, ReasoningDepth.MINIMAL, Freshness.REAL_TIME, [], RiskLevel.NONE, "English", "simple", "The current time is..."),

        # Explanation
        ("explain how photosynthesis works", Intent.EXPLANATION, "photosynthesis", ["photosynthesis"], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.DEEP_REASONING, ReasoningDepth.MODERATE, Freshness.STATIC, [], RiskLevel.NONE, "English", "complex", "Photosynthesis is the process by which plants..."),
        ("explain the theory of relativity", Intent.EXPLANATION, "relativity", ["relativity"], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.DEEP_REASONING, ReasoningDepth.MODERATE, Freshness.STATIC, [], RiskLevel.NONE, "English", "complex", "The theory of relativity, developed by Albert Einstein..."),

        # Analysis
        ("analyze the pros and cons of renewable energy", Intent.ANALYSIS, "renewable energy", ["renewable", "energy"], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.DEEP_REASONING, ReasoningDepth.MODERATE, Freshness.RECENT, [], RiskLevel.NONE, "English", "complex", "Renewable energy has several advantages and disadvantages..."),
        ("compare machine learning algorithms", Intent.COMPARISON, "ml algorithms", ["machine learning", "algorithms"], Domain.GENERAL, "GLOBAL_INTELLIGENCE_ENGINE", "text", ExecutionMode.DEEP_REASONING, ReasoningDepth.MODERATE, Freshness.RECENT, [], RiskLevel.NONE, "English", "complex", "Different machine learning algorithms have different strengths..."),

        # Trading
        ("analyze nifty trend", Intent.TRADING_ANALYSIS, "nifty analysis", ["nifty"], Domain.TRADING, "TRADING_ENGINE", "analysis", ExecutionMode.TRADING_ENGINE, ReasoningDepth.DEEP, Freshness.REAL_TIME, ["market_data"], RiskLevel.FINANCIAL, "English", "complex", "Based on technical analysis, Nifty shows..."),
        ("should I buy reliance stock", Intent.TRADING_DECISION, "reliance investment", ["reliance", "stock"], Domain.TRADING, "TRADING_ENGINE", "recommendation", ExecutionMode.TRADING_ENGINE, ReasoningDepth.DEEP, Freshness.REAL_TIME, ["market_data", "news"], RiskLevel.FINANCIAL, "English", "complex", "Based on Reliance's fundamentals and market conditions..."),

        # Coding
        ("debug this python code", Intent.CODING_DEBUG, "python debugging", ["python"], Domain.CODING, "CODING_ENGINE", "text", ExecutionMode.STANDARD_REASONING, ReasoningDepth.BASIC, Freshness.STATIC, ["debugger"], RiskLevel.LOW, "English", "simple", "I can help you debug your Python code. Please share the snippet..."),
        ("create a website with html and css", Intent.CODING_BUILD, "website creation", ["html", "css", "website"], Domain.CODING, "CODING_ENGINE", "code", ExecutionMode.CODING_ENGINE, ReasoningDepth.MODERATE, Freshness.STATIC, ["code_execution"], RiskLevel.LOW, "English", "complex", "Here's a basic website structure using HTML and CSS..."),

        # Creation
        ("create a document for project proposal", Intent.CREATION_DOCUMENT, "project proposal", ["document", "proposal"], Domain.CREATIVE, "CREATION_ENGINE", "document", ExecutionMode.CREATION_ENGINE, ReasoningDepth.MODERATE, Freshness.STATIC, ["document_editor"], RiskLevel.LOW, "English", "simple", "I'll help you create a professional project proposal..."),
        ("make a presentation about ai", Intent.CREATION_DOCUMENT, "ai presentation", ["presentation", "ai"], Domain.CREATIVE, "CREATION_ENGINE", "presentation", ExecutionMode.CREATION_ENGINE, ReasoningDepth.MODERATE, Freshness.STATIC, ["presentation_tool"], RiskLevel.LOW, "English", "simple", "I'll create an engaging presentation about AI topics..."),

        # Research
        ("research latest developments in quantum computing", Intent.RESEARCHING, "quantum research", ["quantum computing"], Domain.RESEARCH, "RESEARCH_PIPELINE", "research_report", ExecutionMode.RESEARCH_PIPELINE, ReasoningDepth.DEEP, Freshness.REAL_TIME, ["web_research"], RiskLevel.LOW, "English", "complex", "Recent developments in quantum computing include..."),
        ("investigate blockchain technology trends", Intent.INVESTIGATING, "blockchain investigation", ["blockchain"], Domain.RESEARCH, "RESEARCH_PIPELINE", "investigation_report", ExecutionMode.RESEARCH_PIPELINE, ReasoningDepth.DEEP, Freshness.RECENT, ["web_research"], RiskLevel.LOW, "English", "complex", "Investigation into blockchain technology reveals..."),

        # System
        ("check system performance", Intent.SYSTEM_DIAGNOSTICS, "system check", ["system", "performance"], Domain.SYSTEM, "SYSTEM_DIAGNOSTICS", "diagnostic_report", ExecutionMode.SYSTEM_DIAGNOSTICS, ReasoningDepth.MODERATE, Freshness.RECENT, ["system_tools"], RiskLevel.LOW, "English", "simple", "System performance check shows CPU usage at..."),
        ("diagnose computer issues", Intent.SYSTEM_DIAGNOSTICS, "computer diagnosis", ["computer", "issues"], Domain.SYSTEM, "SYSTEM_DIAGNOSTICS", "diagnostic_report", ExecutionMode.SYSTEM_DIAGNOSTICS, ReasoningDepth.MODERATE, Freshness.RECENT, ["system_tools"], RiskLevel.LOW, "English", "simple", "Based on diagnostic tests, potential issues include..."),

        # App control
        ("open notepad", Intent.APP_CONTROL, "open notepad", ["notepad"], Domain.SYSTEM, "COMPUTER_USE", "action", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, [], RiskLevel.LOW, "English", "simple", "Opening Notepad..."),
        ("close chrome", Intent.APP_CONTROL, "close chrome", ["chrome"], Domain.SYSTEM, "COMPUTER_USE", "action", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, [], RiskLevel.LOW, "English", "simple", "Closing Chrome browser..."),
        ("volume 50", Intent.AUDIO_CONTROL, "set volume", ["volume"], Domain.SYSTEM, "COMPUTER_USE", "action", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, [], RiskLevel.LOW, "English", "simple", "Setting volume to 50%..."),

        # Vision
        ("take a screenshot", Intent.VISION_SCREEN, "screenshot", ["screenshot"], Domain.VISION, "VISION", "image", ExecutionMode.VISION, ReasoningDepth.BASIC, Freshness.LIVE, ["screen_capture"], RiskLevel.LOW, "English", "simple", "Capturing screenshot..."),
        ("show me what's on my screen", Intent.VISION_SCREEN, "screen analysis", ["screen"], Domain.VISION, "VISION", "analysis", ExecutionMode.VISION, ReasoningDepth.BASIC, Freshness.LIVE, ["screen_capture", "ocr"], RiskLevel.LOW, "English", "simple", "Analyzing current screen content..."),

        # Phone
        ("call mom", Intent.PHONE_CONTROL, "phone call", ["mom"], Domain.PHONE, "PHONE_ENGINE", "action", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, ["phone"], RiskLevel.LOW, "English", "simple", "Calling Mom..."),
        ("send message to john", Intent.PHONE_CONTROL, "send message", ["john"], Domain.PHONE, "PHONE_ENGINE", "action", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, ["phone"], RiskLevel.LOW, "English", "simple", "Sending message to John..."),

        # Hinglish variations
        ("youtube kholo", Intent.APP_CONTROL, "open youtube", ["youtube"], Domain.SYSTEM, "COMPUTER_USE", "action", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, [], RiskLevel.LOW, "Hinglish", "simple", "YouTube khol raha hoon..."),
        ("chrome kholo", Intent.APP_CONTROL, "open chrome", ["chrome"], Domain.SYSTEM, "COMPUTER_USE", "action", ExecutionMode.FAST_MODEL, ReasoningDepth.BASIC, Freshness.STATIC, [], RiskLevel.LOW, "Hinglish", "simple", "Chrome khol raha hoon..."),
        ("website banao", Intent.CREATION_DOCUMENT, "create website", ["website"], Domain.CREATIVE, "CREATION_ENGINE", "website", ExecutionMode.CREATION_ENGINE, ReasoningDepth.MODERATE, Freshness.STATIC, ["code_execution"], RiskLevel.LOW, "Hinglish", "simple", "Website banana mein madad karta hoon..."),
        ("ppt banao", Intent.CREATION_DOCUMENT, "create presentation", ["presentation"], Domain.CREATIVE, "CREATION_ENGINE", "presentation", ExecutionMode.CREATION_ENGINE, ReasoningDepth.MODERATE, Freshness.STATIC, ["presentation_tool"], RiskLevel.LOW, "Hinglish", "simple", "Presentation banana mein madad karta hoon..."),
        ("nifty analyze karo", Intent.TRADING_ANALYSIS, "analyze nifty", ["nifty"], Domain.TRADING, "TRADING_ENGINE", "analysis", ExecutionMode.TRADING_ENGINE, ReasoningDepth.DEEP, Freshness.REAL_TIME, ["market_data"], RiskLevel.FINANCIAL, "Hinglish", "simple", "Nifty ka technical analysis karte hue..."),
        ("report tayyar karo", Intent.CREATION_DOCUMENT, "prepare report", ["report"], Domain.CREATIVE, "CREATION_ENGINE", "report", ExecutionMode.CREATION_ENGINE, ReasoningDepth.MODERATE, Freshness.STATIC, ["document_editor"], RiskLevel.LOW, "Hinglish", "simple", "Report tayyar karne ke liye, konsa topic hai?")
    ]

    items = []
    for template in templates:
        req, intent, topic, entities, domain, capability, output_type, exec_mode, reasoning, freshness, tools, risk, lang, complexity, expected = template
        items.append(BenchmarkItem(
            request=req,
            intent=intent,
            topic=topic,
            entities=entities,
            domain=domain,
            capability=capability,
            output_type=output_type,
            execution_mode=exec_mode,
            reasoning_depth=reasoning,
            freshness=freshness,
            tools_required=tools,
            risk_level=risk,
            language=lang,
            complexity=complexity,
            expected_response=expected
        ))

    return items

def generate_variations(base_items: List[BenchmarkItem], target_count: int) -> List[BenchmarkItem]:
    """Generate variations to reach target count"""
    items = base_items.copy()

    # Variations to apply
    variations = [
        # Add please/courtesy words
        lambda s: s.replace("open", "please open") if "open" in s else s,
        lambda s: s.replace("create", "kindly create") if "create" in s else s,
        lambda s: s.replace("analyze", "please analyze") if "analyze" in s else s,
        # Add urgency
        lambda s: s.replace("what is", "tell me what is") if "what is" in s else s,
        lambda s: s.replace("explain", "could you explain") if "explain" in s else s,
        # Change numbers
        lambda s: s.replace("volume 50", "volume 70") if "volume 50" in s else s,
        lambda s: s.replace("brightness 80", "brightness 60") if "brightness 80" in s else s,
        # Add context
        lambda s: s + " for my project" if len(s) < 20 and "create" in s else s,
        lambda s: s + " today" if len(s) < 25 and ("analyze" in s or "check" in s) else s,
        # Make negative
        lambda s: s.replace("open", "do not open") if "open" in s and random.random() > 0.7 else s,
        # Make complex
        lambda s: s.replace("what is", "explain in detail what is and how it works") if "what is" in s and random.random() > 0.8 else s,
    ]

    while len(items) < target_count:
        base = random.choice(base_items)
        # Create a variation
        new_request = base.request
        new_expected = base.expected_response

        # Apply 1-3 random variations
        num_variations = random.randint(1, 3)
        for _ in range(num_variations):
            var_func = random.choice(variations)
            new_request = var_func(new_request)
            # Adjust expected response slightly
            if "please" in new_request or "kindly" in new_request:
                if new_expected.startswith("Opening") or new_expected.startswith("Closing"):
                    new_expected = "Sure! " + new_expected.lower()
                elif new_expected.startswith("I'll"):
                    new_expected = "Certainly! " + new_expected
            elif "do not" in new_request:
                new_expected = "I cannot help with that request as it would require closing/open applications."
            elif "for my project" in new_request:
                new_expected = new_expected + " I'll tailor it to your project needs."
            elif "today" in new_request:
                new_expected = new_expected + " Here's the information for today."
            elif "explain in detail" in new_request:
                new_expected = new_expected + " Let me provide a detailed explanation."
            elif "what is" in new_request and "explain in detail what is" in new_request:
                new_except = new_expected + " Additionally, I'll explain how it works and its applications."

        # Sometimes change language to Hinglish
        if random.random() > 0.7 and base.language == "English":
            # Simple Hinglish conversion
            if "open" in new_request.lower():
                new_request = new_request.replace("open", "kholo")
                new_expected = new_expected.replace("Opening", "Khol raha hoon").replace("opening", "khol raha hoon")
            elif "create" in new_request.lower():
                new_request = new_request.replace("create", "banao")
                new_expected = new_expected.replace("I'll help you create", "Madad karta hoon banana").replace("I'll create", "Banata hoon")
            elif "analyze" in new_request.lower():
                new_request = new_request.replace("analyze", "karo")
                new_expected = new_expected.replace("Based on analysis", "Analysis karte hue").replace("Analyzing", "Analyze karte hue")
            elif "check" in new_request.lower():
                new_request = new_request.replace("check", "karlo")
                new_expected = new_expected.replace("check", "check karo")

        # Create new item with variation
        varied_item = BenchmarkItem(
            request=new_request.strip(),
            intent=base.intent,
            topic=base.topic,
            entities=base.entities,
            domain=base.domain,
            capability=base.capability,
            output_type=base.output_type,
            execution_mode=base.execution_mode,
            reasoning_depth=base.reasoning_depth,
            freshness=base.freshness,
            tools_required=base.tools_required,
            risk_level=base.risk_level,
            language="Hinglish" if ("kholo" in new_request or "banao" in new_request or "karo" in new_request) else base.language,
            complexity=base.complexity if len(new_request) < 30 else "complex",
            expected_response=new_expected
        )
        items.append(varied_item)

    return items[:target_count]

def save_benchmark(items: List[BenchmarkItem], filename: str):
    """Save benchmark to JSON file"""
    serializable = []
    for item in items:
        item_dict = asdict(item)
        # Convert enums to strings
        item_dict['intent'] = item.intent.value
        item_dict['domain'] = item.domain.value
        item_dict['execution_mode'] = item.execution_mode.value
        item_dict['reasoning_depth'] = item.reasoning_depth.value
        item_dict['freshness'] = item.freshness.value
        item_dict['risk_level'] = item.risk_level.value
        serializable.append(item_dict)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

def main():
    print("Creating benchmark...")
    base_items = create_template_requests()
    print(f"Created {len(base_items)} base items")

    # Generate 500+ items
    target_count = 520
    all_items = generate_variations(base_items, target_count)
    print(f"Generated {len(all_items)} total items")

    # Split into development, validation, held-out
    random.shuffle(all_items)
    split1 = int(len(all_items) * 0.6)  # 60% development
    split2 = int(len(all_items) * 0.8)  # 20% validation, 20% held-out

    development = all_items[:split1]
    validation = all_items[split1:split2]
    held_out = all_items[split2:]

    print(f"Development: {len(development)} items")
    print(f"Validation: {len(validation)} items")
    print(f"Held-out: {len(held_out)} items")

    # Save files
    save_benchmark(development, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\development.json")
    save_benchmark(validation, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\validation.json")
    save_benchmark(held_out, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\held_out.json")
    save_benchmark(all_items, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\full_benchmark.json")

    # Print statistics
    domains = {}
    languages = {}
    complexities = {}

    for item in all_items:
        domains[item.domain.value] = domains.get(item.domain.value, 0) + 1
        languages[item.language] = languages.get(item.language, 0) + 1
        complexities[item.complexity] = complexities.get(item.complexity, 0) + 1

    print("\nDomain distribution:")
    for domain, count in sorted(domains.items()):
        print(f"  {domain}: {count}")

    print("\nLanguage distribution:")
    for lang, count in sorted(languages.items()):
        print(f"  {lang}: {count}")

    print("\nComplexity distribution:")
    for comp, count in sorted(complexities.items()):
        print(f"  {comp}: {count}")

    print("\nBenchmark creation complete!")

if __name__ == "__main__":
    main()