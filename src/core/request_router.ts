// ============================================================================
// MYRAA Request Router — Unified Routing Boundary for Phase 29.6
// ============================================================================

import type {
  MyraaRequestContext,
  RequestClassification,
  ModelDecision,
} from './contracts';

// ── Routing Decision ────────────────────────────────────────────────────────

export interface RoutingDecision {
  readonly classification: RequestClassification;
  readonly requiresAgent: boolean;
  readonly requiresVision: boolean;
  readonly requiresComputer: boolean;
  readonly requiresResearch: boolean;
  readonly requiresFinance: boolean;
  readonly requiresQuant: boolean;
  readonly requiresModel: boolean;
  readonly modelDecision?: ModelDecision;
  readonly specialistEngine?: string;
  readonly deterministicPath?: string;
  readonly reason: string;
}

// ── Model Selection ─────────────────────────────────────────────────────────

// SINGLE SOURCE OF TRUTH for Ollama model routing (verified against the live
// Ollama installation — qwen3:8b is NOT installed; see /api/tags).
// Phase 29.8: qwen3:4b (2.5GB) and qwen3.5:4b (3.4GB, vision+tools+thinking)
// fit the 4GB VRAM budget.
export const MODEL_ROUTES = {
  FAST: 'qwen3:4b',
  STRONG: 'qwen3.5:4b',
  VISION: 'qwen3.5:4b',
  FALLBACK: 'llama3.2:3b',
} as const;

const FAST_MODEL: ModelDecision = {
  model: MODEL_ROUTES.FAST,
  provider: 'ollama',
  reason: 'Simple conversational request',
  latencyBudget: 3000,
  contextBudget: 4096,
  modality: 'text',
  temperature: 0.7,
  maxTokens: 1024,
  fallback: MODEL_ROUTES.FALLBACK,
};

const STRONG_MODEL: ModelDecision = {
  model: MODEL_ROUTES.STRONG,
  provider: 'ollama',
  reason: 'Complex reasoning required',
  latencyBudget: 10000,
  contextBudget: 8192,
  modality: 'text',
  temperature: 0.7,
  maxTokens: 2048,
  fallback: 'qwen3:4b',
};

// Phase 29.8: gemma3:4b lacks vision capability in the installed build;
// qwen3.5:4b reports capabilities ["vision","completion","tools","thinking"].
// NOTE: qwen3.5:4b is the ONLY installed vision-capable model, so there is
// deliberately NO fallback — a vision request must surface unavailability
// rather than silently degrade to a text-only model.
const VISION_MODEL: ModelDecision = {
  model: MODEL_ROUTES.VISION,
  provider: 'ollama',
  reason: 'Visual/multimodal task',
  latencyBudget: 5000,
  contextBudget: 4096,
  modality: 'vision',
  temperature: 0.5,
  maxTokens: 1024,
};

function selectModel(classification: RequestClassification, complexity: 'simple' | 'complex' = 'simple'): ModelDecision {
  switch (classification) {
    case 'VISION':
      return VISION_MODEL;
    case 'FINANCE':
    case 'QUANT':
      return STRONG_MODEL;
    case 'AGENT_TASK':
      return STRONG_MODEL;
    case 'COMPUTER_ACTION':
      return FAST_MODEL;
    case 'RESEARCH':
      return STRONG_MODEL;
    default:
      return complexity === 'complex' ? STRONG_MODEL : FAST_MODEL;
  }
}

// ── Deterministic Routing ───────────────────────────────────────────────────

function findDeterministicPath(ctx: MyraaRequestContext): string | null {
  const input = ctx.input.toLowerCase();

  // System info — no LLM needed
  if (/^(system info|what time|current time|date|clock)/i.test(input)) {
    return 'systemInfo';
  }

  // Volume — no LLM needed
  if (/^(volume up|volume down|mute|unmute)/i.test(input)) {
    return 'volumeControl';
  }

  // Simple app open — no LLM needed
  if (/^(open|launch|start)\s+(chrome|notepad|explorer|vscode|code|firefox|edge)/i.test(input)) {
    return 'openApplication';
  }

  // Screenshot — no LLM needed
  if (/^(take )?screenshot$/i.test(input)) {
    return 'screenshot';
  }

  return null;
}

// ── Main Router ─────────────────────────────────────────────────────────────

export function routeRequest(ctx: MyraaRequestContext): RoutingDecision {
  const classification = ctx.classification;
  const deterministicPath = findDeterministicPath(ctx);

  // If we have a deterministic path, skip the LLM
  if (deterministicPath) {
    return {
      classification,
      requiresAgent: false,
      requiresVision: false,
      requiresComputer: classification === 'COMPUTER_ACTION',
      requiresResearch: false,
      requiresFinance: false,
      requiresQuant: false,
      requiresModel: false,
      deterministicPath,
      reason: `Deterministic path: ${deterministicPath}`,
    };
  }

  // Route based on classification
  switch (classification) {
    case 'VISION':
      return {
        classification,
        requiresAgent: false,
        requiresVision: true,
        requiresComputer: false,
        requiresResearch: false,
        requiresFinance: false,
        requiresQuant: false,
        requiresModel: true,
        modelDecision: selectModel(classification),
        specialistEngine: 'vision',
        reason: 'Vision observation required',
      };

    case 'COMPUTER_ACTION':
      return {
        classification,
        requiresAgent: false,
        requiresVision: true,
        requiresComputer: true,
        requiresResearch: false,
        requiresFinance: false,
        requiresQuant: false,
        requiresModel: true,
        modelDecision: selectModel(classification),
        specialistEngine: 'computer',
        reason: 'Computer control action required',
      };

    case 'FILE_OPERATION':
      return {
        classification,
        requiresAgent: true,
        requiresVision: false,
        requiresComputer: false,
        requiresResearch: false,
        requiresFinance: false,
        requiresQuant: false,
        requiresModel: true,
        modelDecision: selectModel(classification),
        specialistEngine: 'agent',
        reason: 'File operation via agent',
      };

    case 'RESEARCH':
      return {
        classification,
        requiresAgent: true,
        requiresVision: false,
        requiresComputer: false,
        requiresResearch: true,
        requiresFinance: false,
        requiresQuant: false,
        requiresModel: true,
        modelDecision: selectModel(classification, 'complex'),
        specialistEngine: 'research',
        reason: 'Research required',
      };

    case 'FINANCE':
      return {
        classification,
        requiresAgent: true,
        requiresVision: false,
        requiresComputer: false,
        requiresResearch: false,
        requiresFinance: true,
        requiresQuant: false,
        requiresModel: true,
        modelDecision: selectModel(classification, 'complex'),
        specialistEngine: 'finance',
        reason: 'Financial analysis required',
      };

    case 'QUANT':
      return {
        classification,
        requiresAgent: true,
        requiresVision: false,
        requiresComputer: false,
        requiresResearch: false,
        requiresFinance: true,
        requiresQuant: true,
        requiresModel: true,
        modelDecision: selectModel(classification, 'complex'),
        specialistEngine: 'quant',
        reason: 'Quantitative analysis required',
      };

    case 'AGENT_TASK':
      return {
        classification,
        requiresAgent: true,
        requiresVision: false,
        requiresComputer: false,
        requiresResearch: false,
        requiresFinance: false,
        requiresQuant: false,
        requiresModel: true,
        modelDecision: selectModel(classification, 'complex'),
        specialistEngine: 'agent',
        reason: 'Multi-step agent task',
      };

    case 'SYSTEM':
      return {
        classification,
        requiresAgent: false,
        requiresVision: false,
        requiresComputer: false,
        requiresResearch: false,
        requiresFinance: false,
        requiresQuant: false,
        requiresModel: false,
        deterministicPath: 'system',
        reason: 'System operation',
      };

    default:
      // CONVERSATION — use brain directly
      return {
        classification,
        requiresAgent: false,
        requiresVision: false,
        requiresComputer: false,
        requiresResearch: false,
        requiresFinance: false,
        requiresQuant: false,
        requiresModel: true,
        modelDecision: selectModel(classification),
        reason: 'General conversation — route to brain',
      };
  }
}
