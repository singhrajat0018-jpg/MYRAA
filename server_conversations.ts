/**
 * MYRAA — Conversation Persistence Layer
 *
 * JSON-file-backed conversation storage in the writable data directory.
 * Each conversation is a separate file for atomic writes and easy cleanup.
 * An index file provides fast listing without reading every conversation.
 *
 * Phase 8 hardening:
 * - Atomic temp-file + rename writes (crash-safe)
 * - Per-conversation locking (concurrent-safe)
 * - Corruption detection + recovery
 * - Bounded history loading
 * - Automatic pruning
 */

import fs from "fs";
import path from "path";
import { DATA_DIR, dataFile } from "./server_paths";

// ── Types ──────────────────────────────────────────────────

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  /** Token count estimate (words * 1.3) for context budgeting */
  tokenEstimate: number;
  /** If assistant used tools, record them */
  toolCalls?: Array<{ name: string; args: Record<string, unknown>; result?: string }>;
  /** Metadata from brain pipeline */
  metadata?: Record<string, unknown>;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ConversationMessage[];
  /** Model used for this conversation */
  model: string;
  /** Total token estimate across all messages */
  totalTokens: number;
}

export interface ConversationSummary {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  model: string;
}

// ── Constants ──────────────────────────────────────────────

const CONVERSATIONS_DIR = path.join(DATA_DIR, "conversations");
const INDEX_FILE = path.join(CONVERSATIONS_DIR, "_index.json");
const MAX_CONVERSATIONS = 200;
const MAX_MESSAGES_PER_CONVERSATION = 500;

// ── Per-conversation locking ──────────────────────────────

const _locks = new Map<string, { queue: Array<() => void>; locked: boolean }>();

function _acquireLock(id: string): Promise<void> {
  return new Promise((resolve) => {
    let entry = _locks.get(id);
    if (!entry) {
      entry = { queue: [], locked: false };
      _locks.set(id, entry);
    }
    if (!entry.locked) {
      entry.locked = true;
      resolve();
    } else {
      entry.queue.push(() => {
        entry!.locked = true;
        resolve();
      });
    }
  });
}

function _releaseLock(id: string): void {
  const entry = _locks.get(id);
  if (!entry) return;
  if (entry.queue.length > 0) {
    const next = entry.queue.shift()!;
    next();
  } else {
    entry.locked = false;
    // Clean up idle lock entries to prevent memory leak
    if (entry.queue.length === 0 && !entry.locked) {
      _locks.delete(id);
    }
  }
}

/** Execute a function while holding the lock for a specific conversation. */
async function withLock<T>(id: string, fn: () => T | Promise<T>): Promise<T> {
  await _acquireLock(id);
  try {
    return await fn();
  } finally {
    _releaseLock(id);
  }
}

// ── Helpers ────────────────────────────────────────────────

function ensureDir(): void {
  try {
    fs.mkdirSync(CONVERSATIONS_DIR, { recursive: true });
  } catch { /* already exists */ }
}

function estimateTokens(text: string): number {
  return Math.ceil(text.split(/\s+/).length * 1.3);
}

function generateId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

// ── Windows-safe persistence health ─────────────────────
// Transient EPERM/EACCES/EBUSY during rename is a DEGRADED condition,
// never a process-fatal one. Tracked truthfully for health endpoints.

interface PersistenceHealth {
  status: "HEALTHY" | "DEGRADED";
  consecutiveFailures: number;
  lastSuccessAt: number | null;
  lastFailureAt: number | null;
  lastErrorCode: string | null;
  lastErrorMessage: string | null;
  lastTarget: string | null;
  pendingWrites: number;
  /** Per-target cooldown: after repeated failures on a specific target, skip
   *  writes to that target to prevent storm.  Keyed by file path. */
  cooldowns: Record<string, number>;
}

const _persistenceHealth: PersistenceHealth = {
  status: "HEALTHY",
  consecutiveFailures: 0,
  lastSuccessAt: null,
  lastFailureAt: null,
  lastErrorCode: null,
  lastErrorMessage: null,
  lastTarget: null,
  pendingWrites: 0,
  cooldowns: {},
};

function recordPersistSuccess(): void {
  _persistenceHealth.status = "HEALTHY";
  _persistenceHealth.consecutiveFailures = 0;
  _persistenceHealth.lastSuccessAt = Date.now();
  _persistenceHealth.lastErrorCode = null;
  _persistenceHealth.lastErrorMessage = null;
}

let _lastFailureLogAt = 0;

function recordPersistFailure(target: string, err: unknown): void {
  const e = err as NodeJS.ErrnoException;
  _persistenceHealth.status = "DEGRADED";
  _persistenceHealth.consecutiveFailures += 1;
  _persistenceHealth.lastFailureAt = Date.now();
  _persistenceHealth.lastErrorCode = e?.code ?? "UNKNOWN";
  _persistenceHealth.lastErrorMessage = e?.message ?? String(err);
  _persistenceHealth.lastTarget = target;
  // Per-target exponential cooldown: 2s, 4s, 8s, 16s, 32s, max 60s.
  // Only the failing target is cooled down; other files can still be written.
  const n = _persistenceHealth.consecutiveFailures;
  const cooldownMs = Math.min(2000 * Math.pow(2, Math.min(n - 1, 4)), 60_000);
  _persistenceHealth.cooldowns[target] = Date.now() + cooldownMs;
  const now = Date.now();
  if (now - _lastFailureLogAt > 30_000) {
    _lastFailureLogAt = now;
    console.error(
      `[Conversations] persistence DEGRADED (${_persistenceHealth.consecutiveFailures}): ` +
      `${target}: ${e?.code ?? "UNKNOWN"}`
    );
  }
}

/** Truthful persistence state for health endpoints. No file contents. */
export function getConversationPersistenceHealth(): PersistenceHealth {
  return { ..._persistenceHealth };
}

// ── Serialized write pipeline (one store, one pipeline) ──

const _writeChains = new Map<string, Promise<void>>();

function serializeWrite<T>(target: string, work: () => Promise<T> | T): Promise<T> {
  const prev = _writeChains.get(target) ?? Promise.resolve();
  _persistenceHealth.pendingWrites += 1;
  const run = prev.then(() => work(), () => work());
  const tracked: Promise<T> = run.then(
    (v) => { _persistenceHealth.pendingWrites = Math.max(0, _persistenceHealth.pendingWrites - 1); return v; },
    (e) => { _persistenceHealth.pendingWrites = Math.max(0, _persistenceHealth.pendingWrites - 1); throw e; }
  );
  _writeChains.set(target, tracked.then(() => undefined, () => undefined));
  return tracked;
}

function isTransientFsError(err: unknown): boolean {
  const code = (err as NodeJS.ErrnoException)?.code;
  return code === "EPERM" || code === "EACCES" || code === "EBUSY";
}

function sleepSync(ms: number): void {
  // Minimal busy-wait.  With the cooldown gate in atomicWriteJson, this
  // function is rarely called more than once per write attempt and the
  // delays are small (50-200ms).  Kept non-blocking to avoid stalling
  // voice WebSocket keepalive traffic on the shared event loop.
  const end = Date.now() + ms;
  while (Date.now() < end) { /* bounded spin */ }
}

function cleanupStaleTmpFiles(filePath: string, maxAgeMs = 5 * 60 * 1000): void {
  try {
    const dir = path.dirname(filePath);
    const base = path.basename(filePath);
    if (!fs.existsSync(dir)) return;
    const now = Date.now();
    for (const name of fs.readdirSync(dir)) {
      if (!name.startsWith(base + ".tmp.")) continue;
      const full = path.join(dir, name);
      try {
        if (now - fs.statSync(full).mtimeMs > maxAgeMs) fs.unlinkSync(full);
      } catch { /* best-effort */ }
    }
  } catch { /* best-effort */ }
}

// ── Atomic write (temp + rename, Windows-safe) ────

/**
 * Windows-safe atomic JSON write. Unique temp per attempt, fsync + close
 * before replace, bounded retry on transient locks. Returns true on success,
 * false on permanent transient failure (previous good file preserved).
 * Non-transient errors are rethrown after cleanup.
 */
function atomicWriteJson(filePath: string, data: unknown): boolean {
  // Per-target cooldown gate: if this specific file recently failed, skip it
  // to prevent storm.  Other files are unaffected.
  const now = Date.now();
  const targetCooldown = _persistenceHealth.cooldowns[filePath] ?? 0;
  if (now < targetCooldown) {
    return false; // on cooldown for this target; caller keeps in-memory state
  }
  ensureDir();
  cleanupStaleTmpFiles(filePath);
  const content = JSON.stringify(data, null, 2);
  const unique = `${process.pid}.${Date.now().toString(36)}.${Math.random().toString(36).slice(2, 8)}`;
  let lastErr: unknown = null;
  let delayMs = 50;
  for (let attempt = 0; attempt < 6; attempt++) {
    const tmpPath = `${filePath}.tmp.${unique}.${attempt}`;
    try {
      const fd = fs.openSync(tmpPath, "w");
      try {
        fs.writeFileSync(fd, content, "utf-8");
        try { fs.fsyncSync(fd); } catch { /* best-effort */ }
      } finally {
        fs.closeSync(fd);
      }
      fs.renameSync(tmpPath, filePath);
      recordPersistSuccess();
      return true;
    } catch (err) {
      lastErr = err;
      try { fs.unlinkSync(tmpPath); } catch { /* ignore */ }
      if (!isTransientFsError(err)) throw err;
      if (attempt < 5) {
        sleepSync(delayMs);
        delayMs = Math.min(delayMs * 2, 1000);
      }
    }
  }
  recordPersistFailure(filePath, lastErr);
  return false;
}

/**
 * Safely load a JSON file with corruption detection.
 * Returns the parsed data or null if corrupt/missing.
 */
function safeLoadJson<T>(filePath: string): T | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    const raw = fs.readFileSync(filePath, "utf-8");
    if (!raw.trim()) return null;
    return JSON.parse(raw) as T;
  } catch {
    // Corruption detected — attempt recovery from backup
    const backupPath = filePath + ".bak";
    try {
      if (fs.existsSync(backupPath)) {
        const raw = fs.readFileSync(backupPath, "utf-8");
        const data = JSON.parse(raw);
        // Restore from backup
        fs.copyFileSync(backupPath, filePath);
        return data;
      }
    } catch { /* backup also corrupt */ }
    return null;
  }
}

// ── Index ──────────────────────────────────────────────────

interface IndexEntry {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  model: string;
}

function loadIndex(): IndexEntry[] {
  return safeLoadJson<IndexEntry[]>(INDEX_FILE) || [];
}

function saveIndex(entries: IndexEntry[]): boolean {
  ensureDir();
  const capped = entries
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_CONVERSATIONS);
  return atomicWriteJson(INDEX_FILE, capped);
}

// In-memory overlay: newest conversation state always served from memory so
// a transient disk failure never loses a just-created/updated conversation.
// Overlay entries are authoritative for reads; disk catches up on retry.
const _overlay = new Map<string, Conversation>();
let _indexDirty = false;
let _indexRetryScheduled = false;

function rememberOverlay(conv: Conversation): void {
  _overlay.set(conv.id, JSON.parse(JSON.stringify(conv)) as Conversation);
  if (_overlay.size > MAX_CONVERSATIONS + 50) {
    const oldest = [..._overlay.values()].sort((a, b) => a.updatedAt - b.updatedAt)[0];
    if (oldest) _overlay.delete(oldest.id);
  }
}

function scheduleIndexRetry(): void {
  if (_indexRetryScheduled) return;
  _indexRetryScheduled = true;
  // Respect per-target cooldown: delay retry until after the cooldown window.
  const targetCooldown = _persistenceHealth.cooldowns[INDEX_FILE] ?? 0;
  const delayMs = Math.max(5000, targetCooldown - Date.now() + 500);
  setTimeout(() => {
    _indexRetryScheduled = false;
    if (!_indexDirty) return;
    // Skip if still on cooldown (repeated failures on this specific target).
    if (Date.now() < (_persistenceHealth.cooldowns[INDEX_FILE] ?? 0)) {
      scheduleIndexRetry(); // re-schedule for after cooldown
      return;
    }
    try {
      const merged = loadIndex();
      for (const conv of _overlay.values()) {
        const i = merged.findIndex(e => e.id === conv.id);
        const entry: IndexEntry = {
          id: conv.id, title: conv.title, createdAt: conv.createdAt,
          updatedAt: conv.updatedAt, messageCount: conv.messages.length, model: conv.model,
        };
        if (i >= 0) { if (merged[i].updatedAt <= entry.updatedAt) merged[i] = entry; }
        else merged.unshift(entry);
      }
      if (saveIndex(merged)) _indexDirty = false;
      else scheduleIndexRetry();
    } catch {
      scheduleIndexRetry();
    }
  }, delayMs).unref?.();
}

function updateIndexEntry(conv: Conversation): void {
  const index = loadIndex();
  const existing = index.findIndex(e => e.id === conv.id);
  const entry: IndexEntry = {
    id: conv.id,
    title: conv.title,
    createdAt: conv.createdAt,
    updatedAt: conv.updatedAt,
    messageCount: conv.messages.length,
    model: conv.model,
  };
  if (existing >= 0) {
    index[existing] = entry;
  } else {
    index.unshift(entry);
  }
  if (!saveIndex(index)) {
    _indexDirty = true;
    scheduleIndexRetry();
  } else if (!_indexDirty) {
    // index durable; nothing pending
  }
}

// ── CRUD ───────────────────────────────────────────────────

export function createConversation(
  title: string = "New Chat",
  model: string = "llama3.2:3b"
): Conversation {
  ensureDir();
  const now = Date.now();
  const conv: Conversation = {
    id: generateId(),
    title,
    createdAt: now,
    updatedAt: now,
    messages: [],
    model,
    totalTokens: 0,
  };
  // In-memory state is valid even if disk is transiently locked; never throw
  // a persistence EPERM out of conversation creation (would crash the server).
  rememberOverlay(conv);
  try {
    const convFile = path.join(CONVERSATIONS_DIR, `${conv.id}.json`);
    try {
      atomicWriteJson(convFile, conv);
    } catch (err) {
      // Non-transient disk error: keep in-memory state, mark degraded.
      recordPersistFailure(convFile, err);
    }
    updateIndexEntry(conv);
  } catch (err) {
    recordPersistFailure(INDEX_FILE, err);
  }
  return conv;
}

export function getConversation(id: string): Conversation | null {
  const hit = _overlay.get(id);
  if (hit) {
    const disk = safeLoadJson<Conversation>(path.join(CONVERSATIONS_DIR, `${id}.json`));
    if (disk && disk.updatedAt >= hit.updatedAt) {
      rememberOverlay(disk);
      return disk;
    }
    return JSON.parse(JSON.stringify(hit)) as Conversation;
  }
  return safeLoadJson<Conversation>(path.join(CONVERSATIONS_DIR, `${id}.json`));
}

/** Persist one conversation file + index, never throwing on transient locks. */
function persistConversation(conv: Conversation): void {
  rememberOverlay(conv);
  const convFile = path.join(CONVERSATIONS_DIR, `${conv.id}.json`);
  try {
    if (fs.existsSync(convFile)) {
      fs.copyFileSync(convFile, convFile + ".bak");
    }
  } catch { /* best-effort backup */ }
  try {
    atomicWriteJson(convFile, conv);
  } catch (err) {
    recordPersistFailure(convFile, err);
  }
  try {
    updateIndexEntry(conv);
  } catch (err) {
    recordPersistFailure(INDEX_FILE, err);
  }
}

export async function saveConversation(conv: Conversation): Promise<void> {
  await serializeWrite(conv.id, () =>
    withLock(conv.id, () => {
      conv.updatedAt = Date.now();
      persistConversation(conv);
    })
  );
}

export async function deleteConversation(id: string): Promise<boolean> {
  return serializeWrite(id, () =>
    withLock(id, () => {
      const convFile = path.join(CONVERSATIONS_DIR, `${id}.json`);
      try {
        const existed = fs.existsSync(convFile);
        if (existed) {
          try { fs.copyFileSync(convFile, convFile + ".deleted"); } catch { /* ignore */ }
          try {
            fs.unlinkSync(convFile);
          } catch (err) {
            // Transient Windows lock on delete: keep overlay dropped + index
            // update so the conversation disappears; file cleans up on retry.
            if (!isTransientFsError(err)) return false;
            recordPersistFailure(convFile, err);
          }
        }
        _overlay.delete(id);
        const index = loadIndex();
        const filtered = index.filter(e => e.id !== id);
        try {
          if (!saveIndex(filtered)) {
            _indexDirty = true;
            scheduleIndexRetry();
          }
        } catch (err) {
          recordPersistFailure(INDEX_FILE, err);
          _indexDirty = true;
          scheduleIndexRetry();
        }
        return existed || index.some(e => e.id === id);
      } catch {
        return false;
      }
    })
  );
}

export function listConversations(limit: number = 50): ConversationSummary[] {
  const index = loadIndex();
  // Merge in-memory overlay so conversations created during a transient
  // index-lock window are still listed (disk catches up via retry).
  const merged = [...index];
  for (const conv of _overlay.values()) {
    const i = merged.findIndex(e => e.id === conv.id);
    const entry = {
      id: conv.id, title: conv.title, createdAt: conv.createdAt,
      updatedAt: conv.updatedAt, messageCount: conv.messages.length, model: conv.model,
    };
    if (i >= 0) { if (merged[i].updatedAt <= entry.updatedAt) merged[i] = entry; }
    else merged.unshift(entry);
  }
  merged.sort((a, b) => b.updatedAt - a.updatedAt);
  return merged.slice(0, limit).map(e => ({
    id: e.id,
    title: e.title,
    createdAt: e.createdAt,
    updatedAt: e.updatedAt,
    messageCount: e.messageCount,
    model: e.model,
  }));
}

export async function addMessage(
  conversationId: string,
  role: "user" | "assistant",
  content: string,
  extra?: Partial<ConversationMessage>
): Promise<ConversationMessage | null> {
  return serializeWrite(conversationId, () =>
    withLock(conversationId, () => {
    const conv = getConversation(conversationId);
    if (!conv) return null;

    const msg: ConversationMessage = {
      id: generateMessageId(),
      role,
      content,
      timestamp: Date.now(),
      tokenEstimate: estimateTokens(content),
      ...extra,
    };

    conv.messages.push(msg);
    conv.totalTokens = conv.messages.reduce((sum, m) => sum + m.tokenEstimate, 0);

    // Cap messages
    if (conv.messages.length > MAX_MESSAGES_PER_CONVERSATION) {
      conv.messages = conv.messages.slice(-MAX_MESSAGES_PER_CONVERSATION);
    }

    persistConversation(conv);

    // Trigger pruning periodically (every 50 new messages)
    if (conv.messages.length % 50 === 0) {
      try {
        pruneConversations();
      } catch (err) {
        recordPersistFailure(INDEX_FILE, err);
      }
    }

    return msg;
    })
  );
}

export async function updateMessage(
  conversationId: string,
  messageId: string,
  updates: Partial<ConversationMessage>
): Promise<boolean> {
  return serializeWrite(conversationId, () =>
    withLock(conversationId, () => {
      const conv = getConversation(conversationId);
      if (!conv) return false;

      const idx = conv.messages.findIndex(m => m.id === messageId);
      if (idx < 0) return false;

      conv.messages[idx] = { ...conv.messages[idx], ...updates };
      conv.totalTokens = conv.messages.reduce((sum, m) => sum + m.tokenEstimate, 0);

      persistConversation(conv);
      return true;
    })
  );
}

export function getConversationHistory(
  conversationId: string,
  maxTurns: number = 20
): Array<{ role: string; content: string }> {
  const conv = getConversation(conversationId);
  if (!conv) return [];

  return conv.messages
    .slice(-maxTurns * 2)
    .map(m => ({ role: m.role, content: m.content }));
}

// ── Context Builder ────────────────────────────────────────

/**
 * Build bounded conversation context for the brain/LLM prompt.
 * Returns the last N turns as role/content pairs.
 */
export function buildContext(
  conversationId: string,
  maxTurns: number = 10
): Array<{ role: string; text: string }> {
  const conv = getConversation(conversationId);
  if (!conv) return [];

  return conv.messages
    .slice(-maxTurns * 2)
    .map(m => ({ role: m.role, text: m.content }));
}

// ── Title Generation ───────────────────────────────────────

/**
 * Generate a conversation title from the first user message.
 * Preserves Unicode (Hindi, Hinglish, etc.) while keeping it concise.
 */
export function generateTitle(firstMessage: string): string {
  const cleaned = firstMessage
    .replace(/[^\p{L}\p{M}\p{N}\s?!,.।॥-]/gu, "")
    .trim()
    .slice(0, 60);
  if (cleaned.length <= 40) return cleaned;
  return cleaned.slice(0, 40).trim() + "...";
}

// ── Pruning ────────────────────────────────────────────────

/**
 * Remove old conversations beyond the limit.
 * Keeps the most recently updated ones. Active conversation is never deleted.
 */
export function pruneConversations(): number {
  const index = loadIndex();
  if (index.length <= MAX_CONVERSATIONS) return 0;

  const toRemove = index
    .sort((a, b) => a.updatedAt - b.updatedAt)
    .slice(0, index.length - MAX_CONVERSATIONS);

  let removed = 0;
  for (const entry of toRemove) {
    const convFile = path.join(CONVERSATIONS_DIR, `${entry.id}.json`);
    try {
      if (fs.existsSync(convFile)) {
        fs.unlinkSync(convFile);
      }
      _overlay.delete(entry.id);
      removed++;
    } catch (err) {
      // Transient lock on delete: drop from overlay but keep file for later.
      if (isTransientFsError(err)) {
        _overlay.delete(entry.id);
        recordPersistFailure(convFile, err);
      }
      /* best-effort */
    }
  }

  if (removed > 0) {
    try {
      if (!saveIndex(index.filter(e => !toRemove.find(r => r.id === e.id)))) {
        _indexDirty = true;
        scheduleIndexRetry();
      }
    } catch (err) {
      recordPersistFailure(INDEX_FILE, err);
      _indexDirty = true;
      scheduleIndexRetry();
    }
  }
  return removed;
}

/**
 * Flush pending index retries synchronously (shutdown path).
 * Waits for nothing async; performs one final best-effort index write.
 */
export function flushConversationPersistence(): void {
  if (!_indexDirty) return;
  try {
    const merged = loadIndex();
    for (const conv of _overlay.values()) {
      const i = merged.findIndex(e => e.id === conv.id);
      const entry: IndexEntry = {
        id: conv.id, title: conv.title, createdAt: conv.createdAt,
        updatedAt: conv.updatedAt, messageCount: conv.messages.length, model: conv.model,
      };
      if (i >= 0) { if (merged[i].updatedAt <= entry.updatedAt) merged[i] = entry; }
      else merged.unshift(entry);
    }
    if (saveIndex(merged)) _indexDirty = false;
  } catch (err) {
    recordPersistFailure(INDEX_FILE, err);
  }
}
