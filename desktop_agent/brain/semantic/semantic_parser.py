"""
MYRAA Cognitive Engine
Semantic Parser

Converts natural language into a SemanticTask.
"""

from __future__ import annotations
import logging
log = logging.getLogger(__name__)
from .semantic_models import Intent
from .providers.provider_factory import ProviderFactory
from .semantic_models import SemanticContext, SemanticTask
from .context_resolver import ContextResolver
from .local_parser import LocalSemanticParser
from .tool_selector import ToolSelector
from .function_call_parser import FunctionCallParser
from .semantic_action_mapper import SemanticActionMapper
from desktop_agent.brain.router.intent_router import IntentRouter
from desktop_agent.brain.resolver.knowledge_resolver import KnowledgeResolver
from desktop_agent.core.app_context import registry
from pathlib import Path
from .fast_path import FastPath
from .skill_resolver import SkillResolver
from .semantic_cache import SemanticCache
from desktop_agent.brain.latency_tracing import trace_latency


class SemanticParser:

    def __init__(
        self,
        context_resolver: ContextResolver | None = None,
    ):

        self.provider = ProviderFactory.create()
        self.function_parser = FunctionCallParser()
        self.context_resolver = (
            context_resolver or ContextResolver()
        )

        self.local_parser = LocalSemanticParser()
        self.router = IntentRouter()
        # Knowledge manager accessed lazily to avoid module-level initialization
        self._knowledge_manager = None
        self.fast_path = FastPath()
        self.semantic_cache = SemanticCache()

        # ---------------------------------------------------------
        # Live information keywords
        # ---------------------------------------------------------
        self.live_information_keywords = (
            "price",
            "stock",
            "share",
            "bitcoin",
            "ethereum",
            "crypto",
            "gold",
            "silver",
            "usd",
            "inr",
            "weather",
            "temperature",
            "forecast",
            "news",
            "today news",
            "latest news",
            "headline",
            "cricket score",
            "live score",
            "ipl",
            "sensex",
            "nifty",
            "market",
            "crude oil",
            "oil price",
        )

    # ---------------------------------------------------------
    # Conversational fast path — greetings, small talk, thanks,
    # affirmatives, negatives, wake-word-only, etc.
    # Mirrors TaskRouter._is_conversational() for the semantic parser.
    # ---------------------------------------------------------
    _GREETING_WORDS = frozenset({
        "hi", "hello", "hey", "hii", "hiii", "hola", "namaste",
        "sup", "yo", "howdy", "hiya", "greetings", "good morning",
        "good afternoon", "good evening", "good night", "gm", "gn",
        "nmx", "nm", "what's up", "whats up", "wassup", "kaise ho",
        "kya haal", "kaise hai", "theek ho", "kya kar rahe",
        "aur batao", "suno", "sunno", "arre", "acha", "accha",
        "theek hai", "bilkul", "haan", "nahi", "nahin", "no",
        "yes", "yeah", "yep", "nope", "ok", "okay", "sure",
        "cool", "nice", "awesome", "great", "perfect", "excellent",
        "good", "wow", "amazing", "fantastic", "brilliant", "wonderful",
        "thanks", "thank", "thankyou", "thank you", "dhanyavaad",
        "shukriya", "bye", "goodbye", "see you", "talk to you later",
        "ttyl", "see ya", "alvida", "phir milenge",
        "help", "i need help", "can you help", "help me",
    })

    @classmethod
    def _is_conversational(cls, text: str) -> bool:
        t = text.strip().lower()
        if not t:
            return False
        # Exact match
        if t in cls._GREETING_WORDS:
            return True
        # Strip common wake-word prefixes
        for prefix in ("hey myraa", "hey myra", "myraa", "myra"):
            if t.startswith(prefix):
                t = t[len(prefix):].strip().lstrip(",.!?")
                if not t:
                    return True  # wake-word only
                break
        # Exact match after stripping
        if t in cls._GREETING_WORDS:
            return True
        # Starts with a greeting word
        first = t.split()[0] if t.split() else ""
        return first in cls._GREETING_WORDS

    @property
    def knowledge(self):
        """Lazy initialization of knowledge_manager to avoid module-level instantiation."""
        if self._knowledge_manager is None:
            from desktop_agent.core.app_context import get_knowledge_manager
            self._knowledge_manager = get_knowledge_manager()
        return self._knowledge_manager

    @property
    def resolver(self):
        """Lazy initialization of KnowledgeResolver."""
        if not hasattr(self, '_resolver'):
            self._resolver = KnowledgeResolver(self.knowledge)
        return self._resolver

    # ---------------------------------------------------------

    @trace_latency("action_latency_semantic_parsing")
    def parse(
        self,
        text: str,
        context=None,
    ) -> SemanticTask:
        """
        Parse user text into a SemanticTask.
        """
        import time as _time
        _tp0 = _time.perf_counter()
        semantic_context = self.context_resolver.build_context(
            context
        )
        cached = self.semantic_cache.get(text)
        _tp1 = _time.perf_counter()

        if cached is not None:

            log.debug("Semantic cache hit")

            cached.context = semantic_context

            return cached
        # ---------------------------------------------------------
        # Fast path: already a structured function call
        # ---------------------------------------------------------

        action = self.function_parser.parse(text)

        if action is not None:

            task = SemanticTask(
                raw_text=text,
                normalized_text=text.lower().strip(),
                confidence=action.confidence,
                context=semantic_context,
            )

            task.metadata["action"] = action.name
            task.metadata["parameters"] = action.parameters
            self.semantic_cache.put(text, task)
            return task

        goal_text = text.lower().strip()

        # ---------------------------------------------------------
        # Live Information Detection
        # ---------------------------------------------------------

        if any(

            keyword in goal_text

            for keyword in self.live_information_keywords

        ):

            task = SemanticTask(

                raw_text=text,

                normalized_text=goal_text,

                intent=Intent.SEARCH_WEB,

                confidence=1.0,

                context=semantic_context,

            )

            task.metadata["query"] = text

            task.metadata["live_information"] = True

            task = SemanticActionMapper.populate(task)

            task = ToolSelector.process(task)

            self.semantic_cache.put(text, task)

            log.debug("Live info routed to SearchWeb")

            return task
        # ---------------------------------------------------------
        # Wake Word Cleanup
        # ---------------------------------------------------------

        WAKE_WORDS = (
            "myraa",
            "hey myraa",
            "hello myraa",
            "hi myraa",
            "himarsha",
        )

        for wake in WAKE_WORDS:

            if goal_text.startswith(wake):

                goal_text = goal_text[len(wake):].strip(" ,.")

                text = goal_text

                break

        # After wake-word stripping, if nothing remains, it was a pure
        # greeting / wake-word — skip the LLM entirely.
        if not goal_text:
            log.debug("Wake-word only — returning CHAT intent (no LLM)")
            return SemanticTask(
                raw_text=text,
                normalized_text="",
                intent=Intent.CHAT,
                confidence=1.0,
                context=semantic_context,
            )

        # ---------------------------------------------------------
        # Goal commands
        # ---------------------------------------------------------

        if (
            goal_text.startswith("my goal is")
            or goal_text.startswith("set my goal to")
            or goal_text.startswith("remember my goal")
        ):
            return SemanticTask(
                raw_text=text,
                normalized_text=goal_text,
                intent=Intent.SET_GOAL,
                confidence=1.0,
                context=semantic_context,
                metadata={
                    "goal": text,
                },
            )

        if goal_text in (
            "what is my goal",
            "current goal",
            "my goal",
        ):
            return SemanticTask(
                raw_text=text,
                normalized_text=goal_text,
                intent=Intent.GET_GOAL,
                confidence=1.0,
                context=semantic_context,
            )

        if goal_text in (
            "clear my goal",
            "remove my goal",
            "forget my goal",
        ):
            return SemanticTask(
                raw_text=text,
                normalized_text=goal_text,
                intent=Intent.CLEAR_GOAL,
                confidence=1.0,
                context=semantic_context,
            )

        # ---------------------------------------------------------
        # Existing local semantic parser
        # ---------------------------------------------------------

        task = self.local_parser.parse(text)

        if task is not None:

            task.context = semantic_context

            if self.fast_path.should_skip_llm(task):

                log.debug("Fast path: LLM skipped")
                self.semantic_cache.put(text, task)
                return task

        # ---------------------------------------------------------
        # Conversational fast path — skip LLM for greetings/small talk
        # ---------------------------------------------------------
        if self._is_conversational(goal_text):
            log.debug("Conversational fast path: skipping LLM")
            task = SemanticTask(
                raw_text=text,
                normalized_text=goal_text,
                intent=Intent.CHAT,
                confidence=1.0,
                context=semantic_context,
            )
            self.semantic_cache.put(text, task)
            return task

        route = self.router.route(text)

        log.debug("RouteResult: %s", route)

        if route.handled:

            log.debug("Fast path: Router matched")

            task = SemanticTask(

                raw_text=text,

                normalized_text=text.lower().strip(),

                intent=Intent.ROUTER_ACTION,

                confidence=route.confidence,

                context=semantic_context,

                entities=[],

                metadata={

                    "action": route.action,

                    "parameters": route.parameters,

                },

            )

            task = SemanticActionMapper.populate(task)
            task = SkillResolver.process(task)

            task = ToolSelector.process(task)

            self.semantic_cache.put(text, task)
            return task

        # ---------------------------------------------------------
        # Knowledge Resolver
        # ---------------------------------------------------------

        query = goal_text

        for prefix in (
            "open ",
            "find ",
            "continue ",
            "show ",
        ):
            if query.startswith(prefix):
                query = query[len(prefix):]

        query = query.strip(" .,!?")
        log.debug("Trying Knowledge Resolver: %s", goal_text)
        resolution = self.resolver.resolve(query)
        log.debug("Resolution: %s", resolution)

        if resolution.resolved:

            log.debug("Fast path: Knowledge resolved")

            resolved_path = Path(resolution.path)

            action = (

                "openFolder"

                if resolved_path.is_dir()

                else "openFile"

            )

            task = SemanticTask(

                raw_text=text,

                normalized_text=goal_text,

                intent=Intent.ROUTER_ACTION,

                confidence=resolution.confidence,

                context=semantic_context,

                metadata={

                    "action": action,

                    "parameters": {

                        "path": str(resolved_path),

                    },

                    "knowledge": resolution,

                },

            )

            task = SemanticActionMapper.populate(task)
            task = SkillResolver.process(task)

            task = ToolSelector.process(task)
            self.semantic_cache.put(text, task)

            return task
        # ---------------------------------------------------------
        # LLM fallback (natural language only)
        # ---------------------------------------------------------
        if self.provider is None:
            # No AI provider configured/available: fall back to the rule-based
            # local parser instead of failing the request.
            task = self.local_parser.parse(text)
        else:
            log.debug("LLM fallback: calling semantic provider")
            task = self.provider.parse(text)
        log.debug("Semantic provider result type: %s", type(task))

        if task is None:
            raise RuntimeError(
                "Semantic provider returned None instead of a SemanticTask."
            )

        # Unwrap ParserResponse → SemanticTask if needed.
        from desktop_agent.brain.semantic.providers.parser_response import ParserResponse
        if isinstance(task, ParserResponse):
            task = task.task

        task.context = semantic_context

        task = SemanticActionMapper.populate(task)
        task = SkillResolver.process(task)
        task = ToolSelector.process(task)
        self.semantic_cache.put(text, task)

        return task