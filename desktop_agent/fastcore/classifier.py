"""MYRAA FastCore — Deterministic Classifier.

The rule-based FastCore classifier that runs at near-zero latency.
This is the initial FastCore implementation — deterministic rules.
A trained ML model will replace/augment this once dataset + training are ready.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

from .models import (
    FastCoreOutput,
    TaskType,
    ResponseMode,
    InformationSource,
    Complexity,
    ModelRoute,
    SafetyClass,
)


# ---------------------------------------------------------------------------
# Pattern sets (consolidated from TaskRouter)
# ---------------------------------------------------------------------------

_GREETINGS = frozenset({
    'hello', 'hi', 'hey', 'hola', 'good morning', 'good afternoon',
    'good evening', 'good night', 'thanks', 'thank you', 'ok', 'okay',
    'sure', 'yes', 'no', 'bye', 'goodbye', "what's up", 'whats up',
    'sup', 'please', 'help', 'myraa', 'nice to meet you', "i'm bored",
    'stay with me', "let's talk", 'how are you', "how's it going",
    'what can you do', 'who are you', 'tell me about yourself',
})

_ACTION_VERBS = frozenset({
    'open', 'close', 'launch', 'start', 'run', 'kill', 'stop',
    'minimize', 'maximize', 'restore', 'activate', 'switch',
    'type', 'press', 'click', 'drag', 'scroll', 'move',
    'volume', 'mute', 'brightness', 'dim', 'brighten',
    'shutdown', 'restart', 'sleep', 'lock',
    'copy', 'paste', 'clipboard',
    'screenshot', 'capture', 'read',
    'create', 'write', 'save', 'delete', 'remove', 'rename',
    'browse', 'google', 'search', 'find', 'look',
    'youtube', 'video', 'watch', 'navigate',
    'download', 'upload',
})

_KNOWLEDGE_PREFIXES = (
    'what is', 'what are', 'what does', 'what do',
    'who is', 'who are', 'who was',
    'when was', 'when did', 'when is', 'when does',
    'where is', 'where are',
    'why do', 'why does', 'why is', 'why are',
    'how do', 'how does', 'how to', 'how can',
    'explain', 'describe', 'define', 'tell me about',
    'difference between', 'compare',
)

_FRESHNESS_KEYWORDS = frozenset({
    'latest', 'newest', 'current', 'recent', 'today', 'now',
    'right now', 'live', 'real-time', 'realtime', 'up-to-date',
    'updated', 'current price', 'current version', 'this week',
    'this month', 'breaking', 'just announced',
})

_BROWSER_KEYWORDS = frozenset({
    'browse', 'google', 'search on', 'look up',
    'youtube', 'video', 'watch', 'website', 'webpage',
    'url', 'browser', 'tab', 'navigate', 'download', 'upload',
})

_DESKTOP_KEYWORDS = frozenset({
    'open', 'close', 'launch', 'start', 'run', 'kill',
    'minimize', 'maximize', 'restore', 'activate', 'switch to',
    'type', 'press', 'click', 'drag', 'scroll', 'move mouse',
    'volume', 'mute', 'brightness', 'dim', 'brighten',
    'shutdown', 'restart', 'sleep', 'lock',
    'copy', 'paste', 'clipboard',
})

_FILE_KEYWORDS = frozenset({
    'create file', 'write file', 'save file', 'read file', 'open file',
    'delete file', 'remove file', 'rename file', 'move file', 'copy file',
    'create folder', 'make folder', 'list files', 'show files',
    'find files', 'search files',
})

_VISION_KEYWORDS = frozenset({
    "what's on my screen", 'what is on my screen', 'what do you see',
    'read this screen', 'read the screen', 'read this chart',
    'analyze this screen', 'analyze the screen', 'analyze this image',
    'ocr', 'extract text from', 'what do you see on',
})

_TRADING_KEYWORDS = frozenset({
    'nifty', 'banknifty', 'sensex', 'stock', 'share', 'portfolio',
    'holdings', 'positions', 'p&l', 'market', 'trading', 'trade',
    'buy', 'sell', 'option', 'futures', 'oi', 'iv', 'greeks',
    'groww', 'zerodha', 'angel', 'rsi', 'macd', 'bollinger',
    'stochastic', 'support', 'resistance', 'trend',
})

_CODING_KEYWORDS = frozenset({
    'build project', 'create project', 'write script', 'write program',
    'write code', 'write function', 'write class', 'python script',
    'python file', 'python code', 'install', 'setup', 'configure',
    'debug', 'fix bug', 'fix error', 'fix code', 'fix issue',
})

_DESIGN_KEYWORDS = frozenset({
    'design', 'sketch', 'concept', 'wireframe', '3d', 'model the',
    'blueprint', 'prototype', 'cad', 'render', 'variant',
    'optimize design', 'exploded view', 'section view', 'parametric',
    'aerodynamic', 'futuristic', 'aggressive styling',
    'lightweight version', 'reimagine', 'redesign',
})

_WEATHER_KEYWORDS = frozenset({
    'weather', 'mausam', 'temperature', 'taapman', 'forecast',
    'rain', 'baarish', 'barish', 'snow', 'barf',
    'humidity', 'nami', 'wind', 'hawa', '风暴',
    'cloudy', 'clouds', 'sunny', 'sun', 'clear sky',
    'thunderstorm', 'storm', 'cyclone', 'hurricane',
    'hot', 'garmi', 'cold', 'thand', 'warm', 'cool',
    'feels like', 'apparent temperature',
    'will it rain', 'aaj baarish', 'kal baarish',
    'kal temperature', 'aaj temperature',
    'weather bata', 'mausam bata', 'weather kaisa',
    'mausam kaisa', 'weather hai',
})

_NEWS_KEYWORDS = frozenset({
    'news', 'khabar', 'headlines', 'headline',
    'latest news', 'breaking news', 'taza khabar',
    'today news', 'aaj ki news', 'abhi ki news',
    'tech news', 'technology news', 'business news',
    'sports news', 'world news', 'india news',
    'stock market news', 'ai news', 'startup news',
    'current events', 'latest updates', 'recent news',
    'what happened', 'what is happening',
    'aaj kya hua', 'abhi kya chal raha',
})

# Module-level frozensets for detection helpers (avoid repeated construction)
_BROWSER_ACTION_APPS = frozenset({
    'youtube', 'google', 'chrome', 'firefox', 'edge',
    'github', 'gmail', 'maps', 'netflix', 'spotify',
})
_DESKTOP_ACTION_KW = frozenset({
    'open', 'close', 'launch', 'start', 'run', 'kill', 'stop',
    'minimize', 'maximize', 'restore', 'activate', 'switch',
    'type', 'press', 'click', 'drag', 'scroll', 'move',
    'volume', 'mute', 'brightness', 'dim', 'brighten',
    'shutdown', 'restart', 'sleep', 'lock',
    'copy', 'paste', 'clipboard',
    'screenshot', 'capture',
})
_FILE_PATTERNS = frozenset({
    'create a file', 'write a file', 'read the', 'read a',
    'delete the', 'rename the', 'move the', 'copy the',
    'list files', 'show files', 'find files', 'search files',
})
_FILE_NOUNS = frozenset({
    'file', 'folder', 'document', 'report', 'config', 'log', 'logs',
    'script', 'data', 'image', 'photo', 'video', 'audio',
    'csv', 'json', 'xml', 'pdf', 'docx', 'xlsx', 'txt',
})
_CODING_VERBS = frozenset({
    'build', 'create', 'write', 'make', 'debug', 'fix',
    'develop', 'code', 'program', 'implement', 'design',
})
_CODING_NOUNS = frozenset({
    'project', 'script', 'program', 'code', 'function', 'class',
    'python', 'javascript', 'html', 'css', 'java', 'c++',
    'scraper', 'crawler', 'bot', 'api', 'web app', 'app',
    'website', 'tool', 'utility', 'module', 'library', 'package',
})
_RESEARCH_KW = frozenset({
    'search for', 'find official', 'find the',
    'look up', 'research', 'browse',
})
_BROWSER_KW = frozenset({
    'youtube', 'google', 'browse', 'website', 'webpage',
    'url', 'browser', 'tab', 'navigate', 'download', 'upload',
    'watch video',
})


# ---------------------------------------------------------------------------
# FastCore Deterministic Classifier
# ---------------------------------------------------------------------------

class FastCoreClassifier:
    """Deterministic rule-based FastCore classifier.

    Latency target: <1ms on typical hardware.
    No LLM calls. Pure pattern matching + heuristics.
    """

    def classify(self, text: str) -> FastCoreOutput:
        """Classify user input into a structured FastCoreOutput."""
        t0 = time.monotonic()
        t = text.strip().lower()

        if not t:
            return self._make_output(
                TaskType.CONVERSATION, ResponseMode.FAST_ANSWER,
                InformationSource.NONE, Complexity.TRIVIAL, ModelRoute.DETERMINISTIC,
                confidence=1.0, tools_required=False,
            )

        # --- Phase 1: Greetings / simple conversation ---
        if self._is_greeting(t):
            return self._make_output(
                TaskType.CONVERSATION, ResponseMode.FAST_ANSWER,
                InformationSource.NONE, Complexity.TRIVIAL, ModelRoute.FASTCORE_DIRECT,
                confidence=0.95, tools_required=False,
                reasoning="greeting/conversation",
            )

        # --- Phase 2: Vision task (check before knowledge — "what do you see" is vision) ---
        if self._is_vision_task(t):
            return self._make_output(
                TaskType.VISION_TASK, ResponseMode.VISION,
                InformationSource.SCREEN, Complexity.MODERATE, ModelRoute.LOCAL_SMALL,
                confidence=0.90, tools_required=True, tool_names=["screenshot", "vision"],
                reasoning="vision/screen task",
            )

        # --- Phase 2b: Weather task ---
        if self._is_weather_task(t):
            return self._make_output(
                TaskType.WEATHER_TASK, ResponseMode.WEATHER,
                InformationSource.WEATHER_API, Complexity.SIMPLE, ModelRoute.LOCAL_SMALL,
                confidence=0.92, tools_required=False,
                reasoning="weather query",
            )

        # --- Phase 2c: News task ---
        if self._is_news_task(t):
            return self._make_output(
                TaskType.NEWS_TASK, ResponseMode.NEWS,
                InformationSource.NEWS_API, Complexity.MODERATE, ModelRoute.LOCAL_SMALL,
                confidence=0.90, tools_required=False,
                reasoning="news query",
            )

        # --- Phase 3: Trading task (check before knowledge — "stock price" is trading) ---
        if self._is_trading_task(t):
            freshness = self._requires_freshness(t)
            source = InformationSource.TAVILY if freshness else InformationSource.LOCAL_MODEL
            return self._make_output(
                TaskType.TRADING_TASK, ResponseMode.TRADING,
                source, Complexity.MODERATE, ModelRoute.LOCAL_LARGE,
                confidence=0.85, tools_required=True, tool_names=["trading_engine"],
                freshness_required=freshness,
                reasoning=f"trading (freshness={freshness})",
            )

        # --- Phase 4: Knowledge question (check before desktop — "explain X" is knowledge) ---
        if self._is_knowledge_question(t):
            freshness = self._requires_freshness(t)
            if freshness:
                return self._make_output(
                    TaskType.CURRENT_INFORMATION, ResponseMode.RESEARCH,
                    InformationSource.TAVILY, Complexity.MODERATE, ModelRoute.LOCAL_SMALL,
                    confidence=0.85, tools_required=True, tool_names=["web_search"],
                    freshness_required=True,
                    reasoning="knowledge + freshness → web",
                )
            return self._make_output(
                TaskType.DIRECT_KNOWLEDGE, ResponseMode.FAST_ANSWER,
                InformationSource.LOCAL_MODEL, Complexity.SIMPLE, ModelRoute.LOCAL_SMALL,
                confidence=0.90, tools_required=False,
                reasoning="knowledge question → local model",
            )

        # --- Phase 5: Browser action (check before desktop — "open YouTube" is browser) ---
        if self._is_browser_action(t):
            return self._make_output(
                TaskType.BROWSER_ACTION, ResponseMode.ACTION,
                InformationSource.TOOL_EXECUTION, Complexity.SIMPLE, ModelRoute.DETERMINISTIC,
                confidence=0.85, tools_required=True, tool_names=["browser"],
                reasoning="browser action",
            )

        # --- Phase 6: Desktop action ---
        if self._is_desktop_action(t):
            tools = self._detect_desktop_tools(t)
            return self._make_output(
                TaskType.DESKTOP_ACTION, ResponseMode.ACTION,
                InformationSource.TOOL_EXECUTION, Complexity.SIMPLE, ModelRoute.DETERMINISTIC,
                confidence=0.90, tools_required=True, tool_names=tools,
                reasoning=f"desktop action: {','.join(tools)}",
            )

        # --- Phase 7: Coding task ---
        if self._is_coding_task(t):
            return self._make_output(
                TaskType.CODING_TASK, ResponseMode.CODING,
                InformationSource.TOOL_EXECUTION, Complexity.COMPLEX, ModelRoute.LOCAL_LARGE,
                confidence=0.85, tools_required=True, tool_names=["code_execution"],
                reasoning="coding task",
            )

        # --- Phase 7: File operation ---
        if self._is_file_action(t):
            tools = self._detect_file_tools(t)
            return self._make_output(
                TaskType.FILE_TASK, ResponseMode.ACTION,
                InformationSource.TOOL_EXECUTION, Complexity.SIMPLE, ModelRoute.DETERMINISTIC,
                confidence=0.90, tools_required=True, tool_names=tools,
                reasoning=f"file action: {','.join(tools)}",
            )

        # --- Phase 8: Browser action ---
        if self._is_browser_action(t):
            return self._make_output(
                TaskType.BROWSER_ACTION, ResponseMode.ACTION,
                InformationSource.TOOL_EXECUTION, Complexity.SIMPLE, ModelRoute.DETERMINISTIC,
                confidence=0.85, tools_required=True, tool_names=["browser"],
                reasoning="browser action",
            )

        # --- Phase 9: Research/web search ---
        if self._is_research_query(t):
            return self._make_output(
                TaskType.WEB_RESEARCH, ResponseMode.RESEARCH,
                InformationSource.TAVILY, Complexity.MODERATE, ModelRoute.LOCAL_SMALL,
                confidence=0.85, tools_required=True, tool_names=["web_search"],
                reasoning="research/web search query",
            )

        # --- Phase 10: Standalone freshness ---
        if self._requires_freshness(t):
            return self._make_output(
                TaskType.CURRENT_INFORMATION, ResponseMode.RESEARCH,
                InformationSource.TAVILY, Complexity.MODERATE, ModelRoute.LOCAL_SMALL,
                confidence=0.80, tools_required=True, tool_names=["web_search"],
                freshness_required=True,
                reasoning="freshness keywords → web",
            )

        # --- Phase 11: Design task ---
        if self._is_design_task(t):
            return self._make_output(
                TaskType.DESIGN_TASK, ResponseMode.DESIGN,
                InformationSource.LOCAL_MODEL, Complexity.COMPLEX, ModelRoute.LOCAL_LARGE,
                confidence=0.85, tools_required=True, tool_names=["design_intelligence"],
                reasoning="design task",
            )

        # --- Phase 12: Fallback → reasoning ---
        return self._make_output(
            TaskType.LOCAL_REASONING, ResponseMode.REASONING,
            InformationSource.LOCAL_MODEL, Complexity.MODERATE, ModelRoute.LOCAL_LARGE,
            confidence=0.70, tools_required=False,
            reasoning="fallback → local reasoning",
        )

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _is_greeting(self, t: str) -> bool:
        if not t:
            return True
        if len(t) <= 3:
            return True
        if t in _GREETINGS:
            return True
        for prefix in ('hello', 'hey', 'hi', 'hola', 'good morning', 'good evening', 'good afternoon', 'good night'):
            if t.startswith(prefix):
                remainder = t[len(prefix):].strip().rstrip('!.,?;:')
                if not remainder:
                    return True
                wake_words = {'myraa', 'myra', 'jarvis', 'assistant', 'boss', 'sir', 'friend'}
                if remainder in wake_words:
                    return True
                if len(remainder) <= 10:
                    first_word = remainder.split()[0] if remainder.split() else ''
                    if first_word not in _ACTION_VERBS:
                        return True
                break
        if t.startswith('bye') or t.startswith('goodbye'):
            return True
        if t.startswith('thank'):
            return True
        return False

    def _is_knowledge_question(self, t: str) -> bool:
        if any(t.startswith(p) for p in _KNOWLEDGE_PREFIXES):
            return True
        # "Explain how to use X" patterns
        if re.search(r'\bexplain\b.*\bhow\s+to\s+use\b', t):
            return True
        # "What is the meaning of X" patterns
        if re.search(r'\bwhat\s+is\s+the\s+meaning\s+of\b', t):
            return True
        return False

    def _is_research_query(self, t: str) -> bool:
        """Detect research/web search queries."""
        if any(kw in t for kw in _RESEARCH_KW):
            return True
        # "search X" where X is not a knowledge question pattern
        if re.search(r'\bsearch\b', t) and not self._is_knowledge_question(t):
            return True
        return False

    def _is_browser_action(self, t: str) -> bool:
        if any(kw in t for kw in _BROWSER_KW):
            return True
        # "open X" where X is a known website/app that runs in browser
        if re.search(r'\b(open|launch|go to|visit)\b', t):
            for app in _BROWSER_ACTION_APPS:
                if app in t:
                    return True
        # "search X" without "for" is usually browser search
        if re.search(r'\bsearch\b', t) and not re.search(r'\bsearch\s+for\b', t):
            return True
        return False

    def _is_desktop_action(self, t: str) -> bool:
        if any(kw in t for kw in _DESKTOP_ACTION_KW):
            return True
        # "take a screenshot" pattern
        if re.search(r'\btake\b.*\b(screenshot|picture|photo|capture)\b', t):
            return True
        return False

    def _is_file_action(self, t: str) -> bool:
        # Check file action keywords
        if any(kw in t for kw in _FILE_KEYWORDS):
            return True
        # Check for broader file patterns
        if any(p in t for p in _FILE_PATTERNS):
            return True
        # Check for file operations with file-like nouns
        if re.search(r'\b(create|write|read|delete|remove|rename|move|copy|list|show|find|search)\b', t):
            if any(re.search(r'(?<![a-z])' + re.escape(noun) + r'(?![a-z])', t) for noun in _FILE_NOUNS):
                return True
        return False

    def _is_vision_task(self, t: str) -> bool:
        return any(kw in t for kw in _VISION_KEYWORDS)

    def _is_weather_task(self, t: str) -> bool:
        """Detect weather-related queries in English, Hindi, and Hinglish."""
        # Direct weather keyword match
        if any(kw in t for kw in _WEATHER_KEYWORDS):
            return True
        # Hindi/Hinglish patterns
        weather_patterns = (
            r'\bmausam\b', r'\btaapman\b', r'\bbaarish\b', r'\bbarish\b',
            r'\btemperature\b.*\b(kitna|hai|kaisa)\b',
            r'\bweather\b.*\b(bata|kaisa|hai|check)\b',
            r'\b(kal|aaj|abhi)\b.*\b(baarish|barish|temperature|mausam)\b',
            r'\b(baarish|barish)\b.*\b(hogi|hoega|hojayegi)\b',
        )
        return any(re.search(p, t) for p in weather_patterns)

    def _is_news_task(self, t: str) -> bool:
        """Detect news-related queries in English, Hindi, and Hinglish."""
        # Direct news keyword match
        if any(kw in t for kw in _NEWS_KEYWORDS):
            return True
        # Hindi/Hinglish patterns
        news_patterns = (
            r'\bkhabar\b', r'\bheadlines?\b',
            r'\b(latest|taza|abhi|aaj)\b.*\b(news|khabar|updates)\b',
            r'\b(news|khabar)\b.*\b(bata|dikhao|suno)\b',
            r'\bwhat\s+(is\s+)?happening\b',
            r'\bwhat\s+ happened\b',
        )
        return any(re.search(p, t) for p in news_patterns)

    def _is_trading_task(self, t: str) -> bool:
        """Check for trading keywords with word-boundary matching."""
        for kw in _TRADING_KEYWORDS:
            if re.search(r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])', t):
                return True
        return False

    def _is_design_task(self, t: str) -> bool:
        return any(kw in t for kw in _DESIGN_KEYWORDS)

    def _is_coding_task(self, t: str) -> bool:
        # Check coding keywords
        if any(kw in t for kw in _CODING_KEYWORDS):
            return True
        # Check for coding action verbs + coding nouns
        has_verb = any(v in t for v in _CODING_VERBS)
        has_noun = any(n in t for n in _CODING_NOUNS)
        if has_verb and has_noun:
            # Check if there's a desktop action first ("Open Notepad and write...")
            if re.search(r'\b(open|launch|start|run)\b', t) and re.search(r'\band\b', t):
                return False  # Let desktop action handle it
            return True
        return False

    def _requires_freshness(self, t: str) -> bool:
        return any(kw in t for kw in _FRESHNESS_KEYWORDS)

    def _detect_desktop_tools(self, t: str) -> list[str]:
        tools = []
        if re.search(r'\b(open|launch|start|run)\b', t):
            tools.append('openApplication')
        if re.search(r'\b(close|kill)\b', t):
            tools.append('closeApplication')
        if re.search(r'\b(minimize|maximize|restore|activate|switch)\b', t):
            tools.append('window_control')
        if re.search(r'\b(type|press|click|drag|scroll|move)\b', t):
            tools.append('input_control')
        if re.search(r'\b(volume|mute|brightness)\b', t):
            tools.append('system_control')
        if re.search(r'\b(shutdown|restart|sleep|lock)\b', t):
            tools.append('power_action')
        if re.search(r'\b(copy|paste|clipboard)\b', t):
            tools.append('clipboard')
        if re.search(r'\b(screenshot|capture)\b', t):
            tools.append('screenshot')
        return tools or ['unknown_desktop']

    def _detect_file_tools(self, t: str) -> list[str]:
        if re.search(r'\b(create|write|save)\b', t):
            return ['createFile']
        if re.search(r'\b(read|open)\b', t):
            return ['readFile']
        if re.search(r'\b(delete|remove)\b', t):
            return ['deleteFile']
        if re.search(r'\brename\b', t):
            return ['renameFile']
        if re.search(r'\bmove\b', t):
            return ['moveFile']
        if re.search(r'\bcopy\b', t):
            return ['copyFile']
        if re.search(r'\b(list|show|find|search)\b', t):
            return ['listFiles']
        return ['file_operation']

    def _make_output(
        self,
        task_type: TaskType,
        response_mode: ResponseMode,
        information_source: InformationSource,
        complexity: Complexity,
        model_route: ModelRoute,
        confidence: float = 0.9,
        tools_required: bool = False,
        tool_names: Optional[list[str]] = None,
        freshness_required: bool = False,
        reasoning: str = "",
    ) -> FastCoreOutput:
        escalate = confidence < 0.8
        safety = SafetyClass.SAFE
        if task_type == TaskType.TRADING_TASK:
            safety = SafetyClass.FINANCIAL
        return FastCoreOutput(
            task_type=task_type,
            response_mode=response_mode,
            information_source=information_source,
            complexity=complexity,
            model_route=model_route,
            safety_class=safety,
            confidence=confidence,
            tools_required=tools_required,
            tool_names=tool_names or [],
            freshness_required=freshness_required,
            escalate=escalate,
            reasoning=reasoning,
        )
