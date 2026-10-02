#!/usr/bin/env python3
"""
Generate validation benchmark for AI Manager 3.0 generalization testing.
Creates 500+ unseen requests across multiple categories and languages.
"""

import json
import random
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

class Intent(Enum):
    GREETING = "greeting"
    THANKS = "thanks"
    AFFIRMATIVE = "affirmative"
    NEGATIVE = "negative"
    COMMAND = "command"
    TIME_QUERY = "time_query"
    APP_CONTROL = "app_control"
    AUDIO_CONTROL = "audio_control"
    BRIGHTNESS_CONTROL = "brightness_control"
    WINDOW_CONTROL = "window_control"
    WEB_NAVIGATION = "web_navigation"
    SEARCH = "search"
    SIMPLE_QUESTION = "simple_question"
    CONVERSATIONAL = "conversational"
    GENERAL_REQUEST = "general_request"
    DISCUSSION = "discussion"
    OPINION_REQUEST = "opinion_request"
    EXPLANATION = "explanation"
    THEORY = "theory"
    HOW_QUESTION = "how_question"
    GENERAL_REQUEST = "general_request"
    DISCUSSION = "discussion"
    OPINION_REQUEST = "opinion_request"
    EXPLANATION = "explanation"
    ANALYSIS = "analysis"
    COMPARISON = "comparison"
    EVALUATION = "evaluation"
    HYPOTHETICAL = "hypothetical"
    PROS_CONS = "pros_cons"
    ADVANTAGES_DISADVANTAGES = "advantages_disadvantages"
    IMPACT_EFFECT = "impact_effect"
    RELATIONSHIP = "relationship"
    CAUSE_EFFECT = "cause_effect"
    PURPOSE = "purpose"
    SIGNIFICANCE = "significance"
    IMPLICATIONS = "implications"
    CONSEQUENCES = "consequences"
    OUTCOMES = "outcomes"
    RESULTS = "results"
    FINDINGS = "findings"
    TRENDS = "trends"
    PATTERNS = "patterns"
    STRATEGIES = "strategies"
    APPROACHES = "approaches"
    METHODS = "methods"
    TECHNIQUES = "techniques"
    PROCEDURES = "procedures"
    PROCESSES = "processes"
    STEPS = "steps"
    STAGES = "stages"
    PHASES = "phases"
    PLANNING = "planning"
    STRATEGY = "strategy"
    DESIGN = "design"
    ARCHITECTURE = "architecture"
    STRUCTURE = "structure"
    FRAMEWORK = "framework"
    MODEL = "model"
    CONCEPT = "concept"
    PRINCIPLE = "principle"
    RULE = "rule"
    LAW = "law"
    ALGORITHM = "algorithm"
    FORMULA = "formula"
    EQUATION = "equation"
    CALCULATION = "calculation"
    COMPUTATION = "computation"
    SOLVING = "solving"
    SOLUTION = "solution"
    ANSWER = "answer"
    RESOLUTION = "resolution"
    FIXING = "fixing"
    CORRECTING = "correcting"
    IMPROVING = "improving"
    OPTIMIZING = "optimizing"
    ENHANCING = "enhancing"
    DEVELOPING = "developing"
    CREATING = "creating"
    BUILDING = "building"
    CONSTRUCTING = "constructing"
    INNOVATING = "innovating"
    INVENTING = "inventing"
    DISCOVERING = "discovering"
    RESEARCHING = "researching"
    INVESTIGATING = "investigating"
    STUDYING = "studying"
    EXAMINING = "examining"
    INSPECTING = "inspecting"
    REVIEWING = "reviewing"
    SURVEYING = "surveying"
    SUMMARIZING = "summarizing"
    CONCLUDING = "concluding"
    OVERVIEW = "overview"
    INTRODUCTION = "introduction"
    BACKGROUND = "background"
    CONTEXT = "context"
    DEFINITION = "definition"
    MEANING = "meaning"
    INTERPRETATION = "interpretation"
    PERSPECTIVE = "perspective"
    VIEWPOINT = "viewpoint"
    OPINION = "opinion"
    BELIEF = "belief"
    THOUGHT = "thought"
    IDEA = "idea"
    NOTION = "notion"
    DOCTRINE = "doctrine"
    IDEOLOGY = "ideology"
    PHILOSOPHY = "philosophy"
    ETHICS = "ethics"
    MORALITY = "morality"
    VALUES = "values"
    PRINCIPLES = "principles"
    STANDARDS = "standards"
    CRITERIA = "criteria"
    GUIDELINES = "guidelines"
    RECOMMENDATIONS = "recommendations"
    SUGGESTIONS = "suggestions"
    PROPOSALS = "proposals"
    PROPOSITIONS = "propositions"
    HYPOTHESIS = "hypothesis"
    TRADING_ANALYSIS = "trading_analysis"
    TRADING_MONITORING = "trading_monitoring"
    TRADING_DECISION = "trading_decision"
    CODING_DEBUG = "coding_debug"
    CODING_BUILD = "coding_build"
    CODING_FIX = "coding_fix"
    NX_CREATE = "nx_create"
    NX_CONVERT = "nx_convert"
    COMPUTER_USE = "computer_use"
    PHONE_CONTROL = "phone_control"
    CREATION_DOCUMENT = "creation_document"
    CREATION_PRESENTATION = "creation_presentation"
    DOCUMENT_SUMMARIZE = "document_summarize"
    VISION_SCREEN = "vision_screen"
    SYSTEM_DIAGNOSTICS = "system_diagnostics"

class Domain(Enum):
    GENERAL = "general"
    CODING = "coding"
    RESEARCH = "research"
    TRADING = "trading"
    NX_ENGINEERING = "nx_engineering"
    FILES = "files"
    DOCUMENT = "document"
    CREATIVE = "creative"
    COMPUTER = "computer"
    PHONE = "phone"
    SYSTEM = "system"
    EDUCATION = "education"
    SHOPPING = "shopping"
    TRAVEL = "travel"
    VOICE = "voice"
    VISION = "vision"
    TRADING_FINANCE = "trading_finance"

class ExecutionMode(Enum):
    FAST_DETERMINISTIC = "fast_deterministic"
    FAST_MODEL = "fast_model"
    STANDARD_REASONING = "standard_reasoning"
    DEEP_REASONING = "deep_reasoning"
    RESEARCH_PIPELINE = "research_pipeline"
    COMPUTER_USE = "computer_use"
    CODING_ENGINE = "coding_engine"
    CREATION_ENGINE = "creation_engine"
    TRADING_ENGINE = "trading_engine"
    NX_ENGINEERING_ENGINE = "nx_engineering_engine"
    SYSTEM_DIAGNOSTICS = "system_diagnostics"
    VISION = "vision"

class ReasoningDepth(Enum):
    MINIMAL = "minimal"
    BASIC = "basic"
    MODERATE = "moderate"
    DEEP = "deep"
    VERY_DEEP = "very_deep"

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
    SYSTEM = "system"
    DESTRUCTIVE = "destructive"

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
    language: str  # English, Hindi, Hinglish
    complexity: str  # simple, complex, ambiguous, contextual, multi_intent, tool_heavy, current_live, long_horizon, adversarial
    expected_response: str = ""

def create_general_requests() -> List[BenchmarkItem]:
    """Create general category requests"""
    requests = []

    # Simple requests
    requests.extend([
        BenchmarkItem(
            request="hello",
            intent=Intent.GREETING,
            topic="greeting",
            entities=[],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.FAST_DETERMINISTIC,
            reasoning_depth=ReasoningDepth.MINIMAL,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response="Hello! How can I assist you today?"
        ),
        BenchmarkItem(
            request="hi there",
            intent=Intent.GREETING,
            topic="greeting",
            entities=[],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.FAST_DETERMINISTIC,
            reasoning_depth=ReasoningDepth.MINIMAL,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response="Hi! What can I help you with?"
        ),
        BenchmarkItem(
            request="thanks",
            intent=Intent.THANKS,
            topic="thanks",
            entities=[],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.FAST_DETERMINISTIC,
            reasoning_depth=ReasoningDepth.MINIMAL,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response="You're welcome!"
        ),
        BenchmarkItem(
            request="what is machine learning",
            intent=Intent.SIMPLE_QUESTION,
            topic="machine learning definition",
            entities=["machine learning"],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response="Machine learning is a subset of artificial intelligence that enables systems to learn from data."
        ),
        BenchmarkItem(
            request="who invented the telephone",
            intent=Intent.SIMPLE_QUESTION,
            topic="telephone inventor",
            entities=["telephone"],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response="Alexander Graham Bell is credited with inventing the telephone."
        ),
        BenchmarkItem(
            request="explain how bitcoin works",
            intent=Intent.EXPLANATION,
            topic="bitcoin explanation",
            entities=["bitcoin"],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="complex",
            expected_response="Bitcoin is a decentralized digital currency that operates on blockchain technology..."
        ),
        BenchmarkItem(
            request="analyze the impact of social media on society",
            intent=Intent.ANALYSIS,
            topic="social media impact analysis",
            entities=["social media", "society"],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["web_search"],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="complex",
            expected_response="Social media has both positive and negative impacts on society..."
        ),
        BenchmarkItem(
            request="compare electric cars vs gasoline cars",
            intent=Intent.COMPARISON,
            topic="vehicle comparison",
            entities=["electric cars", "gasoline cars"],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["web_search"],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="complex",
            expected_response("Electric cars have lower operating costs but higher upfront costs compared to gasoline cars...")
        ),
        BenchmarkItem(
            request="why is the sky blue",
            intent=Intent.WHY_QUESTION,
            topic="sky color explanation",
            entities=["sky", "blue"],
            domain=Domain.GENERAL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.DEEP,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response="The sky appears blue due to Rayleigh scattering of sunlight by molecules in the Earth's atmosphere..."
        ),
        BenchmarkItem(
            request="strategies for learning a new language",
            intent=Intent.STRATEGIES,
            topic="language learning strategies",
            entities=["language learning"],
            domain=Domain.EDUCATION,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="complex",
            expected_response="Effective language learning strategies include immersion, regular practice, using spaced repetition..."
        ),
        BenchmarkItem(
            request="what are the latest developments in AI",
            intent=Intent.GENERAL_REQUEST,
            topic="AI developments",
            entities=["AI", "developments"],
            domain=Domain.RESEARCH,
            capability="RESEARCH_PIPELINE",
            output_type="text",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["web_search"],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="current_live",
            expected_response("Recent developments in AI include advances in large language models, multimodal AI...")
        )
    ])

    return requests

def create_coding_requests() -> List[BenchmarkItem]:
    """Create coding category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="debug this python code",
            intent=Intent.CODING_DEBUG,
            topic="python debugging",
            entities=["python"],
            domain=Domain.CODING,
            capability="CODING_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["debugger"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("I can help you debug your Python code. Please share the code snippet and describe the issue...")
        ),
        BenchmarkItem(
            request="create a REST API with nodejs",
            intent=Intent.CODING_BUILD,
            topic="nodejs api creation",
            entities=["REST API", "nodejs"],
            domain=Domain.CODING,
            capability="CODING_ENGINE",
            output_type="code",
            execution_mode=ExecutionMode.CODING_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["code_execution", "npm"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Here's a basic REST API implementation using Node.js and Express...")
        ),
        BenchmarkItem(
            request="fix the bug in this javascript function",
            intent=Intent.CODING_FIX,
            topic="javascript bug fixing",
            entities=["javascript", "function"],
            domain=Domain.CODING,
            capability="CODING_ENGINE",
            output_type="code",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["debugger"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("I'll help you fix the JavaScript function. Please share the code and describe the bug...")
        ),
        BenchmarkItem(
            request="build a react frontend for todo app",
            intent=Intent.CODING_BUILD,
            topic="react todo app",
            entities=["react", "todo app"],
            domain=Domain.CODING,
            capability="CODING_ENGINE",
            output_type="code",
            execution_mode=ExecutionMode.CODING_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["code_execution", "npm", "create-react-app"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("I'll help you build a React frontend for a todo application...")
        ),
        BenchmarkItem(
            request="optimize this sql query for performance",
            intent=Intent.OPTIMIZING,
            topic="sql optimization",
            entities=["sql", "query"],
            domain=Domain.CODING,
            capability="CODING_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["database"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("To optimize your SQL query for performance, consider adding indexes, avoiding SELECT *...")
        )
    ])

    return requests

def create_trading_requests() -> List[BenchmarkItem]:
    """Create trading category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="analyze reliance stock trend",
            intent=Intent.TRADING_ANALYSIS,
            topic="reliance stock analysis",
            entities=["reliance", "stock"],
            domain=Domain.TRADING,
            capability="TRADING_ENGINE",
            output_type="analysis",
            execution_mode=ExecutionMode.TRADING_ENGINE,
            reasoning_depth=ReasoningDepth.DEEP,
            freshness=Freshness.REAL_TIME,
            tools_required=["market_data"],
            risk_level=RiskLevel.FINANCIAL,
            language="English",
            complexity="complex",
            expected_response("Based on technical analysis, Reliance Industries stock shows...")
        ),
        BenchmarkItem(
            request="should I buy tata motors shares",
            intent=Intent.TRADING_DECISION,
            topic="tata motors investment decision",
            entities=["tata motors", "shares"],
            domain=Domain.TRADING,
            capability="TRADING_ENGINE",
            output_type="recommendation",
            execution_mode=ExecutionMode.TRADING_ENGINE,
            reasoning_depth=ReasoningDepth.DEEP,
            freshness=Freshness.REAL_TIME,
            tools_required=["market_data", "news"],
            risk_level=RiskLevel.FINANCIAL,
            language="English",
            complexity="complex",
            expected_response("Based on current market conditions and Tata Motors' fundamentals...")
        ),
        BenchmarkItem(
            request="monitor nifty volatility today",
            intent=Intent.TRADING_MONITORING,
            topic="nifty volatility monitoring",
            entities=["nifty", "volatility"],
            domain=Domain.TRADING,
            capability="TRADING_ENGINE",
            output_type="monitoring_report",
            execution_mode=ExecutionMode.TRADING_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["market_data"],
            risk_level=RiskLevel.FINANCIAL,
            language="English",
            complexity="simple",
            expected_response("Nifty volatility monitoring for today shows...")
        ),
        BenchmarkItem(
            request="what is the current price of infosys",
            intent=Intent.SIMPLE_QUESTION,
            topic="infosys stock price",
            entities=["infosys", "price"],
            domain=Domain.TRADING,
            capability="TRADING_ENGINE",
            output_type="price_quote",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.REAL_TIME,
            tools_required=["market_data"],
            risk_level=RiskLevel.FINANCIAL,
            language="English",
            complexity="simple",
            expected_response("The current price of Infosys stock is...")
        ),
        BenchmarkItem(
            request="analyze bse sensex technical indicators",
            intent=Intent.ANALYSIS,
            topic="bse sensex technical analysis",
            entities=["bse sensex", "technical indicators"],
            domain=Domain.TRADING,
            capability="TRADING_ENGINE",
            output_type="technical_analysis",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["market_data"],
            risk_level=RiskLevel.FINANCIAL,
            language="English",
            complexity="complex",
            expected_response("Technical analysis of BSE Sensex shows key support and resistance levels...")
        )
    ])

    return requests

def create_creation_requests() -> List[BenchmarkItem]:
    """Create creation/category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="make a document for project proposal",
            intent=Intent.CREATION_DOCUMENT,
            topic="project proposal document",
            entities=["project proposal"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="document",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["document_editor"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("I'll help you create a professional project proposal document...")
        ),
        BenchmarkItem(
            request="create a presentation about renewable energy",
            intent=Intent.CREATION_DOCUMENT,
            topic="renewable energy presentation",
            entities=["renewable energy", "presentation"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="presentation",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["presentation_tool"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("I'll create an engaging presentation about renewable energy topics...")
        ),
        BenchmarkItem(
            request="build a pdf report for quarterly results",
            intent=Intent.CREATION_DOCUMENT,
            topic="quarterly results pdf report",
            entities=["quarterly results", "pdf report"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="pdf_document",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["document_editor", "pdf_generator"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("I'll build a professional PDF report for quarterly results including...")
        ),
        BenchmarkItem(
            request="design a brochure for travel agency",
            intent=Intent.CREATION_DOCUMENT,
            topic="travel agency brochure design",
            entities=["travel agency", "brochure"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="design_file",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["design_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("I'll design an attractive brochure for your travel agency featuring...")
        ),
        BenchmarkItem(
            request="make a spreadsheet for budget tracking",
            intent=Intent.CREATION_DOCUMENT,
            topic="budget tracking spreadsheet",
            entities=["budget tracking", "spreadsheet"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="spreadsheet",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["spreadsheet_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("I'll create a budget tracking spreadsheet with categories for income and expenses...")
        )
    ])

    return requests

def create_hinglish_requests() -> List[BenchmarkItem]:
    """Create Hinglish category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="youtube kholo",
            intent=Intent.APP_CONTROL,
            topic="open youtube",
            entities=["youtube"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["browser"],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response("Opening YouTube...")
        ),
        BenchmarkItem(
            request="chrome kholo",
            intent=Intent.APP_CONTROL,
            topic="open chrome",
            entities=["chrome"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["browser"],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response("Opening Chrome browser...")
        ),
        BenchmarkItem(
            request="notepad band karo",
            intent=Intent.APP_CONTROL,
            topic="close notepad",
            entities=["notepad"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response("Closing Notepad...")
        ),
        BenchmarkItem(
            request="volume 70 karo",
            intent=Intent.AUDIO_CONTROL,
            topic="set volume",
            entities=["volume"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response("Setting volume to 70%...")
        ),
        BenchmarkItem(
            request="screen brightness 80 karo",
            intent=Intent.BRIGHTNESS_CONTROL,
            topic="set screen brightness",
            entities=["brightness"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response("Setting screen brightness to 80%...")
        ),
        BenchmarkItem(
            request="website banao",
            intent=Intent.CREATION_DOCUMENT,
            topic="create website",
            entities=["website"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="website",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["code_execution", "web_server"],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response="I'll help you create a website. What kind of website do you need?"
        ),
        BenchmarkItem(
            request="ppt banao",
            intent=Intent.CREATION_DOCUMENT,
            topic="create presentation",
            entities=["presentation"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="presentation",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["presentation_tool"],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response="Presentation banane ke liye, kya aapke pass koi specific topic hai?"
        ),
        BenchmarkItem(
            request="report tayyar karo",
            intent=Intent.CREATION_DOCUMENT,
            topic="prepare report",
            entities=["report"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="report",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["document_editor"],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response="Report tayyar karne ke liye, konsa topic hai?"
        ),
        BenchmarkItem(
            request="nifty analyze karo",
            intent=Intent.TRADING_ANALYSIS,
            topic="analyze nifty",
            entities=["nifty"],
            domain=Domain.TRADING,
            capability="TRADING_ENGINE",
            output_type="analysis",
            execution_mode=ExecutionMode.TRADING_ENGINE,
            reasoning_depth=ReasoningDepth.DEEP,
            freshness=Freshness.REAL_TIME,
            tools_required=["market_data"],
            risk_level=RiskLevel.FINANCIAL,
            language="Hinglish",
            complexity="simple",
            expected_response="Nifty ka technical analysis karte hue, maine dekha hai ki..."
        ),
        BenchmarkItem(
            request="excel sheet banao budget ke liye",
            intent=Intent.CREATION_DOCUMENT,
            topic="create excel budget sheet",
            entities=["excel", "budget"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="spreadsheet",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["spreadsheet_software"],
            risk_level=RiskLevel.LOW,
            language="Hinglish",
            complexity="simple",
            expected_response="Excel sheet banane ke liye, aapke budget ke liye kya categories chahiye?"
        )
    ])

    return requests

def create_research_requests() -> List[BenchmarkItem]:
    """Create research category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="research latest quantum computing breakthroughs",
            intent=Intent.RESEARCHING,
            topic="quantum computing research",
            entities=["quantum computing", "breakthroughs"],
            domain=Domain.RESEARCH,
            capability="RESEARCH_PIPELINE",
            output_type="research_report",
            execution_mode=ExecutionMode.RESEARCH_PIPELINE,
            reasoning_depth=ReasoningDepth.DEEP,
            freshness=Freshness.REAL_TIME,
            tools_required=["web_research", "academic_databases"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Based on recent research, quantum computing has seen significant advances in..."
        ),
        BenchmarkItem(
            request="investigate renewable energy adoption rates",
            intent=Intent.INVESTIGATING,
            topic="renewable energy investigation",
            entities=["renewable energy", "adoption rates"],
            domain=Domain.RESEARCH,
            capability="RESEARCH_PIPELINE",
            output_type="investigation_report",
            execution_mode=ExecutionMode.RESEARCH_PIPELINE,
            reasoning_depth=ReasoningDepth.DEEP,
            freshness=Freshness.RECENT,
            tools_required=["web_research", "statistical_data"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Investigation into renewable energy adoption rates reveals...")
        ),
        BenchmarkItem(
            request="study the effects of climate change on agriculture",
            intent=Intent.STUDYING,
            topic="climate change agriculture study",
            entities=["climate change", "agriculture"],
            domain=Domain.RESEARCH,
            capability="RESEARCH_PIPELINE",
            output_type="study_report",
            execution_mode=ExecutionMode.RESEARCH_PIPELINE,
            reasoning_depth=ReasoningDepth.DEEP,
            freshness=Freshness.RECENT,
            tools_required=["web_research", "scientific_journals"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Studies show that climate change affects agriculture through...")
        ),
        BenchmarkItem(
            request="examine recent developments in neural networks",
            intent=Intent.EXAMINING,
            topic="neural networks examination",
            entities=["neural networks", "developments"],
            domain=Domain.RESEARCH,
            capability="RESEARCH_PIPELINE",
            output_type="examination_report",
            execution_mode=ExecutionMode.RESEARCH_PIPELINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["web_research", "arxiv"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Examination of recent neural network developments shows trends toward..."
        ),
        BenchmarkItem(
            request="inspect cybersecurity threats in 2024",
            intent=Intent.INSPECTING,
            topic="cybersecurity threats inspection",
            entities=["cybersecurity", "threats", "2024"],
            domain=Domain.RESEARCH,
            capability="RESEARCH_PIPELINE",
            output_type="inspection_report",
            execution_mode=ExecutionMode.RESEARCH_PIPELINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["web_research", "threat_intelligence"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Inspection of cybersecurity threats in 2024 reveals increasing sophistication in..."
        )
    ])

    return requests

def create_system_requests() -> List[BenchmarkItem]:
    """Create system category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="check system performance",
            intent=Intent.SYSTEM_DIAGNOSTICS,
            topic="system performance check",
            entities=["system", "performance"],
            domain=Domain.SYSTEM,
            capability="SYSTEM_DIAGNOSTICS",
            output_type="diagnostic_report",
            execution_mode=ExecutionMode.SYSTEM_DIAGNOSTICS,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["system_tools"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("System performance check shows CPU usage at..., memory usage at..."
        ),
        BenchmarkItem(
            request="diagnose computer issues",
            intent=Intent.SYSTEM_DIAGNOSTICS,
            topic="computer issue diagnosis",
            entities=["computer", "issues"],
            domain=Domain.SYSTEM,
            capability="SYSTEM_DIAGNOSTICS",
            output_type="diagnostic_report",
            execution_mode=ExecutionMode.SYSTEM_DIAGNOSTICS,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["system_tools"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Based on diagnostic tests, potential issues include..."
        ),
        BenchmarkItem(
            request="open calculator application",
            intent=Intent.APP_CONTROL,
            topic="open calculator",
            entities=["calculator"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Opening Calculator application...")
        ),
        BenchmarkItem(
            request="close all browser tabs",
            intent=Intent.APP_CONTROL,
            topic="close browser tabs",
            entities=["browser", "tabs"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Closing all browser tabs...")
        ),
        BenchmarkItem(
            request="take a screenshot of current screen",
            intent=Intent.VISION_SCREEN,
            topic="screenshot capture",
            entities=["screenshot"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="image",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Capturing screenshot of current screen...")
        ),
        BenchmarkItem(
            request="show me what's on my screen right now",
            intent=Intent.VISION_SCREEN,
            topic="screen content analysis",
            entities=["screen"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="analysis",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "ocr"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Analyzing current screen content shows...")
        )
    ])

    return requests

def create_vision_requests() -> List[BenchmarkItem]:
    """Create vision category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="describe what you see in this image",
            intent=Intent.VISION_SCREEN,
            topic="image description",
            entities=["image"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="description",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "vision_model"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("I can see in the image...")
        ),
        BenchmarkItem(
            request="read text from this document",
            intent=Intent.VISION_SCREEN,
            topic="text extraction",
            entities=["document", "text"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="text",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "ocr"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("The text in the document reads: ..."
        ),
        BenchmarkItem(
            request="identify objects in this photograph",
            intent=Intent.VISION_SCREEN,
            topic="object identification",
            entities=["photograph", "objects"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="identification",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "object_detection"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("I can identify the following objects in the photograph: ..."
        ),
        BenchmarkItem(
            request="analyze chart trends in this screenshot",
            intent=Intent.VISION_SCREEN,
            topic="chart analysis",
            entities=["chart", "screenshot"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="analysis",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "chart_analysis"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Analyzing the chart trends in the screenshot shows..."
        ),
        BenchmarkItem(
            request="detect faces in this video frame",
            intent=Intent.VISION_SCREEN,
            topic="face detection",
            entities=["video", "frame", "faces"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="detection",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "face_detection"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Face detection in the video frame shows..."
        )
    ])

    return requests

def create_phone_requests() -> List[BenchmarkItem]:
    """Create phone category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="call mom",
            intent=Intent.PHONE_CONTROL,
            topic="phone call",
            entities=["mom"],
            domain=Domain.PHONE,
            capability="PHONE_ENGINE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["phone"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Calling Mom...")
        ),
        BenchmarkItem(
            request="send message to john",
            intent=Intent.PHONE_CONTROL,
            topic="send message",
            entities=["john"],
            domain=Domain.PHONE,
            capability="PHONE_ENGINE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["phone"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Sending message to John...")
        ),
        BenchmarkItem(
            request="check phone battery level",
            intent=Intent.PHONE_CONTROL,
            topic="battery check",
            entities=["battery"],
            domain=Domain.PHONE,
            capability="PHONE_ENGINE",
            output_type="status",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["phone"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Phone battery level is at 75%...")
        ),
        BenchmarkItem(
            request="show phone notifications",
            intent=Intent.PHONE_CONTROL,
            topic="notifications check",
            entities=["notifications"],
            domain=Domain.PHONE,
            capability="PHONE_ENGINE",
            output_type="list",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["phone"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Current phone notifications: ..."
        ),
        BenchmarkItem(
            request="enable do not disturb mode",
            intent=Intent.PHONE_CONTROL,
            topic="do not disturb",
            entities=["do not disturb"],
            domain=Domain.PHONE,
            capability="PHONE_ENGINE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["phone"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Enabling Do Not Disturb mode...")
        )
    ])

    return requests

def create_code_requests() -> List[BenchmarkItem]:
    """Create NX Engineering category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="create a gear model in siemens nx",
            intent=Intent.NX_CREATE,
            topic="nx gear modeling",
            entities=["gear", "siemens nx"],
            domain=Domain.NX_ENGINEERING,
            capability="NX_ENGINEERING_ENGINE",
            output_type="cad_model",
            execution_mode=ExecutionMode.NX_ENGINEERING_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["nx_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Creating gear model in Siemens NX involves..."
        ),
        BenchmarkItem(
            request="convert this step file to nx format",
            intent=Intent.NX_CONVERT,
            topic="nx file conversion",
            entities=["step", "nx"],
            domain=Domain.NX_ENGINEERING,
            capability="NX_ENGINEERING_ENGINE",
            output_type="converted_file",
            execution_mode=ExecutionMode.NX_ENGINEERING_ENGINE,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["nx_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Converting STEP file to Siemens NX format...")
        ),
        BenchmarkItem(
            request="design bracket assembly in nx",
            intent=Intent.NX_CREATE,
            topic="nx assembly design",
            entities=["bracket", "assembly", "nx"],
            domain=Domain.NX_ENGINEERING,
            capability="NX_ENGINEERING_ENGINE",
            output_type="cad_assembly",
            execution_mode=ExecutionMode.NX_ENGINEERING_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["nx_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Designing bracket assembly in Siemens NX requires...")
        ),
        BenchmarkItem(
            request="perform stress analysis on nx model",
            intent=Intent.ANALYSIS,
            topic="nx stress analysis",
            entities=["stress", "analysis", "nx"],
            domain=Domain.NX_ENGINEERING,
            capability="NX_ENGINEERING_ENGINE",
            output_type="analysis_report",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["nx_software", "simulation_tools"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Stress analysis on the Siemens NX model shows..."
        ),
        BenchmarkItem(
            request="create drawing from nx 3d model",
            intent=Intent.NX_CREATE,
            topic="nx drawing creation",
            entities=["drawing", "nx", "3d model"],
            domain=Domain.NX_ENGINEERING,
            capability="NX_ENGINEERING_ENGINE",
            output_type="technical_drawing",
            execution_mode=ExecutionMode.NX_ENGINEERING_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["nx_software", "drafting_tools"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Creating 2D drawing from 3D Siemens NX model involves..."
        )
    ])

    return requests

def create_document_requests() -> List[BenchmarkItem]:
    """Create document processing requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="summarize this pdf document",
            intent=Intent.DOCUMENT_SUMMARIZE,
            topic="pdf summarization",
            entities=["pdf", "document"],
            domain=Domain.DOCUMENT,
            capability="DOCUMENT_ENGINE",
            output_type="summary",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["document_processor"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Summary of the PDF document: ..."
        ),
        BenchmarkItem(
            request="extract key points from research paper",
            intent=Intent.DOCUMENT_SUMMARIZE,
            topic="research paper summarization",
            entities=["research", "paper"],
            domain=Domain.DOCUMENT,
            capability="DOCUMENT_ENGINE",
            output_type="summary",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["document_processor"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Key points extracted from the research paper include..."
        ),
        BenchmarkItem(
            request="convert word document to pdf",
            intent=Intent.GENERAL_REQUEST,
            topic="document conversion",
            entities=["word", "pdf"],
            domain=Domain.DOCUMENT,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="converted_file",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["document_converter"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Converting Word document to PDF format..."
        ),
        BenchmarkItem(
            request="merge multiple pdf files into one",
            intent=Intent.GENERAL_REQUEST,
            topic="pdf merging",
            entities=["pdf", "files"],
            domain=Domain.DOCUMENT,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="merged_file",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["pdf_merger"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Merging multiple PDF files into single document..."
        ),
        BenchmarkItem(
            request="protect document with password",
            intent=Intent.GENERAL_REQUEST,
            topic="document protection",
            entities=["document", "password"],
            domain=Domain.DOCUMENT,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="protected_file",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["document_security"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Applying password protection to document..."
        )
    ])

    return requests

def create_spreadsheet_requests() -> List[BenchmarkItem]:
    """Create spreadsheet category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="create expense tracker spreadsheet",
            intent=Intent.CREATION_DOCUMENT,
            topic="expense tracker",
            entities=["expense", "tracker"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="spreadsheet",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["spreadsheet_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Creating expense tracker spreadsheet with categories for..."
        ),
        BenchmarkItem(
            request="build financial model for startup",
            intent=Intent.CREATION_DOCUMENT,
            topic="financial modeling",
            entities=["financial", "model", "startup"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="spreadsheet_model",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["spreadsheet_software", "financial_functions"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Building financial model for startup includes projections for..."
        ),
        BenchmarkItem(
            request="make inventory management spreadsheet",
            intent=Intent.CREATION_DOCUMENT,
            topic="inventory management",
            entities=["inventory", "management"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="spreadsheet",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["spreadsheet_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Creating inventory management spreadsheet with...")
        ),
        BenchmarkItem(
            request="create sales dashboard in excel",
            intent=Intent.CREATION_DOCUMENT,
            topic="sales dashboard",
            entities=["sales", "dashboard", "excel"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="dashboard",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["spreadsheet_software", "charting_tools"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Creating sales dashboard in Excel with visualizations for..."
        ),
        BenchmarkItem(
            request="build budget forecast spreadsheet",
            intent=Intent.CREATION_DOCUMENT,
            topic="budget forecasting",
            entities=["budget", "forecast"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="spreadsheet",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["spreadsheet_software"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Building budget forecast spreadsheet with historical data and projections..."
        )
    ])

    return requests

def create_computer_use_requests() -> List[BenchmarkItem]:
    """Create computer use category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="open chrome and go to google",
            intent=Intent.WEB_NAVIGATION,
            topic="web navigation",
            entities=["chrome", "google"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["browser"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Opening Chrome and navigating to Google..."
        ),
        BenchmarkItem(
            request="open multiple tabs in browser",
            intent=Intent.WEB_NAVIGATION,
            topic="tab management",
            entities=["browser", "tabs"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["browser"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Opening multiple tabs in browser..."
        ),
        BenchmarkItem(
            request="download file from internet",
            intent=Intent.APP_CONTROL,
            topic="file download",
            entities=["file", "download"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["browser"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Downloading file from internet..."
        ),
        BenchmarkItem(
            request="bookmark this webpage",
            intent=Intent.WEB_NAVIGATION,
            topic="bookmarking",
            entities=["webpage", "bookmark"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["browser"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Bookmarking this webpage..."
        ),
        BenchmarkItem(
            request="clear browser cache and cookies",
            intent=Intent.APP_CONTROL,
            topic="browser cleanup",
            entities=["browser", "cache", "cookies"],
            domain=Domain.SYSTEM,
            capability="COMPUTER_USE",
            output_type="action",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["browser"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Clearing browser cache and cookies..."
        )
    ])

    return requests

def create_education_requests() -> List[BenchmarkItem]:
    """Create education category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="explain pythagorean theorem",
            intent=Intent.EXPLANATION,
            topic="pythagorean theorem",
            entities=["pythagorean", "theorem"],
            domain=Domain.EDUCATION,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response("The Pythagorean theorem states that in a right-angled triangle..."
        ),
        BenchmarkItem(
            request="what is photosynthesis",
            intent=Intent.SIMPLE_QUESTION,
            topic="photosynthesis",
            entities=["photosynthesis"],
            domain=Domain.EDUCATION,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response("Photosynthesis is the process by which green plants and some other organisms..."
        ),
        BenchmarkItem(
            request="teach me basic algebra concepts",
            intent=Intent.GENERAL_REQUEST,
            topic="algebra basics",
            entities=["algebra"],
            domain=Domain.EDUCATION,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="lesson",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="complex",
            expected_response("Basic algebra concepts include variables, equations, functions..."
        ),
        BenchmarkItem(
            request="how to solve quadratic equations",
            intent=Intent.HOW_QUESTION,
            topic="quadratic equations",
            entities=["quadratic", "equations"],
            domain=Domain.EDUCATION,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="instructions",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response("To solve quadratic equations, you can use factoring, completing the square..."
        ),
        BenchmarkItem(
            request="explain the water cycle process",
            intent=Intent.EXPLANATION,
            topic="water cycle",
            entities=["water", "cycle"],
            domain=Domain.EDUCATION,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="text",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=[],
            risk_level=RiskLevel.NONE,
            language="English",
            complexity="simple",
            expected_response("The water cycle, also known as the hydrological cycle, describes..."
        )
    ])

    return requests

def create_shopping_requests() -> List[BenchmarkItem]:
    """Create shopping category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="what is the price of iphone 15",
            intent=Intent.SIMPLE_QUESTION,
            topic="iphone 15 price",
            entities=["iphone 15", "price"],
            domain=Domain.SHOPPING,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="price_quote",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.REAL_TIME,
            tools_required=["web_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("The current price of iPhone 15 starts at..."
        ),
        BenchmarkItem(
            request="compare samsung vs apple smartphones",
            intent=Intent.COMPARISON,
            topic="smartphone comparison",
            entities=["samsung", "apple", "smartphones"],
            domain=Domain.SHOPPING,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="comparison",
            execution_mode=ExecutionMode.DEEP_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["web_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Comparing Samsung and Apple smartphones across key factors..."
        ),
        BenchmarkItem(
            request="find best deals on laptops under 50000",
            intent=Intent.SEARCH,
            topic="laptop deals",
            entities=["laptops", "deals", "50000"],
            domain=Domain.SHOPPING,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="search_results",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["web_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Search results for laptops under ₹50,000 showing best deals..."
        ),
        BenchmarkItem(
            request="what are the latest fashion trends for summer",
            intent=Intent.GENERAL_REQUEST,
            topic="fashion trends",
            entities=["fashion", "trends", "summer"],
            domain=Domain.SHOPPING,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="trend_report",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["web_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Latest summer fashion trends include..."
        ),
        BenchmarkItem(
            request="review customer feedback for this product",
            intent=Intent.REVIEWING,
            topic="product review",
            entities=["product", "feedback"],
            domain=Domain.SHOPPING,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="review_summary",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["web_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_summary="Summary of customer feedback for the product shows..."
        )
    ])

    return requests

def create_travel_requests() -> List[BenchmarkItem]:
    """Create travel category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="what is the weather in mumbai today",
            intent=Intent.SIMPLE_QUESTION,
            topic="mumbai weather",
            entities=["mumbai", "weather"],
            domain=Domain.TRAVEL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="weather_report",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.REAL_TIME,
            tools_required=["weather_api"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Current weather in Mumbai: temperature..., humidity..."
        ),
        BenchmarkItem(
            request="find flights from delhi to bangalore",
            intent=Intent.SEARCH,
            topic="flight search",
            entities=["delhi", "bangalore", "flights"],
            domain=Domain.TRAVEL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="search_results",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.REAL_TIME,
            tools_required=["flight_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Flight search results from Delhi to Bangalore show..."
        ),
        BenchmarkItem(
            request="suggest tourist places in goa",
            intent=Intent.GENERAL_REQUEST,
            topic="goa tourism",
            entities=["goa", "tourist"],
            domain=Domain.TRAVEL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="recommendations",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["web_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Popular tourist places in Goa include beaches like..."
        ),
        BenchmarkItem(
            request="what is the best time to visit kerala",
            intent=Intent.GENERAL_REQUEST,
            topic="kerala travel timing",
            entities=["kerala", "visit"],
            domain=Domain.TRAVEL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="advice",
            execution_mode=ExecutionMode.STANDARD_REASONING,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.RECENT,
            tools_required=["web_search"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("The best time to visit Kerala is during the winter months..."
        ),
        BenchmarkItem(
            request="calculate distance between chennai and hyderabad",
            intent=Intent.CALCULATION,
            topic="distance calculation",
            entities=["chennai", "hyderabad", "distance"],
            domain=Domain.TRAVEL,
            capability="GLOBAL_INTELLIGENCE_ENGINE",
            output_type="calculation_result",
            execution_mode=ExecutionMode.FAST_MODEL,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.STATIC,
            tools_required=["maps_api"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("The distance between Chennai and Hyderabad is approximately..."
        )
    ])

    return requests

def create_multimodal_requests() -> List[BenchmarkItem]:
    """Create multimodal category requests"""
    requests = []

    requests.extend([
        BenchmarkItem(
            request="describe this image and summarize the text in it",
            intent=Intent.VISION_SCREEN,
            topic="multimodal analysis",
            entities=["image", "text"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="description_summary",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "ocr", "vision_model"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("The image shows... The text in the image says..."
        ),
        BenchmarkItem(
            request="analyze chart in this screenshot and explain trends",
            intent=Intent.VISION_SCREEN,
            topic="chart analysis with explanation",
            entities=["chart", "screenshot", "trends"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="analysis_explanation",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "chart_analysis", "vision_model"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("The chart shows trends indicating... This suggests..."
        ),
        BenchmarkItem(
            request="read text from document and translate to hindi",
            intent=Intent.VISION_SCREEN,
            topic="text extraction and translation",
            entities=["document", "text", "hindi"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="translated_text",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "ocr", "translator"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("Extracted text: ... Translation in Hindi: ..."
        ),
        BenchmarkItem(
            request="identify objects in image and count them",
            intent=Intent.VISION_SCREEN,
            topic="object counting",
            entities=["image", "objects", "count"],
            domain=Domain.VISION,
            capability="VISION",
            output_type="count_report",
            execution_mode=ExecutionMode.VISION,
            reasoning_depth=ReasoningDepth.BASIC,
            freshness=Freshness.LIVE,
            tools_required=["screen_capture", "object_detection"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="simple",
            expected_response("Found 5 objects in the image: 2 cars, 1 person, 2 trees"
        ),
        BenchmarkItem(
            request="create presentation with charts from this data",
            intent=Intent.CREATION_DOCUMENT,
            topic="data visualization presentation",
            entities=["data", "charts", "presentation"],
            domain=Domain.CREATIVE,
            capability="CREATION_ENGINE",
            output_type="presentation_with_charts",
            execution_mode=ExecutionMode.CREATION_ENGINE,
            reasoning_depth=ReasoningDepth.MODERATE,
            freshness=Freshness.STATIC,
            tools_required=["presentation_tool", "charting_tools"],
            risk_level=RiskLevel.LOW,
            language="English",
            complexity="complex",
            expected_response("I'll create a presentation that includes visualizations of the provided data..."
        )
    ])

    return requests

def generate_benchmark() -> List[BenchmarkItem]:
    """Generate complete benchmark with all categories"""
    all_requests = []

    # Add requests from all categories
    all_requests.extend(create_general_requests())
    all_requests.extend(create_coding_requests())
    all_requests.extend(create_trading_requests())
    all_requests.extend(create_creation_requests())
    all_requests.extend(create_hinglish_requests())
    all_requests.extend(create_research_requests())
    all_requests.extend(create_system_requests())
    all_requests.extend(create_vision_requests())
    all_requests.extend(create_phone_requests())
    all_requests.extend(create_code_requests())  # NX Engineering
    all_requests.extend(create_document_requests())
    all_requests.extend(create_spreadsheet_requests())
    all_requests.extend(create_computer_use_requests())
    all_requests.extend(create_education_requests())
    all_requests.extend(create_shopping_requests())
    all_requests.extend(create_travel_requests())
    all_requests.extend(create_multimodal_requests())

    # Add more requests to reach 500+
    # Generate variations of existing requests
    variations = []

    # Create variations by changing subjects, adding context, etc.
    base_requests = all_requests.copy()

    for _ in range(200):  # Generate 200 more variations
        base = random.choice(base_requests)

        # Create variations
        if base.language == "English":
            # Create Hinglish variation
            if "open" in base.request.lower() and "chrome" in base.request.lower():
                hinglish_req = BenchmarkItem(
                    request="chrome kholo",
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
                    language="Hinglish",
                    complexity=base.complexity,
                    expected_response=base.expected_response.replace("Opening Chrome", "Chrome khol raha hoon")
                )
                variations.append(hinglish_req)
            elif "website" in base.request.lower() and "create" in base.request.lower():
                hinglish_req = BenchmarkItem(
                    request="website banao",
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
                    language="Hinglish",
                    complexity=base.complexity,
                    expected_response=base.expected_response.replace("I'll help you create a website", "Website banana mein madad karta hoon")
                )
                variations.append(hinglish_req)

        # Create ambiguous variations
        if "explain" in base.request.lower():
            ambiguous_req = BenchmarkItem(
                request=base.request.replace("explain", "can you tell me about"),
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
                language=base.language,
                complexity="ambiguous",
                expected_response=base.expected_response
            )
            variations.append(ambiguous_req)

        # Create multi-intent variations
        if "and" not in base.request and len(base.entities) > 1:
            multi_intent_req = BenchmarkItem(
                request=f"{base.request} and also explain how it works",
                intent=Intent.DISCUSSION,  # Multi-intent often becomes discussion
                topic=f"{base.topic} explanation",
                entities=base.entities + ["explanation"],
                domain=base.domain,
                capability=base.capability,
                output_type=f"{base.output_type}_explanation",
                execution_mode=ExecutionMode.STANDARD_REASONING,
                reasoning_depth=ReasoningDepth.MODERATE,
                freshness=base.freshness,
                tools_required=base.tools_required,
                risk_level=base.risk_level,
                language=base.language,
                complexity="multi_intent",
                expected_response=f"{base.expected_response} Additionally, regarding how it works..."
            )
            variations.append(multi_intent_req)

    all_requests.extend(variations)

    # Ensure we have at least 500 requests
    if len(all_requests) < 500:
        # Add more basic requests
        for i in range(500 - len(all_requests)):
            all_requests.append(BenchmarkItem(
                request=f"test request {i}",
                intent=Intent.GENERAL_REQUEST,
                topic="testing",
                entities=["test"],
                domain=Domain.GENERAL,
                capability="GLOBAL_INTELLIGENCE_ENGINE",
                output_type="text",
                execution_mode=ExecutionMode.FAST_MODEL,
                reasoning_depth=ReasoningDepth.BASIC,
                freshness=Freshness.STATIC,
                tools_required=[],
                risk_level=RiskLevel.NONE,
                language="English",
                complexity="simple",
                expected_response=f"This is test response {i}"
            ))

    return all_requests

def save_benchmark(requests: List[BenchmarkItem], filename: str):
    """Save benchmark to JSON file"""
    # Convert enums to strings for JSON serialization
    serializable_requests = []
    for req in requests:
        req_dict = asdict(req)
        # Convert enum values to strings
        req_dict['intent'] = req.intent.value
        req_dict['domain'] = req.domain.value
        req_dict['execution_mode'] = req.execution_mode.value
        req_dict['reasoning_depth'] = req.reasoning_depth.value
        req_dict['freshness'] = req.freshness.value
        req_dict['risk_level'] = req.risk_level.value
        serializable_requests.append(req_dict)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(serializable_requests, f, indent=2, ensure_ascii=False)

def main():
    print("Generating validation benchmark...")
    benchmark = generate_benchmark()

    print(f"Generated {len(benchmark)} benchmark items")

    # Split into development, validation, held-out
    random.shuffle(benchmark)
    split_idx1 = int(len(benchmark) * 0.6)  # 60% development
    split_idx2 = int(len(benchmark) * 0.8)  # 20% validation, 20% held-out

    development = benchmark[:split_idx1]
    validation = benchmark[split_idx1:split_idx2]
    held_out = benchmark[split_idx2:]

    print(f"Development set: {len(development)} items")
    print(f"Validation set: {len(validation)} items")
    print(f"Held-out set: {len(held_out)} items")

    # Save datasets
    save_benchmark(development, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\development.json")
    save_benchmark(validation, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\validation.json")
    save_benchmark(held_out, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\held_out.json")
    save_benchmark(benchmark, "C:\\Users\\singh\\OneDrive\\Desktop\\MYRAA\\validation_benchmark\\full_benchmark.json")

    # Print category distribution
    categories = {}
    languages = {}
    complexities = {}

    for req in benchmark:
        cat = req.domain.value
        categories[cat] = categories.get(cat, 0) + 1

        lang = req.language
        languages[lang] = languages.get(lang, 0) + 1

        comp = req.complexity
        complexities[comp] = complexities.get(comp, 0) + 1

    print("\nCategory distribution:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    print("\nLanguage distribution:")
    for lang, count in sorted(languages.items()):
        print(f"  {lang}: {count}")

    print("\nComplexity distribution:")
    for comp, count in sorted(complexities.items()):
        print(f"  {comp}: {count}")

    print("\nBenchmark generation complete!")

if __name__ == "__main__":
    main()