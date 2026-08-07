"""
MYRAA Cognitive Engine
Semantic Parser

Converts natural language into a SemanticTask.
"""

from __future__ import annotations
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
        self.knowledge = registry.get("knowledge_manager")
        self.resolver = KnowledgeResolver(self.knowledge)
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

    def parse(
        self,
        text: str,
        context=None,
    ) -> SemanticTask:
        """
        Parse user text into a SemanticTask.
        """

        semantic_context = self.context_resolver.build_context(
            context
        )
        cached = self.semantic_cache.get(text)

        if cached is not None:

            print("[CACHE] Semantic hit")

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

            print("[LIVE INFO] Routed directly to SearchWeb")

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

                print("[FAST PATH] LLM skipped")
                self.semantic_cache.put(text, task)
                return task

        route = self.router.route(text)

        print(f"[SEMANTIC] RouteResult: {route}")

        if route.handled:

            print("[FAST PATH] Router matched")

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
        print(f"[DEBUG] Trying Knowledge Resolver: {goal_text}")
        resolution = self.resolver.resolve(query)
        print(f"[DEBUG] Resolution: {resolution}")

        if resolution.resolved:

            print("[FAST PATH] Knowledge resolved")

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
        print("[LLM FALLBACK] Sending to Ollama")
        task = self.provider.parse(text)
        print("\n========== SEMANTIC PROVIDER RESULT ==========")
        print("Type :", type(task))
        print("Value:", task)
        print("=============================================\n")

        if task is None:
            raise RuntimeError(
                "Semantic provider returned None instead of a SemanticTask."
            )
        task.context = semantic_context

        task = SemanticActionMapper.populate(task)
        task = SkillResolver.process(task)
        task = ToolSelector.process(task)
        self.semantic_cache.put(text, task)

        return task