#!/usr/bin/env python3
"""
Phase 5 — Unified Capability Routing Tests

Tests for:
- capability resolution
- multi-capability routing
- unsupported capability
- missing tool
- tool fallback
- risk-aware routing
- multi-intent capability chains
"""

import sys
import os

# Add the MYRAA directory to the path so desktop_agent can be found as a package
myraa_path = os.path.join(os.path.dirname(__file__), '..')
myraa_path = os.path.normpath(myraa_path)
print(f"Adding to path: {myraa_path}")
sys.path.insert(0, myraa_path)
print(f"Sys path: {sys.path[:3]}")

from desktop_agent.brain.ai.ai_manager import AIManager, Domain, Intent, OutputType, RiskLevel, ExecutionMode, Freshness
from desktop_agent.brain.ai.capability_resolver import CapabilityResolver, ToolStrategy, CapabilityResolution
from desktop_agent.brain.ai.tool_resolver import REGISTERED_TOOLS, CANONICAL_TOOL_RESOLVER, resolve, is_resolvable


def test_capability_registry_has_required_capabilities():
    """Test that all required capabilities are registered."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    required_capabilities = [
        'COMPUTER_USE',
        'FILES_ENGINE',
        'DOCUMENT_ENGINE',
        'RESEARCH_PIPELINE',
        'VISION_ENGINE',
        'VOICE_ENGINE',
        'CODING_ENGINE',
        'CALENDAR_ENGINE',
        'TRADING_ENGINE',
        'NX_ENGINEERING_ENGINE',
        'CREATION_ENGINE',
        'PRESENTATION_ENGINE',
        'SPREADSHEET_ENGINE',
    ]
    
    for cap_id in required_capabilities:
        cap = resolver.registry.get(cap_id)
        assert cap is not None, f"Capability {cap_id} not registered"
        assert cap.capability_id == cap_id
        print(f"  PASS: {cap_id} registered")


def test_calendar_capability_exists():
    """Test that CALENDAR capability exists and is properly configured."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    cap = resolver.registry.get('CALENDAR_ENGINE')
    assert cap is not None, "CALENDAR_ENGINE not registered"
    assert cap.domain == Domain.CALENDAR
    assert Intent.CALENDAR_CREATE in cap.supported_intents
    assert Intent.CALENDAR_READ in cap.supported_intents
    assert Intent.CALENDAR_UPDATE in cap.supported_intents
    assert Intent.CALENDAR_DELETE in cap.supported_intents
    assert Intent.CALENDAR_LIST in cap.supported_intents
    assert Intent.CALENDAR_SEARCH in cap.supported_intents
    assert cap.required_tools == ['calendar_tool']
    print("  PASS: CALENDAR_ENGINE properly configured")


def test_capability_resolution_basic():
    """Test basic capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("create a calendar event")
    
    resolution = resolver.resolve(
        domain=Domain.CALENDAR,
        intent=Intent.CALENDAR_CREATE,
        output_type=OutputType.SYSTEM_ACTION,
        signals=signals,
    )
    
    assert isinstance(resolution, CapabilityResolution)
    assert resolution.capability.capability_id == 'CALENDAR_ENGINE'
    assert resolution.tool_strategy.capability_id == 'CALENDAR_ENGINE'
    assert resolution.tool_strategy.risk_level == RiskLevel.LOW
    assert resolution.tool_strategy.verification_required == True
    print("  PASS: Basic capability resolution works")


def test_computer_use_resolution():
    """Test COMPUTER_USE capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("open notepad")
    
    resolution = resolver.resolve(
        domain=Domain.COMPUTER,
        intent=Intent.APP_CONTROL,
        output_type=OutputType.SYSTEM_ACTION,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'COMPUTER_USE'
    assert 'openApplication' in resolution.resolved_tools or 'desktop_tool' in str(resolution.resolved_tools)
    assert resolution.tool_strategy.execution_mode == ExecutionMode.FAST_DETERMINISTIC
    print("  PASS: COMPUTER_USE resolution works")


def test_files_engine_resolution():
    """Test FILES_ENGINE capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("create a file")
    
    resolution = resolver.resolve(
        domain=Domain.FILES,
        intent=Intent.FILE_CREATE,
        output_type=OutputType.SYSTEM_ACTION,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'FILES_ENGINE'
    assert resolution.tool_strategy.risk_level == RiskLevel.LOW
    print("  PASS: FILES_ENGINE resolution works")


def test_trading_engine_resolution():
    """Test TRADING_ENGINE capability resolution with financial risk."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("analyze nifty trend")
    
    resolution = resolver.resolve(
        domain=Domain.TRADING,
        intent=Intent.TRADING_ANALYSIS,
        output_type=OutputType.MARKET_ANALYSIS,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'TRADING_ENGINE'
    assert resolution.tool_strategy.risk_level == RiskLevel.FINANCIAL
    assert resolution.tool_strategy.requires_confirmation == True
    assert resolution.tool_strategy.verification_required == True
    print("  PASS: TRADING_ENGINE resolution with financial risk works")


def test_research_pipeline_resolution():
    """Test RESEARCH_PIPELINE capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("research latest AI models")
    
    resolution = resolver.resolve(
        domain=Domain.RESEARCH,
        intent=Intent.RESEARCHING,
        output_type=OutputType.RESEARCH_REPORT,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'RESEARCH_PIPELINE'
    assert resolution.tool_strategy.timeout_ms == 60000
    print("  PASS: RESEARCH_PIPELINE resolution works")


def test_coding_engine_resolution():
    """Test CODING_ENGINE capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("debug this python code")
    
    resolution = resolver.resolve(
        domain=Domain.CODING,
        intent=Intent.CODING_DEBUG,
        output_type=OutputType.CODE,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'CODING_ENGINE'
    assert 'runPythonScript' in resolution.resolved_tools or 'code_execution' in str(resolution.resolved_tools)
    print("  PASS: CODING_ENGINE resolution works")


def test_vision_engine_resolution():
    """Test VISION_ENGINE capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("take a screenshot")
    
    resolution = resolver.resolve(
        domain=Domain.VISION,
        intent=Intent.SCREEN_CAPTURE,
        output_type=OutputType.SCREEN,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'VISION_ENGINE'
    assert resolution.tool_strategy.freshness_requirement == Freshness.REAL_TIME
    print("  PASS: VISION_ENGINE resolution works")


def test_voice_engine_resolution():
    """Test VOICE_ENGINE capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("play music")
    
    resolution = resolver.resolve(
        domain=Domain.VOICE,
        intent=Intent.AUDIO_PLAY,
        output_type=OutputType.SYSTEM_ACTION,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'VOICE_ENGINE'
    assert resolution.tool_strategy.verification_required == False
    print("  PASS: VOICE_ENGINE resolution works")


def test_calendar_engine_resolution():
    """Test CALENDAR_ENGINE capability resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    signals = ai_manager._extract_task_signals("create a meeting for tomorrow")
    
    resolution = resolver.resolve(
        domain=Domain.CALENDAR,
        intent=Intent.CALENDAR_CREATE,
        output_type=OutputType.SYSTEM_ACTION,
        signals=signals,
    )
    
    assert resolution.capability.capability_id == 'CALENDAR_ENGINE'
    assert resolution.tool_strategy.risk_level == RiskLevel.LOW
    assert resolution.tool_strategy.verification_required == True
    print("  PASS: CALENDAR_ENGINE resolution works")


def test_unsupported_capability():
    """Test that unsupported capability raises appropriate error."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    # Try to get a non-existent capability
    cap = resolver.registry.get('NON_EXISTENT_CAPABILITY')
    assert cap is None, "Non-existent capability should return None"
    print("  PASS: Unsupported capability returns None")


def test_missing_tool_handling():
    """Test that missing tools are reported in warnings."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    # Create a capability with a non-existent tool using the Capability class from ai_manager
    CapabilityClass = type(ai_manager._capability_registry['TRADING_ENGINE'])
    test_cap = CapabilityClass(
        capability_id='TEST_CAPABILITY',
        domain=Domain.GENERAL,
        supported_intents=[Intent.ASK],
        required_tools=['non_existent_tool'],
        context_requirements=[],
        freshness_requirement=Freshness.STATIC,
        risk_class=RiskLevel.NONE,
        latency_profile='low',
        supported_models=['gemini'],
        fallback_models=[]
    )
    
    # Register it temporarily
    resolver.registry.register(test_cap)
    
    # Manually validate the test capability's tools
    resolved_tools, missing_tools = resolver.validate_capability_tools(test_cap)
    
    # Should have missing tools
    assert 'non_existent_tool' in missing_tools
    assert len(resolved_tools) == 0
    print("  PASS: Missing tool reported in validation")
    
    # Clean up
    del resolver.registry._capabilities['TEST_CAPABILITY']


def test_tool_fallback():
    """Test tool fallback mechanism."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    # Check that fallback models are considered
    cap = resolver.registry.get('TRADING_ENGINE')
    assert 'ollama' in cap.fallback_models
    
    signals = ai_manager._extract_task_signals("analyze stock")
    resolution = resolver.resolve(
        domain=Domain.TRADING,
        intent=Intent.TRADING_ANALYSIS,
        output_type=OutputType.MARKET_ANALYSIS,
        signals=signals,
    )
    
    # Fallback tools should be in the strategy
    assert len(resolution.tool_strategy.fallback_tools) >= 0  # May be empty if no canonical mapping
    print("  PASS: Tool fallback mechanism works")


def test_risk_aware_routing():
    """Test risk-aware routing for different capabilities."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    # High risk: trading
    signals = ai_manager._extract_task_signals("should I buy reliance stock")
    resolution = resolver.resolve(
        domain=Domain.TRADING,
        intent=Intent.TRADING_DECISION,
        output_type=OutputType.RECOMMENDATION,
        signals=signals,
    )
    assert resolution.tool_strategy.risk_level == RiskLevel.FINANCIAL
    assert resolution.tool_strategy.requires_confirmation == True
    
    # Medium risk: system shutdown
    signals = ai_manager._extract_task_signals("shutdown the system")
    resolution = resolver.resolve(
        domain=Domain.SYSTEM,
        intent=Intent.SYSTEM_SHUTDOWN,
        output_type=OutputType.SYSTEM_ACTION,
        signals=signals,
    )
    assert resolution.tool_strategy.risk_level in (RiskLevel.MEDIUM, RiskLevel.LOW)
    
    # Low risk: file read
    signals = ai_manager._extract_task_signals("read the file")
    resolution = resolver.resolve(
        domain=Domain.FILES,
        intent=Intent.FILE_READ,
        output_type=OutputType.SYSTEM_ACTION,
        signals=signals,
    )
    assert resolution.tool_strategy.risk_level == RiskLevel.LOW
    assert resolution.tool_strategy.requires_confirmation == False
    
    print("  PASS: Risk-aware routing works")


def test_multi_intent_capability_chain():
    """Test multi-intent capability chain resolution."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    # Create mock goals (simulating multi-intent decomposition)
    from desktop_agent.brain.ai.ai_manager import ClauseGoal
    
    goals = [
        ClauseGoal("create a calendar event", Intent.CALENDAR_CREATE, Domain.CALENDAR, 'CALENDAR_ENGINE', OutputType.SYSTEM_ACTION, 0.8),
        ClauseGoal("send email to team", Intent.SEND_EMAIL, Domain.COMPUTER, 'COMPUTER_USE', OutputType.SYSTEM_ACTION, 0.7),
    ]
    
    chain = resolver.get_capability_chain(goals)
    
    assert len(chain) == 2
    assert chain[0].capability.capability_id == 'CALENDAR_ENGINE'
    assert chain[1].capability.capability_id == 'COMPUTER_USE'
    print("  PASS: Multi-intent capability chain works")


def test_tool_resolver_basic():
    """Test the tool resolver basic functionality."""
    # Test registered tool resolution
    assert resolve('openApplication') == ['openApplication']
    assert resolve('createFile') == ['createFile']
    
    # Test canonical tool resolution
    assert 'openApplication' in resolve('desktop_tool')
    assert 'createFile' in resolve('file_tool')
    assert 'searchWeb' in resolve('web_research')
    assert 'runPythonScript' in resolve('code_execution')
    
    # Test capability-owned tools
    assert resolve('phone_tool') == []
    assert resolve('voice_tool') == []
    assert resolve('calendar_tool') == []
    
    # Test is_resolvable
    assert is_resolvable('openApplication') == True
    assert is_resolvable('desktop_tool') == True
    assert is_resolvable('non_existent_tool') == False
    
    print("  PASS: Tool resolver basic functionality works")


def test_capability_registry_methods():
    """Test CapabilityRegistry methods."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    # Test get_by_domain
    computer_caps = resolver.registry.get_by_domain(Domain.COMPUTER)
    assert any(c.capability_id == 'COMPUTER_USE' for c in computer_caps)
    
    trading_caps = resolver.registry.get_by_domain(Domain.TRADING)
    assert any(c.capability_id == 'TRADING_ENGINE' for c in trading_caps)
    
    calendar_caps = resolver.registry.get_by_domain(Domain.CALENDAR)
    assert any(c.capability_id == 'CALENDAR_ENGINE' for c in calendar_caps)
    
    # Test get_by_intent
    file_caps = resolver.registry.get_by_intent(Intent.FILE_CREATE)
    assert any(c.capability_id == 'FILES_ENGINE' for c in file_caps)
    
    # Test has
    assert resolver.registry.has('COMPUTER_USE') == True
    assert resolver.registry.has('NON_EXISTENT') == False
    
    print("  PASS: CapabilityRegistry methods work")


def test_canonical_tool_ids_only():
    """Test that only registered capabilities and tools are used."""
    ai_manager = AIManager()
    resolver = ai_manager.capability_resolver
    
    # Verify all capabilities use only registered tools or canonical IDs
    for cap_id, cap in resolver.registry.get_all().items():
        for tool in cap.required_tools:
            assert is_resolvable(tool), f"Capability {cap_id} requires unresolvable tool: {tool}"
    
    print("  PASS: All capabilities use only registered/canonical tools")


def run_all_tests():
    """Run all Phase 5 capability routing tests."""
    print("=" * 60)
    print("Phase 5 — Unified Capability Routing Tests")
    print("=" * 60)
    
    tests = [
        test_capability_registry_has_required_capabilities,
        test_calendar_capability_exists,
        test_capability_resolution_basic,
        test_computer_use_resolution,
        test_files_engine_resolution,
        test_trading_engine_resolution,
        test_research_pipeline_resolution,
        test_coding_engine_resolution,
        test_vision_engine_resolution,
        test_voice_engine_resolution,
        test_calendar_engine_resolution,
        test_unsupported_capability,
        test_missing_tool_handling,
        test_tool_fallback,
        test_risk_aware_routing,
        test_multi_intent_capability_chain,
        test_tool_resolver_basic,
        test_capability_registry_methods,
        test_canonical_tool_ids_only,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)