# EPIC-14G: WORLD-CLASS PERFORMANCE & LATENCY OPTIMIZATION

## Mission
Optimize the entire MYRAA runtime for:
- Low latency
- High responsiveness  
- High throughput
- Smooth UI
- Efficient CPU/RAM/GPU/network usage
- Faster model responses/tool execution/voice interaction/screen perception/verification

While preserving:
- Correctness
- Target accuracy
- Verification quality
- Safety
- PermissionManager enforcement
- EPIC-10C confirmation
- MYRAA_TEST_MODE protection
- Browser continuity
- Existing functionality

Target Principle: FASTEST SAFE MYRAA

## Current Baseline Measurements (from audit)

### Latency Benchmarks (from test_benchmark_suite.py)
- Static Desktop Baseline: 183.46 ms
- Active Browser Interactions: 18.00 ms  
- YouTube Search End-to-End: 125.00 ms
- Notepad Text Input: 63.00 ms
- Dynamic UI Elements: 55.00 ms
- Moving Target Tracking: 49.00 ms
- Web Navigation: 165.00 ms
- Target Disappearance Recovery: 73.00 ms
- OCR Degradation Handling: 60.00 ms
- Browser Disconnect Recovery: 80.00 ms

### System Resource Usage (from simple_performance_audit.py)
- CPU: 27.2% average (max: 72.7%)
- Memory: 11,280 MB average (max: 11,314 MB)

### Microbenchmarks
- File operations: 9.19 ms
- Process spawning: 28.57 ms
- Safe module imports: 120.50 ms
- Tool registry access: 1.96 ms
- Configuration access: negligible

## Implementation Plan

### Phase 1: Performance Audit & Baseline Establishment
✓ Completed
- Created performance audit scripts
- Ran baseline benchmarks
- Established current performance metrics
- Identified obvious bottlenecks (module import times, full system initialization)

### Phase 2: End-to-End Latency Tracing & Fast Path Implementation
- [ ] Implement structured latency tracing throughout the pipeline
- [ ] Create canonical latency trace format: task_id, step_id, stage, start, end, duration
- [ ] Instrument key pipeline stages:
  - Voice pipeline (STT, Brain routing, model provider, TTS)
  - Computer-use pipeline (observation → target resolution → validation → action → verification)
- [ ] Implement fast path for trivial commands:
  - Hello/yes/no confirmations
  - Current time queries
  - Simple app launch/navigation
  - State queries
  - Stop/cancel/pause/resume commands
- [ ] Ensure fast path bypasses heavy model invocation when appropriate

### Phase 3: Model Routing & Context Optimization
- [ ] Optimize AIManager routing strategy:
  - SIMPLE → fastest appropriate model (local/fastest available)
  - MEDIUM → standard model (Gemini/Ollama baseline)
  - COMPLEX → NVIDIA Nemotron
  - DEEP PLANNING → Nemotron + reasoning enabled
  - OFFLINE/PRIVATE → local model
- [ ] Implement efficient context assembly policy with priority:
  1. Current user request
  2. Current task state
  3. Relevant recent conversation
  4. Relevant ScreenState summary
  5. Required tool results
  6. Relevant memory
  7. Older context only when necessary
- [ ] Implement bounded context budgets and caching
- [ ] Optimize Nemotron usage with selective reasoning:
  - Simple tasks → reasoning OFF
  - Complex tasks → reasoning ON (when necessary for correctness)

### Phase 4: Screen Vision & Perception Optimization
- [ ] Enhance EPIC-14A/14B vision pipeline:
  - Latest-frame-wins optimization
  - Frame differencing with adaptive FPS
  - Region-based processing for small changes
  - Avoid unnecessary OCR/full-frame analysis
  - Prevent repeated ScreenState rebuilds/target resolution
- [ ] Implement event-driven vision processing:
  - Window change events → update context
  - Large visual change events → process
  - User task initiation → increase perception priority
  - Stable screen → reduce processing work
- [ ] Maintain vision quality while improving FPS

### Phase 5: Priority-Aware Processing & Parallelization
- [ ] Implement priority classes:
  - CRITICAL: active computer-use verification
  - HIGH: current user command
  - NORMAL: background screen analysis
  - LOW: non-critical housekeeping
- [ ] Ensure background work doesn't block user-facing work
- [ ] Parallelize independent work (research from multiple sources)
- [ ] Maintain serialization where ordering matters (mouse click + keyboard type)
- [ ] Audit and convert blocking I/O to async where appropriate:
  - Network/WebSocket calls
  - Model API calls
  - External APIs
  - File operations
  - Browser communication
- [ ] Use thread/process pools for genuinely blocking workloads

### Phase 6: UI & Rendering Performance
- [ ] Optimize UI for 4K visual quality at 120 FPS target:
  - GPU-accelerated rendering for MYRAA HUD
  - Avoid unnecessary DOM/layout thrashing
  - Cache static geometry and textures
  - Minimize redraw regions
  - Use efficient animation loops
- [ ] Optimize Earth/HUD animation:
  - Stable render loop with delta-time animation
  - Low-cost procedural effects
  - Cached meshes/textures
  - Independent HUD layer animation
  - Smooth Earth rotation during AI generation/thinking
- [ ] Separate UI rendering from Brain/Vision/Voice/Tools processing
- [ ] Ensure UI remains responsive during heavy AI/vision work

### Phase 7: Memory & Cache Optimization
- [ ] Audit and bound major memory consumers:
  - ScreenState history
  - Frame buffers
  - OCR data
  - Target history
  - Verification evidence
  - Action history
  - Logs
  - Model contexts
  - Browser handles
  - WebSocket buffers
  - Caches
- [ ] Implement bounded sizes with retention policies and cleanup strategies
- [ ] Create safe caching architecture:
  - Model metadata
  - Stable semantic mappings
  - Static application context
  - Repeated research data (with TTL)
  - Target synonyms
  - Configuration
  - Expensive deterministic computations
- [ ] Ensure all caches have TTL or explicit invalidation
- [ ] Never cache real-time information without proper freshness handling

### Phase 8: Tool, Browser & Voice Performance
- [ ] Optimize tool execution:
  - Measure each tool's performance
  - Avoid redundant/duplicate tool calls
  - Avoid duplicate screenshots/browser inspections
  - Avoid repeated target resolution/filesystem reads/model calls
  - Validate cached results before reuse
- [ ] Optimize browser performance (preserving visible-browser continuity):
  - Browser inspection and target resolution
  - DOM lookup where supported
  - Screenshot frequency optimization
  - State synchronization improvements
  - Never launch hidden browser sessions
- [ ] Optimize voice performance for real-time feel:
  - STT endpoint detection optimization
  - Model first-token latency reduction
  - TTS first-audio latency improvement
  - Streaming TTS with sentence-aware chunking
  - Maintain VAD, barge-in, interruption, echo protection, Hinglish behavior
- [ ] Implement sentence-aware TTS buffering (complete meaningful sentence → TTS)

### Phase 9: System-Level Optimizations
- [ ] Optimize WebSocket/IPC performance:
  - Audit message size, serialization, deserialization
  - Avoid duplicate messages and buffering issues
  - Optimize reconnect behavior and heartbeat
  - Transmit small state updates instead of large payloads when possible
- [ ] Optimize file/project performance for large projects:
  - Use indexing and incremental updates
  - File hashes and timestamps
  - Dependency graphs and cached metadata
  - Only reprocess changed files
- [ ] Optimize research performance:
  - Parallelize independent source retrieval
  - Deduplicate → rank sources → synthesize
  - Maintain source reliability and citations
  - Never trade source quality for speed
- [ ] Prepare for trading performance (EPIC-17):
  - Incremental market updates
  - Candle-close triggers
  - Event-driven price thresholds
  - Lightweight monitoring with deep analysis only on meaningful changes

### Phase 10: Resource Management & Governance
- [ ] Implement resource budgets where appropriate:
  - CPU budget
  - Memory budget
  - Queue budget
  - Concurrent task budget
  - Network request budget
  - Model request budget
- [ ] Implement graceful degradation when resources constrained:
  - Reduce background work rather than freezing MYRAA
- [ ] Implement load shedding strategy when overloaded:
  1. Preserve active user task
  2. Preserve safety/verification
  3. Preserve voice responsiveness
  4. Reduce background vision
  5. Reduce low-priority research
  6. Pause optional maintenance
  7. Never shed safety checks, permissions, or final verification
- [ ] Implement response deduplication using EPIC-14E idempotency mechanisms
- [ ] Ensure failure recovery remains bounded and safe:
  - Don't disable recovery or reduce verification below safe levels
  - Don't reuse stale targets or bypass confirmation
  - Performance from better scheduling/caching/context/routing/observation

### Phase 11: Performance Infrastructure
- [ ] Create performance regression guard with real baseline measurements:
  - Track median latency, p95 latency, p99 latency
  - Track first-token latency, first-audio latency
  - Track action latency, verification latency
  - Track memory peak, CPU usage, queue depth
  - Detect regressions automatically
- [ ] Create comprehensive benchmark suite for EPIC-14G:
  1. Simple voice command
  2. Complex Nemotron reasoning
  3. Streaming response
  4. Voice interruption
  5. Screen perception
  6. Target resolution
  7. Safe click
  8. Multi-step browser task
  9. Verification/recovery
  10. Research task
  11. Large project analysis
  12. NIFTY monitoring simulation
  13. UI rendering
  14. Start/stop cycle
  15. Long-running session
  16. Measure: latency, throughput, CPU, RAM, queue depth, success rate
- [ ] Implement soak/stress testing for long-duration stability:
  - Measure RAM growth, CPU stability, thread count, queue growth
  - Monitor connection stability, browser stability, UI responsiveness
  - Track model failures and recovery events
  - Avoid destructive power actions
- [ ] Optimize startup performance:
  - Measure: PC launch → UI ready → voice ready → vision ready → Brain ready
  - Initialize heavy resources lazily when possible
  - Implement lazy loading for non-immediate subsystems
  - Avoid excessive dynamic import delays
- [ ] Implement model warming and connection reuse:
  - Maintain lightweight provider readiness
  - Reuse HTTP sessions/connections and client instances
  - Avoid unnecessary authentication handshakes
  - Don't keep excessive resources alive unnecessarily
- [ ] Optimize serialization:
  - Audit JSON/state serialization
  - Avoid repeatedly serializing huge ScreenState/memory/tool results
  - Use compact summaries when possible
- [ ] Create performance observability dashboard:
  - Expose metrics through existing MYRAA observability architecture
  - Minimum metrics: latency by stage, provider latency, first-token/audio latency
  - Action/verification latency, CPU, RAM, queue depth, active tasks
  - Dropped frames, cache hit rate, fallback count
  - Never expose secrets
- [ ] Implement performance-aware logging:
  - Use appropriate log levels (ERROR/WARN/INFO/DEBUG/TRACE)
  - Production default: INFO/WARN/ERROR
  - Avoid logging every frame/token/internal event at INFO level

### Phase 12: Validation & Testing
- [ ] Create comprehensive test suite for performance optimizations:
  - Router performance behavior tests
  - Context trimming and cache invalidation tests
  - Queue prioritization and backpressure tests
  - Response deduplication tests
  - Resource budget and timeout behavior tests
  - Cancellation, concurrency, and streaming tests
  - TTS chunking and performance metrics tests
- [ ] Integration tests:
  - Brain → NIM → tool pipeline
  - Voice → Brain → NIM → TTS pipeline
  - Screen → perception → target pipeline
  - Target → action → verification pipeline
  - Browser and research workflows
  - Long session and fallback tests
- [ ] UI performance validation:
  - Validate 4K rendering and smooth 120 FPS target
  - Verify central Earth rotates slowly
  - Ensure HUD remains smooth during AI generation, screen perception, browser activity
  - Measure actual FPS and ensure no excessive GPU/CPU usage or memory growth from animation
- [ ] Real API performance test (using actual NVIDIA API key in controlled env):
  - Measure first token, total response, streaming
  - Test reasoning ON vs OFF
  - Measure fallback behavior
  - Separate mocked unit performance from real-provider performance
- [ ] Before/after comparison documentation:
  - Report median latency change, p95 change, first-token change
  - Voice perceived latency change, tool latency change
  - CPU change, RAM change, frame processing change, UI FPS change
  - Cache hit-rate change and other relevant metrics
- [ ] Long-running soak test completion
- [ ] Verify no material memory leaks
- [ ] Ensure no unacceptable UI degradation
- [ ] Verify no regressions in EPIC-11 through EPIC-14F
- [ ] Ensure TypeScript passes, build passes, Python tests pass

## Success Criteria (Definition of Done)

EPIC-14G is COMPLETE only when:

✓ Full latency audit completed and documented
✓ CPU/RAM/GPU/network bottlenecks measured and addressed
✓ End-to-end latency traces implemented throughout pipeline
✓ Fast path implemented for trivial commands with measurements
✓ Model routing optimized with measurable improvements
✓ Nemotron latency measured and optimized (first-token, streaming)
✓ Context budgeting optimized with demonstrated efficiency gains
✓ Screen vision optimized without unsafe quality loss (measure FPS vs accuracy)
✓ Event-driven processing implemented and measured
✓ Priority scheduling implemented where justified with measurements
✓ Safe parallelization added for independent work
✓ Blocking operations audited and converted to async where appropriate
✓ UI rendering optimized with measured FPS improvements
✓ 4K/120 FPS target benchmarked and validated
✓ Earth animation remains smooth during heavy processing
✓ Memory usage optimized with bounded collections and cleanup
✓ Safe caching implemented with measurable hit-rate improvement
✓ Tool calls deduplicated with measurable reduction in redundant execution
✓ Browser performance improved with measurable latency reduction
✓ Voice first-audio latency improved with measurable measurements
✓ TTS chunking optimized with natural prosody maintained
✓ WebSocket/IPC overhead measured and reduced
✓ Large project processing optimized with incremental improvements
✓ Research parallelism optimized with maintained source quality
✓ NIFTY monitoring prepared for efficient implementation
✓ Resource budgets enforced where justified with graceful degradation
✓ Load shedding implemented where justified with preservation of critical functions
✓ Startup performance measured and optimized
✓ Lazy loading applied where beneficial with measured improvements
✓ Provider connections reused where safe with measured benefits
✓ Serialization overhead reduced with measurable improvements
✓ Performance metrics available through observability dashboard
✓ Logging overhead controlled without losing diagnostic capability
✓ Security boundaries preserved (PermissionManager, confirmation, etc.)
✓ All unit tests pass
✓ All integration tests pass
✓ Real NIM benchmark captured and documented
✓ Before/after benchmarks completed and documented
✓ Long-running soak test completed with stability measurements
✓ No material memory leaks detected
✓ No unacceptable UI degradation observed
✓ No regression in EPIC-11 through EPIC-14F functionality
✓ TypeScript passes (npm run lint)
✓ Build passes (npm run build)
✓ Python tests pass (pytest)

## Deliverables

1. Performance audit report with baseline measurements
2. Files modified for optimization (to be tracked during implementation)
3. Fast-path implementation details
4. Model-routing changes and measurements
5. Nemotron benchmark results (first-token, streaming, reasoning impact)
6. Context optimization details and measurements
7. Screen vision optimization details (FPS, quality tradeoffs)
8. Voice optimization details (latency measurements)
9. UI/FPS results and validation
10. CPU/RAM/GPU findings and improvements
11. Cache and backpressure changes with measurements
12. Startup performance measurements
13. Concurrency changes with measurements
14. Before/after latency table with all benchmark scenarios
15. Soak-test results with stability measurements
16. Regression test results confirming no EPIC-11 through EPIC-14F regressions
17. Security confirmation that all boundaries preserved
18. Remaining bottlenecks and recommended future optimizations
19. Complete documentation of performance architecture

## Notes

- STOP AFTER EPIC-14G. DO NOT START EPIC-15.
- All optimization must preserve correctness and safety - FASTEST SAFE MYRAA, not FASTEST POSSIBLE MYRAA
- Performance must come from better scheduling, caching, context, routing, observation - never from reducing safety or quality
- When in doubt, measure rather than assume
- Document all changes with clear before/after measurements