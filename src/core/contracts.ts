// ============================================================================
// MYRAA Unified Request Context — Canonical Contracts for Phase 29.6
// ============================================================================

import type { PlanTask, TaskResult } from '../agent/contracts';

// ── Request Context ─────────────────────────────────────────────────────────

export type InputType = 'voice' | 'text' | 'image' | 'screen';

export type RequestClassification =
  | 'CONVERSATION'
  | 'VISION'
  | 'COMPUTER_ACTION'
  | 'FILE_OPERATION'
  | 'RESEARCH'
  | 'FINANCE'
  | 'QUANT'
  | 'AGENT_TASK'
  | 'SYSTEM'
  | 'UNKNOWN';

export interface MyraaRequestContext {
  readonly requestId: string;
  readonly traceId: string;
  readonly sessionId?: string;
  readonly conversationId?: string;
  readonly input: string;
  readonly inputType: InputType;
  readonly classification: RequestClassification;
  readonly conversation: readonly ConversationTurn[];
  readonly memory?: MemoryContext;
  readonly world?: WorldContext;
  readonly vision?: VisionContext;
  readonly tools?: ToolContext;
  readonly evidence?: EvidenceContext;
  readonly policy?: PolicyContext;
  readonly learning?: LearningSignals;
  readonly timestamps: RequestTimestamps;
}

export interface ConversationTurn {
  readonly role: 'user' | 'assistant' | 'system';
  readonly content: string;
  readonly timestamp?: string;
}

export interface MemoryContext {
  readonly relevantMemories: readonly MemoryEntry[];
  readonly memoryContext?: string;
}

export interface MemoryEntry {
  readonly id: string;
  readonly category: string;
  readonly content: string;
  readonly importance: number;
  readonly recency: number;
}

export interface WorldContext {
  readonly entities?: readonly unknown[];
  readonly facts?: readonly unknown[];
  readonly freshness?: string;
}

export interface VisionContext {
  readonly available: boolean;
  readonly sceneDescription?: string;
  readonly elements?: readonly unknown[];
  readonly ocrText?: string;
  readonly captureTimestamp?: string;
}

export interface ToolContext {
  readonly availableTools: readonly string[];
  readonly toolMetadata?: Record<string, ToolMetadata>;
}

export interface ToolMetadata {
  readonly name: string;
  readonly capability: string;
  readonly dangerLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  readonly requiresConfirmation: boolean;
  readonly timeout: number;
}

export interface EvidenceContext {
  readonly sources: readonly EvidenceSource[];
  readonly confidence: number;
  readonly contradictions: readonly string[];
}

export interface EvidenceSource {
  readonly source: string;
  readonly freshness: string;
  readonly confidence: number;
  readonly provenance: string;
}

export interface PolicyContext {
  readonly financialFirewallActive: boolean;
  readonly autonomyLevel: string;
  readonly blockedActions: readonly string[];
}

export interface LearningSignals {
  readonly providerQuality?: Record<string, number>;
  readonly strategyHealth?: Record<string, string>;
  readonly recentFailures?: readonly string[];
}

export interface RequestTimestamps {
  readonly received: string;
  readonly normalized?: string;
  readonly routed?: string;
  readonly contextAssembled?: string;
  readonly executionStarted?: string;
  readonly executionCompleted?: string;
  readonly verified?: string;
  readonly responded?: string;
}

// ── Execution Bridge Contract ───────────────────────────────────────────────

export interface ExecutionRequest {
  readonly requestId: string;
  readonly taskId: string;
  readonly actionId: string;
  readonly capability: string;
  readonly tool: string;
  readonly arguments: Record<string, unknown>;
  readonly policyContext?: PolicyContext;
  readonly expectedOutcome?: string;
  readonly timeout?: number;
  readonly idempotencyKey?: string;
}

export interface ExecutionResult {
  readonly requestId: string;
  readonly taskId: string;
  readonly actionId: string;
  readonly success: boolean;
  readonly status: string;
  readonly result?: unknown;
  readonly error?: string;
  readonly observation?: string;
  readonly verificationHint?: string;
  readonly duration: number;
}

// ── Health ──────────────────────────────────────────────────────────────────

export type SubsystemStatus = 'UP' | 'DEGRADED' | 'DOWN' | 'UNAVAILABLE';

export interface SubsystemHealth {
  readonly status: SubsystemStatus;
  readonly message?: string;
  readonly lastCheck?: string;
  readonly latencyMs?: number;
}

export interface SystemHealth {
  readonly server: SubsystemHealth;
  readonly pythonAgent: SubsystemHealth;
  readonly brain: SubsystemHealth;
  readonly memory: SubsystemHealth;
  readonly world: SubsystemHealth;
  readonly vision: SubsystemHealth;
  readonly computer: SubsystemHealth;
  readonly finance: SubsystemHealth;
  readonly quant: SubsystemHealth;
  readonly learning: SubsystemHealth;
  readonly voice: SubsystemHealth;
  readonly providers: SubsystemHealth;
  readonly bridge: SubsystemHealth;
}

// ── Model Decision ──────────────────────────────────────────────────────────

export interface ModelDecision {
  readonly model: string;
  readonly provider: string;
  readonly reason: string;
  readonly latencyBudget: number;
  readonly contextBudget: number;
  readonly modality: 'text' | 'vision' | 'audio';
  readonly fallback?: string;
  readonly temperature?: number;
  readonly maxTokens?: number;
}

// ── Learning Signal ─────────────────────────────────────────────────────────

export interface LearningSignal {
  readonly source: string;
  readonly capability: string;
  readonly provider: string;
  readonly strategy?: string;
  readonly confidence: number;
  readonly evidence: string;
  readonly recommendation: string;
  readonly expiresAt: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

export function generateRequestId(): string {
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function generateTraceId(): string {
  return `trace-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function generateActionId(): string {
  return `act-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
