"""Unified Intelligent Task Router — the single front door for every user request.

Determines:
1. What type of task this is (TaskType)
2. Whether external tools are required
3. Whether fresh/current information is needed
4. The fastest appropriate response path
5. Tool cost awareness (minimize unnecessary tool calls)

This is a deterministic, rule-based classifier. No LLM calls.
It consumes the existing SemanticTask and enriches it with routing metadata.
"""

from __future__ import annotations

import re
import time
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task Type Taxonomy
# ---------------------------------------------------------------------------

class TaskType(Enum):
    """Canonical classification for every user request."""
    DIRECT_KNOWLEDGE = auto()    # "What is Python?" — model can answer directly
    LOCAL_REASONING = auto()     # "Explain recursion" — reasoning, no tools
    CURRENT_INFORMATION = auto() # "Latest Python version" — needs fresh data
    WEB_RESEARCH = auto()        # "Research topic X" — deep web research
    DESKTOP_ACTION = auto()      # "Open Notepad" — desktop tool needed
    BROWSER_ACTION = auto()      # "Open YouTube" — browser needed
    VISION_TASK = auto()         # "What's on my screen?" — vision needed
    FILE_TASK = auto()           # "Read file X" — file operation
    TRADING_TASK = auto()        # "Analyze NIFTY" — trading/market data
    CODING_TASK = auto()         # "Build a Python project" — code execution
    DESIGN_TASK = auto()         # "Design a futuristic bike" — design intelligence
    MULTIMODAL_TASK = auto()     # Complex multi-subsystem tasks
    CONVERSATION = auto()        # "Hello" — simple chat, no tools


class ResponseMode(Enum):
    """How to produce the response."""
    FAST_ANSWER = auto()        # Direct from model, lowest latency
    REASONING = auto()          # Model + reasoning, no tools
    RESEARCH = auto()           # Web search + synthesis
    ACTION = auto()             # Desktop/browser tool execution
    VISION = auto()             # Screen analysis
    TRADING = auto()            # Market data + analysis
    CODING = auto()             # Code generation/execution
    DESIGN = auto()             # Design intelligence pipeline
    MULTIMODAL = auto()         # Multiple subsystems


# ---------------------------------------------------------------------------
# Freshness Detection
# ---------------------------------------------------------------------------

_FRESHNESS_PATTERNS = re.compile(
    r'\b('
    r'latest|newest|current|recent|today|now|right\s+now|'
    r'live|real[\-\s]?time|up[\-\s]?to[\-\s]?date|updated|'
    r'current\s+price|current\s+version|this\s+week|this\s+month|'
    r'right\s+away|as\s+of|breaking|just\s+announced'
    r')\b',
    re.IGNORECASE,
)


def requires_freshness(text: str) -> bool:
    """Detect whether the request requires current/fresh information."""
    return bool(_FRESHNESS_PATTERNS.search(text))


# ---------------------------------------------------------------------------
# Tool Necessity Keywords
# ---------------------------------------------------------------------------

# Desktop actions — these REQUIRE tool execution
_DESKTOP_ACTION_PATTERNS = re.compile(
    r'\b('
    r'open|launch|start|run|close|kill|'
    r'minimize|maximize|restore|activate|switch\s+to|'
    r'type|press|click|drag|scroll|move\s+mouse|'
    r'volume|mute|brightness|'
    r'shutdown|restart|sleep|lock|'
    r'copy|paste|clipboard|'
    r'screenshot|capture|read\s+screen'
    r')\b',
    re.IGNORECASE,
)

# Browser actions
_BROWSER_ACTION_PATTERNS = re.compile(
    r'\b('
    r'browse|google|search\s+on|look\s+up|'
    r'youtube|video|watch|'
    r'website|webpage|url|'
    r'browser|tab|navigate|'
    r'gmail|github|chatgpt|reddit|wikipedia|linkedin|'
    r'instagram|facebook|twitter|netflix|spotify|whatsapp|'
    r'download|upload'
    r')\b',
    re.IGNORECASE,
)


def _named_site(text: str) -> str | None:
    """Return the canonical URL when ``text`` names a known website.

    Uses the ONE website resolver (desktop_agent.tools_websites); this module
    keeps no site table of its own, so a new alias never needs a change here.
    """
    try:
        from desktop_agent.tools_websites import SITE_URLS, resolve_site
    except Exception:  # pragma: no cover - import guard
        return None
    lowered = text.lower()
    for alias in SITE_URLS:
        # Single-letter aliases ("x") are too easy to hit by accident.
        if len(alias) < 2:
            continue
        if re.search(r'(?<![a-z])' + re.escape(alias) + r'(?![a-z])', lowered):
            return resolve_site(alias)
    return None

# File operations
_FILE_ACTION_PATTERNS = re.compile(
    r'\b('
    r'create\s+(a\s+)?file|write\s+(a\s+)?file|save\s+(a\s+)?file|'
    r'read\s+(a\s+)?file|open\s+(a\s+)?file|'
    r'delete\s+(a\s+)?file|remove\s+(a\s+)?file|'
    r'rename|move\s+(a\s+)?file|copy\s+(a\s+)?file|'
    r'create\s+(a\s+)?folder|make\s+(a\s+)?folder|'
    r'list\s+files|show\s+files|find\s+files|search\s+files'
    r')\b',
    re.IGNORECASE,
)

# Vision tasks
_VISION_PATTERNS = re.compile(
    r'\b('
    r"what(?:'s|\s+(?:is|are))\s+(on\s+)?my\s+screen|"
    r'read\s+(this|the)\s+(screen|chart|text|display)|'
    r'what\s+do\s+you\s+see|'
    r'analyze\s+(this|the)\s+(screen|image|screenshot)|'
    r'ocr|extract\s+text\s+from'
    r')\b',
    re.IGNORECASE,
)

# Trading / market
_TRADING_PATTERNS = re.compile(
    r'\b('
    r'nifty|banknifty|sensex|stock|share|'
    r'portfolio|holdings|positions|p[\&\s]*l|'
    r'market|trading|trade|buy|sell|'
    r'option|futures|oi|iv|greeks|'
    r'groww|zerodha|angel|'
    r'rsi|macd|bollinger|stochastic|'
    r'support|resistance|trend'
    r')\b',
    re.IGNORECASE,
)

# Coding / project
_CODING_PATTERNS = re.compile(
    r'\b('
    r'build\s+(a\s+)?project|create\s+(a\s+)?project|'
    r'write\s+(a\s+\w+\s+)?(script|program|code|function|class)|'
    r'python\s+(script|file|code)|'
    r'install|setup|configure|'
    r'debug|fix\s+(this|the|a)?\s*(\w+\s+)?(bug|error|code|issue|problem)'
    r')\b',
    re.IGNORECASE,
)

# Knowledge / explanation patterns (no tools needed)
_KNOWLEDGE_PATTERNS = re.compile(
    r'\b('
    r'what\s+is|what\s+are|what\s+does|what\s+do|'
    r'who\s+is|who\s+are|who\s+was|'
    r'when\s+was|when\s+did|when\s+is|'
    r'where\s+is|where\s+are|'
    r'why\s+do|why\s+does|why\s+is|why\s+are|'
    r'how\s+do|how\s+does|how\s+to|how\s+can|'
    r'explain|describe|define|tell\s+me\s+about|'
    r'difference\s+between|compare|'
    r'what\s+is\s+the\s+meaning\s+of'
    r')\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Routing Decision
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RoutingDecision:
    """Complete routing decision for a user request."""
    task_type: TaskType
    response_mode: ResponseMode
    tools_required: bool
    freshness_required: bool
    confidence: float
    reasoning: str
    estimated_latency_ms: float = 0.0
    tool_names: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The Task Router
# ---------------------------------------------------------------------------

class TaskRouter:
    """Single front door for classifying user requests.

    Deterministic, rule-based. No LLM calls. Extremely low latency.

    Usage:
        router = TaskRouter()
        decision = router.route("What is Python?")
        # decision.tools_required == False
        # decision.response_mode == ResponseMode.FAST_ANSWER
    """

    def route(self, text: str) -> RoutingDecision:
        """Classify a user request and return a routing decision."""
        t0 = time.monotonic()
        text = text.strip()

        if not text:
            return self._empty()

        # --- Phase 1: Direct pattern matching (fastest) ---

        # 1a. Empty / greeting / simple
        if self._is_conversational(text):
            return self._decision(
                TaskType.CONVERSATION,
                ResponseMode.FAST_ANSWER,
                tools_required=False,
                freshness_required=False,
                confidence=0.95,
                reasoning="Conversational / greeting — no tools needed",
                latency_start=t0,
            )

        # 1b. Browser action detected (check BEFORE desktop — "open YouTube" is browser)
        if _BROWSER_ACTION_PATTERNS.search(text) and not self._is_knowledge_question(text):
            return self._decision(
                TaskType.BROWSER_ACTION,
                ResponseMode.ACTION,
                tools_required=True,
                freshness_required=False,
                confidence=0.85,
                reasoning="Browser action detected",
                latency_start=t0,
                tool_names=["browser"],
            )

        # 1c. Desktop action detected
        if _DESKTOP_ACTION_PATTERNS.search(text) and not self._is_knowledge_question(text):
            tools = self._detect_desktop_tools(text)
            return self._decision(
                TaskType.DESKTOP_ACTION,
                ResponseMode.ACTION,
                tools_required=True,
                freshness_required=False,
                confidence=0.90,
                reasoning=f"Desktop action detected: {tools}",
                latency_start=t0,
                tool_names=tools,
            )

        # 1d. File operation detected
        if _FILE_ACTION_PATTERNS.search(text):
            tools = self._detect_file_tools(text)
            return self._decision(
                TaskType.FILE_TASK,
                ResponseMode.ACTION,
                tools_required=True,
                freshness_required=False,
                confidence=0.90,
                reasoning=f"File operation detected: {tools}",
                latency_start=t0,
                tool_names=tools,
            )

        # 1e. Vision task detected
        if _VISION_PATTERNS.search(text):
            return self._decision(
                TaskType.VISION_TASK,
                ResponseMode.VISION,
                tools_required=True,
                freshness_required=False,
                confidence=0.90,
                reasoning="Vision / screen analysis task",
                latency_start=t0,
                tool_names=["screenshot", "vision"],
            )

        # 1f. Trading task detected
        if _TRADING_PATTERNS.search(text):
            freshness = requires_freshness(text)
            return self._decision(
                TaskType.TRADING_TASK,
                ResponseMode.TRADING,
                tools_required=True,
                freshness_required=freshness,
                confidence=0.85,
                reasoning=f"Trading/market task (freshness={freshness})",
                latency_start=t0,
                tool_names=["trading_engine"],
            )

        # 1h. Coding task detected (check BEFORE desktop — "write code" is coding)
        if _CODING_PATTERNS.search(text):
            return self._decision(
                TaskType.CODING_TASK,
                ResponseMode.CODING,
                tools_required=True,
                freshness_required=False,
                confidence=0.85,
                reasoning="Coding / project task",
                latency_start=t0,
                tool_names=["code_execution"],
            )

        # --- Phase 2: Knowledge question (no tools) ---

        if self._is_knowledge_question(text):
            freshness = requires_freshness(text)
            if freshness:
                # "What is the latest Python version?" — needs web
                return self._decision(
                    TaskType.CURRENT_INFORMATION,
                    ResponseMode.RESEARCH,
                    tools_required=True,
                    freshness_required=True,
                    confidence=0.85,
                    reasoning="Knowledge question with freshness requirement — web research needed",
                    latency_start=t0,
                    tool_names=["web_search"],
                )
            # "What is Python?" — direct answer from model
            return self._decision(
                TaskType.DIRECT_KNOWLEDGE,
                ResponseMode.FAST_ANSWER,
                tools_required=False,
                freshness_required=False,
                confidence=0.90,
                reasoning="Knowledge question — direct model answer, no tools",
                latency_start=t0,
            )

        # --- Phase 2b: Standalone freshness query (no question pattern) ---
        # "Latest Python version", "Current weather", etc. — these are not
        # knowledge questions but require fresh data.
        if requires_freshness(text):
            return self._decision(
                TaskType.CURRENT_INFORMATION,
                ResponseMode.RESEARCH,
                tools_required=True,
                freshness_required=True,
                confidence=0.80,
                reasoning="Freshness keywords detected — current information needed",
                latency_start=t0,
                tool_names=["web_search"],
            )

        # --- Phase 3: Fallback — default to reasoning (no tools) ---

        return self._decision(
            TaskType.LOCAL_REASONING,
            ResponseMode.REASONING,
            tools_required=False,
            freshness_required=False,
            confidence=0.70,
            reasoning="No tool patterns matched — model reasoning path",
            latency_start=t0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_conversational(self, text: str) -> bool:
        """Check if the text is a greeting, thanks, or simple chat.

        Uses both exact-match and prefix/pattern detection so that
        wake-word + greeting combinations (e.g. "hello myraa",
        "hey myra") are always caught as CONVERSATION.
        """
        t = text.lower().strip()
        if not t:
            return True

        # Exact-match greetings (single word or short phrase)
        exact_greetings = {
            'hello', 'hi', 'hey', 'good morning', 'good afternoon',
            'good evening', 'good night', 'thanks', 'thank you',
            'ok', 'okay', 'sure', 'yes', 'no', 'bye', 'goodbye',
            'how are you', "what's up", 'whats up', 'sup',
            'please', 'help', 'myraa', 'nice to meet you',
            "i'm bored", 'stay with me', "let's talk",
        }
        if t in exact_greetings:
            return True

        # Very short text (1-3 chars) is always conversational
        if len(t) <= 3:
            return True

        # Prefix patterns: greeting word optionally followed by wake-word
        # Covers: "hello myraa", "hey myra", "hi myraa", etc.
        _GREETING_PREFIXES = (
            'hello', 'hey', 'hi', 'hola',
            'good morning', 'good evening', 'good afternoon', 'good night',
        )
        for prefix in _GREETING_PREFIXES:
            if t.startswith(prefix):
                remainder = t[len(prefix):].strip()
                # Empty remainder = just the greeting word
                if not remainder:
                    return True
                # Remainder is only a wake-word or punctuation
                wake_words = {'myraa', 'myra', 'jarvis', 'assistant', 'boss', 'sir', 'friend'}
                cleaned = remainder.rstrip('!.,?;:')
                if cleaned in wake_words:
                    return True
                # Short conversational suffixes: "hello there", "hey buddy"
                if len(cleaned) <= 10 and not any(
                    c in cleaned for c in '?!.'
                ):
                    # Could be a short conversational phrase — check it
                    # doesn't contain action verbs
                    _ACTION_VERBS = {
                        'open', 'close', 'search', 'find', 'create', 'delete',
                        'write', 'read', 'run', 'start', 'stop', 'take',
                        'show', 'what', 'how', 'why', 'where', 'when',
                        'who', 'which', 'explain', 'tell',
                    }
                    first_word = cleaned.split()[0] if cleaned.split() else ''
                    if first_word not in _ACTION_VERBS:
                        return True
                break

        # Farewell patterns
        if t.startswith('bye') or t.startswith('goodbye'):
            remainder = t.lstrip('bye').lstrip('goodbye').strip().rstrip('!.,?;:')
            if not remainder or remainder in {'myraa', 'myra', 'see you', 'good night'}:
                return True

        # Thanks patterns
        if t.startswith('thank') or t.startswith('thanks'):
            return True

        # "How are you" variants
        if t.startswith('how are you') or t.startswith("how's it going"):
            return True

        # "What can you do" / "who are you" / "tell me about yourself"
        if t in {
            'what can you do', 'what can you do?', 'who are you',
            'who are you?', 'tell me about yourself',
            'what are you doing', 'what are you doing?',
            'are you there', 'are you there?',
        }:
            return True

        return False

    def _is_knowledge_question(self, text: str) -> bool:
        """Check if the text is a knowledge/explanation question."""
        return bool(_KNOWLEDGE_PATTERNS.search(text))

    def _detect_desktop_tools(self, text: str) -> list[str]:
        """Detect which desktop tools are likely needed."""
        tools = []
        t = text.lower()
        if re.search(r'\b(open|launch|start|run|go\s+to|visit)\b', t):
            # A named website must reach the URL opener, never the application
            # launcher ("Open YouTube" is not an application).
            if _named_site(t):
                tools.append('openWebsite')
            else:
                tools.append('openApplication')
        if re.search(r'\b(close|kill)\b', t):
            tools.append('closeApplication')
        if re.search(r'\b(minimize|maximize|restore|activate|switch)\b', t):
            tools.append('window_control')
        if re.search(r'\b(type|press|click|drag|scroll|move\s+mouse)\b', t):
            tools.append('input_control')
        if re.search(r'\b(volume|mute|brightness)\b', t):
            tools.append('system_control')
        if re.search(r'\b(shutdown|restart|sleep|lock)\b', t):
            tools.append('power_action')
        if re.search(r'\b(copy|paste|clipboard)\b', t):
            tools.append('clipboard')
        if re.search(r'\b(screenshot|capture|read\s+screen)\b', t):
            tools.append('screenshot')
        return tools or ['unknown_desktop_action']

    def _detect_file_tools(self, text: str) -> list[str]:
        """Detect which file tools are likely needed."""
        t = text.lower()
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
        if re.search(r'\b(folder|directory)\b', t):
            return ['openFolder']
        return ['file_operation']

    def _decision(
        self,
        task_type: TaskType,
        response_mode: ResponseMode,
        tools_required: bool,
        freshness_required: bool,
        confidence: float,
        reasoning: str,
        latency_start: float = 0.0,
        tool_names: Optional[list[str]] = None,
    ) -> RoutingDecision:
        elapsed = (time.monotonic() - latency_start) * 1000
        return RoutingDecision(
            task_type=task_type,
            response_mode=response_mode,
            tools_required=tools_required,
            freshness_required=freshness_required,
            confidence=confidence,
            reasoning=reasoning,
            estimated_latency_ms=round(elapsed, 2),
            tool_names=tool_names or [],
        )

    def _empty(self) -> RoutingDecision:
        return RoutingDecision(
            task_type=TaskType.CONVERSATION,
            response_mode=ResponseMode.FAST_ANSWER,
            tools_required=False,
            freshness_required=False,
            confidence=0.0,
            reasoning="Empty input",
        )
