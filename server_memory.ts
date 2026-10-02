import fs from "fs/promises";
import fsSync from "fs";
import path from "path";
import { Memory, MemoryCategory, MemoryTransaction } from "./src/lib/memoryTypes";
import { dataFile } from "./server_paths";

const MEMORY_FILE = dataFile("memories.json");

// ---------------------------------------------------------------------------
// Hardened persistence primitives (F1)
//
// - Atomic writes: write to a temp file, then rename over the live file. A
//   crash mid-write can never corrupt memories.json (the rename is atomic on
//   the same volume).
// - Serialized writes: a promise-chain mutex guarantees read-modify-write
//   sequences never interleave across concurrent callers.
// - Backup/rollback: the last good state is kept at memories.json.bak so a
//   corrupt live file can be restored instead of silently discarded.
// - Corruption recovery: loadMemories validates JSON and shape; on failure it
//   quarantines the corrupt file, tries the .bak, and only then starts empty.
// ---------------------------------------------------------------------------

const MAX_MEMORIES = 500;

const VALID_CATEGORIES: MemoryCategory[] = [
  "identity",
  "preference",
  "goal",
  "project",
  "relationship",
  "emotional",
  "behavior",
];

/** Coerce an arbitrary value to a valid MemoryCategory (default: identity). */
function toCategory(value: unknown): MemoryCategory {
  return VALID_CATEGORIES.includes(value as MemoryCategory)
    ? (value as MemoryCategory)
    : "identity";
}

/** Promise-chain mutex: serializes all writes to the memory file. */
let writeChain: Promise<void> = Promise.resolve();

// Truthful memory-persistence health (DEGRADED, never fatal).
interface MemHealth {
  status: "HEALTHY" | "DEGRADED";
  consecutiveFailures: number;
  lastSuccessAt: number | null;
  lastFailureAt: number | null;
  lastErrorCode: string | null;
  lastTarget: string | null;
  pendingWrites: number;
}

const _memHealth: MemHealth = {
  status: "HEALTHY",
  consecutiveFailures: 0,
  lastSuccessAt: null,
  lastFailureAt: null,
  lastErrorCode: null,
  lastTarget: null,
  pendingWrites: 0,
};

function recordMemSuccess(): void {
  _memHealth.status = "HEALTHY";
  _memHealth.consecutiveFailures = 0;
  _memHealth.lastSuccessAt = Date.now();
  _memHealth.lastErrorCode = null;
}

let _lastMemFailLog = 0;
function recordMemFailure(target: string, err: unknown): void {
  const e = err as NodeJS.ErrnoException;
  _memHealth.status = "DEGRADED";
  _memHealth.consecutiveFailures += 1;
  _memHealth.lastFailureAt = Date.now();
  _memHealth.lastErrorCode = e?.code ?? "UNKNOWN";
  _memHealth.lastTarget = target;
  if (Date.now() - _lastMemFailLog > 30_000) {
    _lastMemFailLog = Date.now();
    console.error(`[Memory] persistence DEGRADED (${_memHealth.consecutiveFailures}): ${target}: ${e?.code ?? "UNKNOWN"}`);
  }
}

export function getMemoryPersistenceHealth(): MemHealth {
  return { ..._memHealth };
}

/** Wait for the write lock, run the work, release the lock. */
async function withWriteLock<T>(work: () => Promise<T>): Promise<T> {
  const run = writeChain.then(work);
  // Keep the chain alive even if `work` rejects; the next caller must proceed.
  writeChain = run.then(
    () => undefined,
    () => undefined
  );
  return run;
}

function isTransientFsError(err: unknown): boolean {
  const code = (err as NodeJS.ErrnoException)?.code;
  return code === "EPERM" || code === "EACCES" || code === "EBUSY";
}

const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

async function cleanupStaleTmpFiles(file: string, maxAgeMs = 5 * 60 * 1000): Promise<void> {
  try {
    const dir = path.dirname(file);
    const base = path.basename(file);
    const entries = await fs.readdir(dir).catch(() => [] as string[]);
    const now = Date.now();
    for (const name of entries) {
      if (!name.startsWith(base + ".tmp.")) continue;
      const full = path.join(dir, name);
      try {
        const st = await fs.stat(full);
        if (now - st.mtimeMs > maxAgeMs) await fs.unlink(full).catch(() => undefined);
      } catch { /* best-effort */ }
    }
  } catch { /* best-effort */ }
}

/**
 * Atomic file write shared by every Node-side JSON/text store.
 *
 * Windows-safe sequence: `.bak` of the previous good copy -> unique temp file
 * per attempt -> write -> fsync -> close -> bounded `rename` retry. Transient
 * EPERM/EACCES/EBUSY (OneDrive/AV holding the target) are retried with
 * exponential backoff; the bounded budget returns `false` instead of throwing.
 *
 * `recordHealth` is true only for the memory store, so `getMemoryPersistenceHealth()`
 * keeps reporting the memory store's health rather than another file's.
 */
async function atomicWriteFile(
  file: string,
  payload: string,
  opts: { recordHealth?: boolean } = {},
): Promise<boolean> {
  const recordHealth = opts.recordHealth !== false;
  const bak = `${file}.bak`;

  // Keep a backup of the current good state before overwriting it.
  try {
    await fs.copyFile(file, bak);
  } catch {
    /* first write / file missing — fine */
  }

  await cleanupStaleTmpFiles(file);
  const unique = `${process.pid}.${Date.now().toString(36)}.${Math.random().toString(36).slice(2, 8)}`;
  let lastErr: unknown = null;
  let delayMs = 50;
  for (let attempt = 0; attempt < 6; attempt++) {
    const tmp = `${file}.tmp.${unique}.${attempt}`;
    try {
      // Deterministic failure-injection hook for tests (never set in prod).
      const forceHook = (globalThis as any).__MYRAA_TEST_FORCE_RENAME_EPERM as
        | ((dest: string) => boolean)
        | undefined;
      if (typeof forceHook === "function" && forceHook(file)) {
        const forced: any = new Error("EPERM: operation not permitted, rename");
        forced.code = "EPERM";
        throw forced;
      }
      const handle = await fs.open(tmp, "w");
      try {
        await handle.writeFile(payload, "utf-8");
        try { await handle.sync(); } catch { /* best-effort */ }
      } finally {
        await handle.close();
      }
      await fs.rename(tmp, file);
      if (recordHealth) recordMemSuccess();
      return true;
    } catch (err) {
      lastErr = err;
      await fs.unlink(tmp).catch(() => undefined);
      if (!isTransientFsError(err)) throw err;
      if (attempt < 5) {
        await sleep(delayMs);
        delayMs = Math.min(delayMs * 2, 1000);
      }
    }
  }
  if (recordHealth) recordMemFailure(file, lastErr);
  return false;
}

/** Write JSON atomically to `file` (memory-store health accounting). */
async function atomicWriteJson(file: string, data: unknown): Promise<boolean> {
  return atomicWriteFile(file, JSON.stringify(data, null, 2));
}

/**
 * Atomic JSON write for stores that are NOT the brain-memory store, so their
 * failures are reported by their own callers rather than polluting
 * `getMemoryPersistenceHealth()`.
 */
export async function atomicWriteJsonFile(file: string, data: unknown): Promise<boolean> {
  return atomicWriteFile(file, JSON.stringify(data, null, 2), { recordHealth: false });
}

/**
 * Atomic text write (used for the server-side `.env` secrets file).
 * Returns true only when the replacement actually landed on disk.
 */
export async function atomicWriteTextFile(file: string, text: string): Promise<boolean> {
  return atomicWriteFile(file, text, { recordHealth: false });
}

/**
 * Validates that a value is a well-formed Memory array. Invalid entries are
 * dropped so one corrupt record cannot take down the whole store.
 */
function sanitizeMemories(value: unknown): Memory[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const out: Memory[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const m = item as Record<string, unknown>;
    const id = typeof m.id === "string" ? m.id : "";
    const category = toCategory(m.category);
    const text = typeof m.text === "string" ? m.text.trim() : "";
    const createdAt = typeof m.createdAt === "string" ? m.createdAt : "";
    const updatedAt = typeof m.updatedAt === "string" ? m.updatedAt : "";
    if (!id || !text) continue;
    if (seen.has(id)) continue; // duplicate id — drop
    seen.add(id);
    out.push({ id, category, text, createdAt, updatedAt });
  }
  return out;
}

export async function loadMemories(): Promise<Memory[]> {
  let raw: string | null = null;
  try {
    raw = await fs.readFile(MEMORY_FILE, "utf-8");
    const parsed = JSON.parse(raw);
    return sanitizeMemories(parsed);
  } catch (error: any) {
    if (error.code === "ENOENT") {
      return [];
    }
    // Corrupt (or partially written) file. Quarantine it so we never lose the
    // evidence, then try the last known-good backup.
    console.error("[Memory] Corrupt memory file detected, attempting recovery:", error);
    try {
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      await fs.rename(MEMORY_FILE, `${MEMORY_FILE}.corrupt.${ts}`);
    } catch {
      /* best-effort quarantine */
    }
    try {
      const bak = await fs.readFile(`${MEMORY_FILE}.bak`, "utf-8");
      const restored = sanitizeMemories(JSON.parse(bak));
      if (restored.length > 0) {
        console.log(`[Memory] Recovered ${restored.length} memories from backup.`);
        return restored;
      }
    } catch {
      /* no usable backup */
    }
    return [];
  }
}

export async function saveMemories(memories: Memory[]): Promise<void> {
  await withWriteLock(async () => {
    const clean = sanitizeMemories(memories);
    const bounded = enforceRetention(clean);
    _memHealth.pendingWrites += 1;
    try {
      const ok = await atomicWriteJson(MEMORY_FILE, bounded);
      if (!ok) {
        // Transient lock storm: in-memory state stays valid, disk retries
        // on the next save; report but never crash the server.
        console.error("[Memory] saveMemories deferred: disk transiently locked, will retry on next save.");
        _pendingMemories = bounded;
        scheduleMemRetry();
        return;
      }
      _pendingMemories = null;
      console.log(`[Memory] Saved ${bounded.length} memories successfully.`);
    } catch (error) {
      // Non-transient disk error: record degraded, keep in-memory state.
      recordMemFailure(MEMORY_FILE, error);
      console.error("[Memory] Error writing memory file:", error);
    } finally {
      _memHealth.pendingWrites = Math.max(0, _memHealth.pendingWrites - 1);
    }
  });
}

let _pendingMemories: Memory[] | null = null;
let _memRetryScheduled = false;
function scheduleMemRetry(): void {
  if (_memRetryScheduled) return;
  _memRetryScheduled = true;
  setTimeout(() => {
    _memRetryScheduled = false;
    if (!_pendingMemories) return;
    const pending = _pendingMemories;
    saveMemories(pending).catch(() => undefined);
  }, 5000).unref?.();
}

/** Flush pending memory retry synchronously-ish (shutdown path). */
export async function flushMemoryPersistence(): Promise<void> {
  if (!_pendingMemories) return;
  try {
    await saveMemories(_pendingMemories);
  } catch { /* best-effort */ }
}

// ---------------------------------------------------------------------------
// Retention & deduplication (F1)
// ---------------------------------------------------------------------------

/** Normalized text used for content-level deduplication. */
export function normalizeMemoryText(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").trim();
}

/** Importance heuristic used only for bounded retention / eviction. */
function memoryImportance(m: Memory): number {
  const categoryWeight: Record<string, number> = {
    identity: 0.9,
    goal: 0.85,
    preference: 0.8,
    relationship: 0.8,
    project: 0.7,
    emotional: 0.6,
    behavior: 0.55,
    system: 0.5,
  };
  const cat = (categoryWeight[m.category] ?? 0.5);
  const len = Math.min(m.text.length / 300, 1.0) * 0.3;
  let recency = 0.0;
  const t = Date.parse(m.updatedAt || m.createdAt || "");
  if (!Number.isNaN(t)) {
    const ageDays = (Date.now() - t) / 86_400_000;
    recency = Math.max(0, 1 - ageDays / 365) * 0.2;
  }
  return cat + len + recency;
}

/**
 * Apply retention: cap the store at MAX_MEMORIES, evicting lowest-importance
 * records first (importance = category weight + length + recency).
 */
export function enforceRetention(memories: Memory[]): Memory[] {
  if (memories.length <= MAX_MEMORIES) return memories;
  return [...memories]
    .sort((a, b) => memoryImportance(b) - memoryImportance(a))
    .slice(0, MAX_MEMORIES);
}

/**
 * Content-level dedup: within a list, collapse records that share the same
 * normalized text. The newest record wins (its metadata is preserved). Also
 * collapses duplicate ids (first occurrence wins).
 */
export function dedupeMemories(memories: Memory[]): Memory[] {
  const byText = new Map<string, Memory>();
  const byId = new Map<string, Memory>();
  const out: Memory[] = [];
  // Iterate newest-first so a later (newer) duplicate wins over an older one.
  const sorted = [...memories].sort(
    (a, b) =>
      Date.parse(b.updatedAt || b.createdAt || "") -
      Date.parse(a.updatedAt || a.createdAt || "")
  );
  for (const m of sorted) {
    const key = `${m.category}\u0000${normalizeMemoryText(m.text)}`;
    if (byText.has(key) || byId.has(m.id)) continue;
    byText.set(key, m);
    byId.set(m.id, m);
    out.push(m);
  }
  // Preserve original ordering after dedup.
  const keptIds = new Set(out.map((m) => m.id));
  return memories.filter((m) => keptIds.has(m.id));
}

// ---------------------------------------------------------------------------
// Sensitive-data rejection (F1)
// ---------------------------------------------------------------------------

const SENSITIVE_PATTERNS: RegExp[] = [
  /\b(api[_-]?key|apikey)\b[\s:=]+[A-Za-z0-9_\-]{12,}/i,
  /\b(password|passwd|pwd)\b[\s:=]+[^\s]{6,}/i,
  /\b(secret|client[_-]?secret)\b[\s:=]+[^\s]{6,}/i,
  /\b(access[_-]?token|auth[_-]?token|bearer)\b[\s:=]+[^\s]{10,}/i,
  /\b(ssh[_-]?key|private[_-]?key|BEGIN [A-Z ]*PRIVATE KEY)\b/i,
  /(sk-|rk-|ghp_|github_pat_)[A-Za-z0-9]{16,}/, // common LLM/GitHub token prefixes
  /\bnvapi-[A-Za-z0-9_\-]{20,}\b/, // NVIDIA API key shape
  /\btvly-[A-Za-z0-9_\-]{16,}\b/, // Tavily API key shape
  /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/, // JWT tokens
  /\b[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}\b/, // credit-card shaped
  // Natural phrasing: "my password is hunter2" / "the secret is 12345abc"
  /\b(password|passwd|pwd|secret|client[_-]?secret)\b[^\n]{0,6}is\s+\S*\d\S*/i,
];

/**
 * Reject memory text that looks like a secret (API key, password, token, …).
 * Secrets must never be persisted as ordinary memories.
 */
export function isSensitiveMemoryText(text: string): boolean {
  return SENSITIVE_PATTERNS.some((re) => re.test(text));
}

/** Stable-ish random id used when minting new memories. */
export function generateMemoryId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).substring(2, 8)}`;
}

/**
 * Validate + normalize a single memory add. Returns null when the input is
 * empty or sensitive (secrets are rejected, not stored).
 */
export function normalizeNewMemory(
  category: string,
  text: string
): Memory | null {
  const clean = (text || "").trim();
  if (!clean) return null;
  if (isSensitiveMemoryText(clean)) {
    console.warn("[Memory] Rejected memory containing sensitive data (never stored).");
    return null;
  }
  const now = new Date().toISOString();
  return {
    id: generateMemoryId(),
    category: toCategory(category),
    text: clean,
    createdAt: now,
    updatedAt: now,
  };
}

/** Load → mutate → persist as one serialized unit (lost-update safe). */
export async function updateMemories(
  mutate: (memories: Memory[]) => Memory[]
): Promise<Memory[]> {
  return withWriteLock(async () => {
    const current = await loadMemories();
    const next = mutate(current);
    const clean = sanitizeMemories(next);
    const deduped = dedupeMemories(clean);
    const bounded = enforceRetention(deduped);
    await atomicWriteJson(MEMORY_FILE, bounded);
    return bounded;
  });
}

// Format memory core to system instruction injections
export function formatSystemInstructionsWithMemories(baseInstruction: string, memories: Memory[]): string {
  if (memories.length === 0) {
    return baseInstruction +
      "\n\n" +
      "=== MYRAA MEMORY CORE ===\n" +
      "You do not possess any historic recollections of this companion yet. " +
      "As you speak, pay deep attention to who they are, their projects, relationships, and habits so you naturally grow closer over time.\n" +
      "=========================\n";
  }

  // ----------------------------------------------------
// Build Critical User Preferences
// These are injected BEFORE normal memories so the LLM
// always treats them as highest-priority instructions.
// ----------------------------------------------------

let criticalPreferences = "";

const preferenceTexts = memories
  .filter(m => m.category === "preference")
  .map(m => m.text.toLowerCase());

if (preferenceTexts.some(t => t.includes("hindi"))) {
  criticalPreferences +=
`=== CRITICAL USER LANGUAGE PREFERENCE ===
The user ALWAYS prefers Hindi.

You MUST:
- Speak in Hindi by default.
- Never start conversations in English.
- Only switch to English if the user explicitly requests it.

==========================================

`;
}

  // Group by category
  const grouped: Record<string, string[]> = {};
  memories.forEach((m) => {
    grouped[m.category] = grouped[m.category] || [];
    grouped[m.category].push(m.text);
  });

  let memoryBlock =
    "\n\n" +
    criticalPreferences +
    "=== MYRAA PERSISTENT MEMORY CORE (RECOLLECTIONS) ===\n" +
    "You have spoken with this user for a long duration. Below are your persistent recollections of who they are.\n" +
    "CRITICAL BRAND AND COGNITIVE PRINCIPLES:\n" +
    "- INTEGRATE MEMORIES INSTINCTIVELY: Always make conversational references feel completely smooth, natural, and human. NEVER say 'According to my memory files...', 'My recollection database indicates...', or 'As you told me on June 12th...'. Instead, speak of these details casually and supportively as a true friend would (e.g. 'Oh, since you're working on that website project...', 'I hope you're keeping up with your YouTube channel goals too!').\n" +
    "- COMPANIONSHIP DEPTH: Allow your witty and responsive personality to adapt with empathy, based on their goals, life events, emotional milestones, and preferences.\n\n" +
    "CURRENT PERSISTENT KNOWLEDGE CARD:\n";

  const categoriesOrdered = [
    { key: "identity", label: "Identity (Name, nick, profession, background)" },
    { key: "preference", label: "Preferences & Tastes (Likes, dislikes, games, movies)" },
    { key: "goal", label: "Active Goals & Aspirations" },
    { key: "project", label: "Ongoing Projects & Ecosystems" },
    { key: "relationship", label: "Key People & Relationships mentioned" },
    { key: "emotional", label: "Emotional Highlights & Core Milestones" },
    { key: "behavior", label: "Observed Traits & Behavioral Tendencies" },
  ];

  categoriesOrdered.forEach((cat) => {
    const list = grouped[cat.key] || [];
    if (list.length > 0) {
      memoryBlock += `* ${cat.label}:\n` + list.map(t => `  - ${t}`).join("\n") + "\n";
    }
  });

  memoryBlock += "====================================================\n";

  return baseInstruction + memoryBlock;
}

// Background memory consolidation queue lock
let isConsolidating = false;

/**
 * Apply ADD/UPDATE/REMOVE memory transactions to an existing memory list.
 * Pure + testable: no I/O, no LLM. Dedupes ADD by normalized text+category,
 * drops sensitive content, and ignores updates that target a missing id.
 */
export function applyMemoryTransactions(
  currentMemories: Memory[],
  transactions: MemoryTransaction[]
): Memory[] {
  let updatedMemories = [...currentMemories];
  const timestamp = new Date().toISOString();

  for (const trx of transactions) {
    if (trx.action === "ADD") {
      const cleanText = (trx.text || "").trim();
      if (!cleanText || isSensitiveMemoryText(cleanText)) continue;
      // Content-level dedup against existing memories.
      const key = normalizeMemoryText(cleanText);
      const existingIdx = updatedMemories.findIndex(
        (m) => `${m.category}\u0000${normalizeMemoryText(m.text)}` === `${trx.category}\u0000${key}`
      );
      if (existingIdx !== -1) {
        updatedMemories[existingIdx] = { ...updatedMemories[existingIdx], updatedAt: timestamp };
        continue;
      }
      updatedMemories.push({
        id: generateMemoryId(),
        category: toCategory(trx.category),
        text: cleanText,
        createdAt: timestamp,
        updatedAt: timestamp
      });
    } else if (trx.action === "UPDATE") {
      const tarIndex = updatedMemories.findIndex(m => m.id === trx.id);
      const cleanText = (trx.text || "").trim();
      if (tarIndex !== -1 && cleanText && !isSensitiveMemoryText(cleanText)) {
        updatedMemories[tarIndex] = {
          ...updatedMemories[tarIndex],
          category: toCategory(trx.category),
          text: cleanText,
          updatedAt: timestamp
        };
      }
      // Missing-id UPDATE is silently dropped instead of creating a duplicate.
    } else if (trx.action === "REMOVE") {
      updatedMemories = updatedMemories.filter(m => m.id !== trx.id);
    }
  }
  return updatedMemories;
}

export async function processConversationSlice(
  apiKey: string,
  dialogueHistory: { role: string; text: string }[]
): Promise<Memory[] | null> {
  if (isConsolidating) {
    console.log("[Memory] Consolidation loop busy, skipping slice processing");
    return null;
  }

  if (dialogueHistory.length < 2) {
    return null;
  }

  isConsolidating = true;
  console.log("[Memory] Initiating pipeline for dialogue slice of length:", dialogueHistory.length);

  try {
    // Use local Ollama for memory consolidation (local-first mode)
    const ollamaUrl = process.env.OLLAMA_URL || "http://127.0.0.1:11434";

    const currentMemories = await loadMemories();

    // Format memory map to help the model understand what to edit
    const memoryContext = currentMemories.map(m => `ID: ${m.id} | Category: ${m.category} | Fact: ${m.text}`).join("\n");
    const dialogueContext = dialogueHistory.map(line => `${line.role === "user" ? "User" : "Myraa"}: ${line.text}`).join("\n");

    const prompt = `You are Myraa's deep cognitive recollection engine. Your task is to analyze the recent conversation piece against previous persistent memories, and output precise update transactions.

### OBJECTIVE
Decide if any statements contain durable, important personal facts, enduring preferences, aspirations, ongoing projects, critical relationships, key historical emotional events, or behavioral trends.
Avoid cataloging small talk, greetings, general chit-chat, or fleeting sentences (e.g., ignore 'hello', 'how are you', 'waking up', 'lol').

### CURRENT USER MEMORIES:
${memoryContext || "(No memory records exist)"}

### RECENT DIALOGUE SLICE:
${dialogueContext}

### RULES
- ACTIONS:
  - "ADD": If new material information is introduced (e.g. user says 'My favorite food is lasagna' and it's not present).
  - "UPDATE": If previous information has evolved or is corrected (e.g. user says 'I changed my major to computer science' when memory says they study history). Provide the exact ID of the memory to replace.
  - "REMOVE": If a memory was explicitly disproven or the user directly asked Myraa to forget it.
- TEXT STYLE: Express the memories as clean, concise, third-person declarative summaries (e.g., 'The user is building a startup named Myraa.', 'The user loves playing GTA 6.', 'The user enjoys technical and fast-paced styling explanations.'). Do not include conversational filler, quotes, or timestamps.
- ID: For ADD, leave blank. For UPDATE or REMOVE, provide the exact 'id' from the "Current user memories" list.
- SECURITY: Never extract passwords, API keys, tokens, or any secret as a memory. If a transaction's text would contain such a secret, drop it.

Respond with ONLY a JSON object: {"transactions": [{"action": "ADD|UPDATE|REMOVE", "id": "", "category": "identity|preference|goal|project|relationship|emotional|behavior", "text": "..."}]}
If no updates needed, respond with {"transactions": []}`;

    const resp = await fetch(`${ollamaUrl}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "llama3.2:3b",
        prompt,
        stream: false,
        options: { temperature: 0.1, num_ctx: 4096 },
      }),
      signal: AbortSignal.timeout(30000),
    });

    if (!resp.ok) {
      console.error("[Memory] Ollama request failed:", resp.status);
      return null;
    }

    const data = await resp.json();
    const responseText = data?.response || "";
    const resultObj = JSON.parse(responseText);
    const transactions: MemoryTransaction[] = resultObj.transactions || [];

    if (transactions.length === 0) {
      console.log("[Memory] Zero transactions generated. Ignored routine conversations.");
      isConsolidating = false;
      return null;
    }

    console.log(`[Memory] Processing ${transactions.length} memory updates:`, JSON.stringify(transactions));

    const updatedMemories = applyMemoryTransactions(currentMemories, transactions);

    // Persist through the serialized, deduplicated, bounded path.
    const finalMemories = await updateMemories(() => updatedMemories);
    isConsolidating = false;
    return finalMemories;

  } catch (error) {
    console.error("[Memory] Consolidation failure:", error);
    isConsolidating = false;
    return null;
  }
}

// ---------------------------------------------------------------------------
// Conversation history (recent user/assistant dialogue) — Node-owned, bounded.
// This is distinct from long-term memories.json: it is short-lived continuity
// context (recent turns) fed to the Brain, not durable recollections.
// ---------------------------------------------------------------------------
const CONVERSATION_FILE = dataFile("conversation_history.json");
const MAX_CONVERSATION_TURNS = 30;

export async function loadConversationHistory(): Promise<
  { role: string; text: string }[]
> {
  try {
    const data = await fs.readFile(CONVERSATION_FILE, "utf-8");
    const parsed = JSON.parse(data);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error: any) {
    if (error.code === "ENOENT") return [];
    console.error("[Memory] Error loading conversation history:", error);
    return [];
  }
}

export async function saveConversationHistory(
  history: { role: string; text: string }[]
): Promise<boolean> {
  return withWriteLock(async () => {
    try {
      // Bound the persisted window so it cannot grow without limit.
      const bounded = history.slice(-MAX_CONVERSATION_TURNS);
      const ok = await atomicWriteJson(CONVERSATION_FILE, bounded);
      if (!ok) {
        _pendingHistory = bounded;
        scheduleHistoryRetry();
      } else {
        _pendingHistory = null;
      }
      return ok;
    } catch (error) {
      recordMemFailure(CONVERSATION_FILE, error);
      console.error("[Memory] Error writing conversation history:", error);
      return false;
    }
  });
}

let _pendingHistory: { role: string; text: string }[] | null = null;
let _historyRetryScheduled = false;
function scheduleHistoryRetry(): void {
  if (_historyRetryScheduled) return;
  _historyRetryScheduled = true;
  setTimeout(() => {
    _historyRetryScheduled = false;
    if (!_pendingHistory) return;
    const pending = _pendingHistory;
    saveConversationHistory(pending).catch(() => undefined);
  }, 5000).unref?.();
}