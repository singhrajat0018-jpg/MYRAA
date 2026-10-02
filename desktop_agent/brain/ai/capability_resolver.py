"""AI Manager 4.1 — Capability Resolution (Phase 5).

Authoritative capability-to-tool resolution chain:
  AI Manager → capability → Capability Registry → Capability Resolver → Tool Strategy → executable tool(s)

This module owns the canonical capability resolution logic, replacing the inline
logic in AIManager with a dedicated, testable component.

Registered capabilities only. Registered tools only. No fabricated tool IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from .ai_manager import (
        AIManager,
        Capability,
        CapabilityCandidate,
        Domain,
        ExecutionMode,
        Intent,
        OutputType,
        RiskLevel,
        TaskSignals,
    )

from .tool_resolver import CANONICAL_TOOL_RESOLVER, REGISTERED_TOOLS, resolve, is_resolvable


@dataclass(frozen=True)
class ToolStrategy:
    """Execution strategy for a capability's required tools."""
    
    capability_id: str
    primary_tools: Tuple[str, ...]
    fallback_tools: Tuple[str, ...]
    execution_mode: "ExecutionMode"
    risk_level: "RiskLevel"
    requires_confirmation: bool
    verification_required: bool
    timeout_ms: int
    retry_policy: Dict[str, Any]
    freshness_requirement: "Freshness" = None  # type: ignore


@dataclass(frozen=True)
class CapabilityResolution:
    """Complete capability resolution result."""
    
    capability: "Capability"
    candidate: "CapabilityCandidate"
    tool_strategy: ToolStrategy
    resolved_tools: Tuple[str, ...]
    missing_tools: Tuple[str, ...]
    warnings: Tuple[str, ...]


class CapabilityRegistry:
    """Authoritative capability registry.
    
    Single source of truth for all capabilities. No duplicate registries.
    """
    
    def __init__(self, capabilities: Optional[Dict[str, "Capability"]] = None):
        self._capabilities: Dict[str, "Capability"] = capabilities or {}
    
    def register(self, capability: "Capability") -> None:
        """Register a capability."""
        self._capabilities[capability.capability_id] = capability
    
    def get(self, capability_id: str) -> Optional["Capability"]:
        """Get a capability by ID."""
        return self._capabilities.get(capability_id)
    
    def get_all(self) -> Dict[str, "Capability"]:
        """Get all registered capabilities."""
        return dict(self._capabilities)
    
    def get_by_domain(self, domain: "Domain") -> List["Capability"]:
        """Get capabilities for a domain."""
        return [c for c in self._capabilities.values() if c.domain == domain]
    
    def get_by_intent(self, intent: "Intent") -> List["Capability"]:
        """Get capabilities supporting an intent."""
        return [c for c in self._capabilities.values() if intent in c.supported_intents]
    
    def has(self, capability_id: str) -> bool:
        """Check if capability exists."""
        return capability_id in self._capabilities


class CapabilityResolver:
    """Authoritative capability-to-tool resolver.
    
    Completes the chain: Capability → Tool Strategy → Executable Tools
    """
    
    # Risk-aware execution parameters per capability
    _CAPABILITY_EXECUTION_PARAMS: Dict[str, Dict[str, Any]] = {
        'TRADING_ENGINE': {
            'timeout_ms': 30000,
            'requires_confirmation': True,
            'verification_required': True,
            'retry_policy': {'max_attempts': 1, 'backoff_ms': 0},
            'execution_mode': 'TRADING_ENGINE',
            'risk_level': 'FINANCIAL',
        },
        'RESEARCH_PIPELINE': {
            'timeout_ms': 60000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'RESEARCH_PIPELINE',
            'risk_level': 'LOW',
        },
        'CODING_ENGINE': {
            'timeout_ms': 45000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 500},
            'execution_mode': 'CODING_ENGINE',
            'risk_level': 'LOW',
        },
        'COMPUTER_USE': {
            'timeout_ms': 15000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 500},
            'execution_mode': 'FAST_DETERMINISTIC',
            'risk_level': 'LOW',
        },
        'FILES_ENGINE': {
            'timeout_ms': 10000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 250},
            'execution_mode': 'FAST_DETERMINISTIC',
            'risk_level': 'LOW',
        },
        'PROJECT_BUILDER': {
            'timeout_ms': 120000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 3, 'backoff_ms': 1000},
            'execution_mode': 'PROJECT_BUILDER',
            'risk_level': 'LOW',
        },
        'SYSTEM_ENGINE': {
            'timeout_ms': 15000,
            'requires_confirmation': True,
            'verification_required': True,
            'retry_policy': {'max_attempts': 1, 'backoff_ms': 0},
            'execution_mode': 'SYSTEM_ENGINE',
            'risk_level': 'LOW',
        },
        'VISION_ENGINE': {
            'timeout_ms': 10000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 500},
            'execution_mode': 'VISION_ENGINE',
            'risk_level': 'LOW',
        },
        'VOICE_ENGINE': {
            'timeout_ms': 10000,
            'requires_confirmation': False,
            'verification_required': False,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 500},
            'execution_mode': 'FAST_DETERMINISTIC',
            'risk_level': 'LOW',
        },
        'DOCUMENT_ENGINE': {
            'timeout_ms': 30000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'CREATION_ENGINE',
            'risk_level': 'LOW',
        },
        'PRESENTATION_ENGINE': {
            'timeout_ms': 30000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'CREATION_ENGINE',
            'risk_level': 'LOW',
        },
        'SPREADSHEET_ENGINE': {
            'timeout_ms': 30000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'CREATION_ENGINE',
            'risk_level': 'LOW',
        },
        'CREATION_ENGINE': {
            'timeout_ms': 30000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'CREATION_ENGINE',
            'risk_level': 'LOW',
        },
        'NX_ENGINEERING_ENGINE': {
            'timeout_ms': 60000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'NX_ENGINEERING_ENGINE',
            'risk_level': 'LOW',
        },
        'SYSTEM_DIAGNOSTICS': {
            'timeout_ms': 15000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 500},
            'execution_mode': 'SYSTEM_ENGINE',
            'risk_level': 'LOW',
        },
        'GENERAL_INTELLIGENCE_ENGINE': {
            'timeout_ms': 30000,
            'requires_confirmation': False,
            'verification_required': False,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 500},
            'execution_mode': 'STANDARD_REASONING',
            'risk_level': 'NONE',
        },
        'CALENDAR_ENGINE': {
            'timeout_ms': 10000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 500},
            'execution_mode': 'FAST_DETERMINISTIC',
            'risk_level': 'LOW',
        },
        'BROWSER_ENGINE': {
            'timeout_ms': 30000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'STANDARD_REASONING',
            'risk_level': 'LOW',
        },
        'COMMUNICATION_ENGINE': {
            'timeout_ms': 15000,
            'requires_confirmation': True,
            'verification_required': True,
            'retry_policy': {'max_attempts': 1, 'backoff_ms': 0},
            'execution_mode': 'FAST_DETERMINISTIC',
            'risk_level': 'LOW',
        },
        'ARTIFACT_GENERATION_ENGINE': {
            'timeout_ms': 45000,
            'requires_confirmation': False,
            'verification_required': True,
            'retry_policy': {'max_attempts': 2, 'backoff_ms': 1000},
            'execution_mode': 'CREATION_ENGINE',
            'risk_level': 'LOW',
        },
    }
    
    def __init__(self, ai_manager: "AIManager"):
        self._ai_manager = ai_manager
        self._registry = CapabilityRegistry(ai_manager._capability_registry)
    
    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry
    
    def select_capability(
        self,
        domain: "Domain",
        intent: "Intent",
        output_type: "OutputType",
        signals: "TaskSignals",
    ) -> "CapabilityCandidate":
        """Select the best capability for the given routing context.
        
        This is the authoritative capability selection logic.
        """
        return self._ai_manager._capability_for(domain, intent, output_type, signals)
    
    def resolve_tools(self, capability: "Capability", signals: "TaskSignals") -> Tuple[str, ...]:
        """Resolve a capability's required_tools to actual registered tool names.
        
        Returns tuple of registered tool names.
        """
        tools: List[str] = []
        required = getattr(capability, 'required_tools', [])
        
        for tool_id in required:
            if tool_id in REGISTERED_TOOLS:
                tools.append(tool_id)
            elif tool_id in CANONICAL_TOOL_RESOLVER:
                resolved = CANONICAL_TOOL_RESOLVER[tool_id]
                for real_tool in resolved:
                    if real_tool not in tools:
                        tools.append(real_tool)
            # Unknown tool IDs are silently ignored (logged elsewhere)
        
        # Add tool hints from signals
        for hint in sorted(signals.tool_hints):
            if hint in REGISTERED_TOOLS and hint not in tools:
                tools.append(hint)
            elif hint in CANONICAL_TOOL_RESOLVER:
                resolved = CANONICAL_TOOL_RESOLVER[hint]
                for real_tool in resolved:
                    if real_tool not in tools:
                        tools.append(real_tool)
        
        return tuple(tools)
    
    def validate_capability_tools(self, capability: "Capability") -> Tuple[List[str], List[str]]:
        """Validate a capability's required tools.
        
        Returns (resolved_tools, missing_tools).
        """
        resolved: List[str] = []
        missing: List[str] = []
        
        required = getattr(capability, 'required_tools', [])
        for tool_id in required:
            if is_resolvable(tool_id):
                resolved.extend(resolve(tool_id))
            else:
                missing.append(tool_id)
        
        return tuple(resolved), tuple(missing)
    
    def build_tool_strategy(
        self,
        capability: "Capability",
        intent: "Intent",
        output_type: "OutputType",
        signals: "TaskSignals",
    ) -> ToolStrategy:
        """Build execution strategy for a capability."""
        from .ai_manager import ExecutionMode, RiskLevel, Freshness
        
        params = self._CAPABILITY_EXECUTION_PARAMS.get(
            capability.capability_id,
            self._CAPABILITY_EXECUTION_PARAMS['GENERAL_INTELLIGENCE_ENGINE']
        )
        
        primary_tools = self.resolve_tools(capability, signals)
        
        # Get fallback tools from capability's fallback_models
        fallback_tools: List[str] = []
        for model in getattr(capability, 'fallback_models', []):
            if model in CANONICAL_TOOL_RESOLVER:
                fallback_tools.extend(CANONICAL_TOOL_RESOLVER[model])
        
        # Convert string execution_mode and risk_level to enums
        execution_mode_str = params.get('execution_mode', 'STANDARD_REASONING')
        risk_level_str = params.get('risk_level', 'LOW')
        
        execution_mode = getattr(ExecutionMode, execution_mode_str, ExecutionMode.STANDARD_REASONING)
        risk_level = getattr(RiskLevel, risk_level_str, RiskLevel.LOW)
        
        # Get freshness from capability
        freshness = getattr(capability, 'freshness_requirement', Freshness.STATIC)
        
        return ToolStrategy(
            capability_id=capability.capability_id,
            primary_tools=tuple(primary_tools),
            fallback_tools=tuple(fallback_tools),
            execution_mode=execution_mode,
            risk_level=risk_level,
            requires_confirmation=params.get('requires_confirmation', False),
            verification_required=params.get('verification_required', True),
            timeout_ms=params.get('timeout_ms', 30000),
            retry_policy=params.get('retry_policy', {'max_attempts': 2, 'backoff_ms': 500}),
            freshness_requirement=freshness,
        )
    
    def resolve(
        self,
        domain: "Domain",
        intent: "Intent",
        output_type: "OutputType",
        signals: "TaskSignals",
    ) -> CapabilityResolution:
        """Complete capability resolution: select → validate → build strategy.
        
        This is the main entry point for Phase 5 capability routing.
        """
        # Step 1: Select capability
        candidate = self.select_capability(domain, intent, output_type, signals)
        capability = candidate.capability
        
        # Step 2: Validate tools
        resolved_tools, missing_tools = self.validate_capability_tools(capability)
        
        # Step 3: Build tool strategy
        tool_strategy = self.build_tool_strategy(capability, intent, output_type, signals)
        
        # Step 4: Collect warnings
        warnings: List[str] = []
        if missing_tools:
            warnings.append(f"Capability {capability.capability_id} has unresolved tools: {missing_tools}")
        if not resolved_tools and capability.required_tools:
            warnings.append(f"Capability {capability.capability_id} requires tools but none resolved")
        if candidate.confidence < 0.5:
            warnings.append(f"Low capability confidence: {candidate.confidence:.2f}")
        
        return CapabilityResolution(
            capability=capability,
            candidate=candidate,
            tool_strategy=tool_strategy,
            resolved_tools=tuple(resolved_tools),
            missing_tools=tuple(missing_tools),
            warnings=tuple(warnings),
        )
    
    def get_capability_chain(
        self,
        goals: List[Any],  # ClauseGoal list
    ) -> List[CapabilityResolution]:
        """Resolve a chain of capabilities for multi-intent requests."""
        from .ai_manager import OutputType
        
        resolutions: List[CapabilityResolution] = []
        
        for goal in goals:
            if goal.intent and goal.domain and goal.capability:
                # We have a pre-selected capability from decomposition
                capability = self._registry.get(goal.capability)
                if capability:
                    # Build a minimal signals object for this goal
                    signals = self._ai_manager._extract_task_signals(goal.text)
                    resolution = self.resolve(
                        goal.domain,
                        goal.intent,
                        goal.output_type or OutputType.SYSTEM_ACTION,
                        signals,
                    )
                    resolutions.append(resolution)
        
        return resolutions


# Backward compatibility: expose the resolver from AIManager
def get_capability_resolver(ai_manager: "AIManager") -> CapabilityResolver:
    """Get or create the capability resolver for an AIManager."""
    return CapabilityResolver(ai_manager)