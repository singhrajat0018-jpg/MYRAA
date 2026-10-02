import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import fs from "fs";
import path from "path";
import os from "os";

// Expose a hook so tests can force transient rename failures deterministically.
// server_memory reads this global on each atomic-write attempt.
declare global {
  // eslint-disable-next-line no-var
  var __MYRAA_TEST_FORCE_RENAME_EPERM: ((dest: string) => boolean) | undefined;
}

const TEST_DIR = path.join(os.tmpdir(), `myraa-persist-win-${Date.now()}-${Math.random().toString(36).slice(2)}`);

vi.mock("../server_paths", () => ({
  DATA_DIR: TEST_DIR,
  dataFile: (name: string) => path.join(TEST_DIR, name),
}));

let conversations: typeof import("../server_conversations");
let memory: typeof import("../server_memory");

beforeEach(async () => {
  fs.mkdirSync(TEST_DIR, { recursive: true });
  vi.resetModules();
  conversations = await import("../server_conversations");
  memory = await import("../server_memory");
});

afterEach(() => {
  fs.rmSync(TEST_DIR, { recursive: true, force: true });
  vi.resetModules();
});

describe("Windows failure injection: conversation store", () => {
  it("survives EPERM on index rename: no throw, health DEGRADED, data listed", () => {
    const origRename = fs.renameSync;
    const spy = vi.spyOn(fs, "renameSync").mockImplementation(((a: any, b: any) => {
      if (String(b).endsWith("_index.json")) {
        const e: any = new Error("EPERM: operation not permitted, rename");
        e.code = "EPERM";
        throw e;
      }
      return origRename(a, b);
    }) as any);
    try {
      const conv = conversations.createConversation("EPERM test");
      expect(conv.id).toMatch(/^conv_/);
      // In-memory overlay keeps it visible even though index disk write failed.
      expect(conversations.listConversations(10).some(c => c.id === conv.id)).toBe(true);
      expect(conversations.getConversation(conv.id)).not.toBeNull();
      const health = conversations.getConversationPersistenceHealth();
      expect(health.status).toBe("DEGRADED");
      expect(health.lastErrorCode).toBe("EPERM");
    } finally {
      spy.mockRestore();
    }
    // After the lock clears, a new conversation heals the store.
    // Per-target cooldown: index is cooled down but conversation files are not,
    // so conv2 file writes succeed. Then the index write also succeeds (mock
    // removed), healing the status to HEALTHY.
    const conv2 = conversations.createConversation("recovery");
    expect(conversations.getConversationPersistenceHealth().status).toBe("HEALTHY");
    expect(conversations.getConversation(conv2.id)).not.toBeNull();
  });

  it("rapid concurrent creates never throw and never corrupt the index", async () => {
    const made = Array.from({ length: 20 }, (_, i) => conversations.createConversation(`Rapid ${i}`));
    expect(made.length).toBe(20);
    const listed = conversations.listConversations(50);
    expect(listed.length).toBe(20);
    const raw = fs.readFileSync(path.join(TEST_DIR, "conversations", "_index.json"), "utf-8");
    const parsed = JSON.parse(raw);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed.length).toBe(20);
  });

  it("rapid concurrent message writes keep every message", async () => {
    const conv = conversations.createConversation("Concurrent msgs");
    await Promise.all(Array.from({ length: 15 }, (_, i) => conversations.addMessage(conv.id, "user", `M${i}`)));
    expect(conversations.getConversation(conv.id)!.messages.length).toBe(15);
  });

  it("data survives a simulated restart (fresh module import)", async () => {
    const conv = conversations.createConversation("Restart me");
    await conversations.addMessage(conv.id, "user", "hello");
    vi.resetModules();
    const fresh: typeof import("../server_conversations") = await import("../server_conversations");
    const found = fresh.getConversation(conv.id);
    expect(found).not.toBeNull();
    expect(found!.messages.length).toBe(1);
  });

  it("no stale .tmp files remain after successful writes", () => {
    conversations.createConversation("tmp check");
    const dir = path.join(TEST_DIR, "conversations");
    const leftovers = fs.readdirSync(dir).filter(f => f.includes(".tmp."));
    expect(leftovers).toEqual([]);
  });
});

describe("Windows failure injection: memory store", () => {
  it("survives EPERM on rename: no throw, health DEGRADED, recovers", async () => {
    globalThis.__MYRAA_TEST_FORCE_RENAME_EPERM = (dest: string) => dest.endsWith("memories.json");
    try {
      await memory.saveMemories([{ id: "m1", category: "identity", text: "hello", createdAt: "x", updatedAt: "x" } as any]);
      const health = memory.getMemoryPersistenceHealth();
      expect(health.status).toBe("DEGRADED");
      expect(health.lastErrorCode).toBe("EPERM");
    } finally {
      globalThis.__MYRAA_TEST_FORCE_RENAME_EPERM = undefined;
    }
    await memory.saveMemories([{ id: "m1", category: "identity", text: "hello", createdAt: "x", updatedAt: "x" } as any]);
    expect(memory.getMemoryPersistenceHealth().status).toBe("HEALTHY");
    expect(await memory.loadMemories()).toHaveLength(1);
  });
});
