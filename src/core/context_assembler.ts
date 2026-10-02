// ============================================================================
// MYRAA Context Assembler — Selective Context Assembly for Requests
// ============================================================================

import type {
  MyraaRequestContext,
  InputType,
  RequestClassification,
  ConversationTurn,
  MemoryContext,
  VisionContext,
  ToolContext,
  PolicyContext,
  RequestTimestamps,
  LearningSignals,
} from './contracts';
import { generateRequestId, generateTraceId } from './contracts';
import { loadMemories, formatSystemInstructionsWithMemories } from '../../server_memory';
import { hybridRetrieve } from './memory_retrieval';

// ── Classification ──────────────────────────────────────────────────────────

const VISION_KEYWORDS = /\b(screenshot|screen|see|look|ocr|what.{0,10}(on|is).{0,10}screen|capture|visual)\b/i;
const COMPUTER_KEYWORDS = /\b(open|launch|start|close|minimize|maximize|chrome|notepad|vscode|firefox|edge|spotify|discord|volume|brightness|click|type|press|scroll|drag|mouse|keyboard|hotkey)\b/i;
const FILE_KEYWORDS = /\b(read the file|read file|write file|create file|delete file|rename file|move file|file path|folder|directory)\b/i;
const RESEARCH_KEYWORDS = /\b(research|search|find|look up|google|web|internet|browse|summarize|summary)\b/i;
const FINANCE_KEYWORDS = /\b(stock|market|nifty|sensex|price|trade|portfolio|invest|financial|fund|equity|share|dividend)\b/i;
const CODE_KEYWORDS = /\b(code|script|program|function|class|debug|error|fix|run|execute|python|javascript)\b/i;

export function classifyInput(input: string): RequestClassification {
  const lower = input.toLowerCase();
  if (VISION_KEYWORDS.test(lower)) return 'VISION';
  if (COMPUTER_KEYWORDS.test(lower)) return 'COMPUTER_ACTION';
  if (FILE_KEYWORDS.test(lower)) return 'FILE_OPERATION';
  if (CODE_KEYWORDS.test(lower)) return 'AGENT_TASK';
  if (RESEARCH_KEYWORDS.test(lower)) return 'RESEARCH';
  if (FINANCE_KEYWORDS.test(lower)) return 'FINANCE';
  return 'CONVERSATION';
}

// ── Memory Retrieval ────────────────────────────────────────────────────────

async function assembleMemoryContext(input: string): Promise<MemoryContext | undefined> {
  try {
    const memories = await loadMemories();
    if (!memories || memories.length === 0) return undefined;

    // Phase 29.7: hybrid retrieval — keyword relevance + recency + importance
    const scored = hybridRetrieve(memories, input, { maxResults: 10 });

    if (scored.length === 0) return undefined;

    const memoryContext = formatSystemInstructionsWithMemories('', memories);

    return {
      relevantMemories: scored.map(m => ({
        id: m.id,
        category: m.category,
        content: m.text,
        importance: m.importanceScore,
        recency: m.recencyScore,
      })),
      memoryContext: memoryContext || undefined,
    };
  } catch {
    return undefined;
  }
}

// ── Vision Context ──────────────────────────────────────────────────────────

function assembleVisionContext(
  classification: RequestClassification,
  visionEngine?: { isEngineRunning: boolean; observeOnce?: () => Promise<unknown> } | null,
): VisionContext | undefined {
  if (classification !== 'VISION' && classification !== 'COMPUTER_ACTION') return undefined;
  if (!visionEngine?.isEngineRunning) return { available: false };
  return { available: true };
}

// ── Tool Context ────────────────────────────────────────────────────────────

function assembleToolContext(): ToolContext {
  return {
    availableTools: [
      'openApplication', 'closeApplication', 'openWebsite',
      'searchWeb', 'searchYouTube', 'searchGoogle', 'searchGitHub',
      'createFile', 'readFile', 'renameFile', 'deleteFile', 'moveFile',
      'openFolder', 'listFiles', 'searchFiles',
      'volumeUp', 'volumeDown', 'muteToggle', 'setVolume',
      'takeScreenshot', 'saveScreenshot', 'analyzeScreenshot', 'readScreen',
      'typeText', 'pressKey', 'keyDown', 'keyUp', 'hotkey',
      'moveMouse', 'leftClick', 'rightClick', 'doubleClick', 'middleClick',
      'dragMouse', 'scrollMouse', 'mousePosition',
      'systemInfo', 'gpuInfo', 'temperatureInfo',
      'runShellCommand', 'runPythonScript',
    ],
  };
}

// ── Policy Context ──────────────────────────────────────────────────────────

function assemblePolicyContext(): PolicyContext {
  return {
    financialFirewallActive: true,
    autonomyLevel: 'SUPERVISED',
    blockedActions: [
      'execute_trade', 'place_order', 'buy_stock', 'sell_stock',
      'short_stock', 'transfer_funds', 'open_position', 'close_position',
    ],
  };
}

// ── Main Assembler ──────────────────────────────────────────────────────────

export interface AssembleContextOptions {
  input: string;
  inputType: InputType;
  conversation?: readonly ConversationTurn[];
  visionEngine?: { isEngineRunning: boolean } | null;
}

export async function assembleRequestContext(
  options: AssembleContextOptions,
): Promise<MyraaRequestContext> {
  const { input, inputType, conversation = [], visionEngine = null } = options;
  const now = new Date().toISOString();

  const classification = classifyInput(input);

  // Selective assembly — only fetch what's relevant
  const [memory, vision] = await Promise.all([
    assembleMemoryContext(input),
    Promise.resolve(assembleVisionContext(classification, visionEngine)),
  ]);

  const timestamps: RequestTimestamps = {
    received: now,
    contextAssembled: new Date().toISOString(),
  };

  return {
    requestId: generateRequestId(),
    traceId: generateTraceId(),
    input,
    inputType,
    classification,
    conversation,
    memory,
    vision,
    tools: assembleToolContext(),
    policy: assemblePolicyContext(),
    timestamps,
  };
}
