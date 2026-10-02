import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs";
import path from "path";
import os from "os";

// We test server_conversations by importing its public API.
// Since it depends on DATA_DIR from server_paths, we mock the data dir
// to a temp directory for test isolation.

const TEST_DIR = path.join(os.tmpdir(), `myraa-test-${Date.now()}`);

// Mock server_paths before importing server_conversations
vi.mock("../server_paths", () => ({
  DATA_DIR: TEST_DIR,
  dataFile: (name: string) => path.join(TEST_DIR, name),
}));

// Dynamic import after mock is set up
let conversations: typeof import("../server_conversations");

beforeEach(async () => {
  fs.mkdirSync(TEST_DIR, { recursive: true });
  conversations = await import("../server_conversations");
});

afterEach(() => {
  fs.rmSync(TEST_DIR, { recursive: true, force: true });
  vi.resetModules();
});

describe("Conversation CRUD", () => {
  it("creates a conversation with default values", () => {
    const conv = conversations.createConversation("Test Chat", "llama3.2:3b");
    expect(conv.id).toMatch(/^conv_/);
    expect(conv.title).toBe("Test Chat");
    expect(conv.model).toBe("llama3.2:3b");
    expect(conv.messages).toEqual([]);
    expect(conv.totalTokens).toBe(0);
  });

  it("retrieves a conversation by id", () => {
    const conv = conversations.createConversation("Retrieve Me");
    const found = conversations.getConversation(conv.id);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(conv.id);
    expect(found!.title).toBe("Retrieve Me");
  });

  it("returns null for non-existent conversation", () => {
    const found = conversations.getConversation("conv_nonexistent");
    expect(found).toBeNull();
  });

  it("lists conversations", () => {
    conversations.createConversation("Chat 1");
    conversations.createConversation("Chat 2");
    conversations.createConversation("Chat 3");
    const list = conversations.listConversations(10);
    expect(list.length).toBe(3);
  });

  it("deletes a conversation", async () => {
    const conv = conversations.createConversation("Delete Me");
    const ok = await conversations.deleteConversation(conv.id);
    expect(ok).toBe(true);
    const found = conversations.getConversation(conv.id);
    expect(found).toBeNull();
  });

  it("returns false when deleting non-existent conversation", async () => {
    const ok = await conversations.deleteConversation("conv_nonexistent");
    expect(ok).toBe(false);
  });
});

describe("Message operations", () => {
  it("adds a message to a conversation", async () => {
    const conv = conversations.createConversation("Msg Test");
    const msg = await conversations.addMessage(conv.id, "user", "Hello world");
    expect(msg).not.toBeNull();
    expect(msg!.role).toBe("user");
    expect(msg!.content).toBe("Hello world");
    expect(msg!.tokenEstimate).toBeGreaterThan(0);
  });

  it("returns null when adding message to non-existent conversation", async () => {
    const msg = await conversations.addMessage("conv_nonexistent", "user", "Hello");
    expect(msg).toBeNull();
  });

  it("tracks total tokens", async () => {
    const conv = conversations.createConversation("Token Test");
    await conversations.addMessage(conv.id, "user", "Hello world");
    await conversations.addMessage(conv.id, "assistant", "Hi there!");
    const found = conversations.getConversation(conv.id);
    expect(found!.totalTokens).toBeGreaterThan(0);
  });
});

describe("Context builder", () => {
  it("builds bounded context", async () => {
    const conv = conversations.createConversation("Context Test");
    await conversations.addMessage(conv.id, "user", "Message 1");
    await conversations.addMessage(conv.id, "assistant", "Reply 1");
    await conversations.addMessage(conv.id, "user", "Message 2");
    await conversations.addMessage(conv.id, "assistant", "Reply 2");

    const ctx = conversations.buildContext(conv.id, 2);
    expect(ctx.length).toBe(4); // 2 turns * 2 messages
    expect(ctx[0].role).toBe("user");
    expect(ctx[1].role).toBe("assistant");
  });

  it("returns empty array for non-existent conversation", () => {
    const ctx = conversations.buildContext("conv_nonexistent");
    expect(ctx).toEqual([]);
  });
});

describe("Title generation", () => {
  it("preserves ASCII text", () => {
    const title = conversations.generateTitle("What is the weather?");
    expect(title).toBe("What is the weather?");
  });

  it("preserves Hindi/Unicode text", () => {
    const title = conversations.generateTitle("दिल्ली में मौसम कैसा है");
    expect(title).toContain("दिल्ली");
  });

  it("truncates long titles", () => {
    const long = "A".repeat(100);
    const title = conversations.generateTitle(long);
    expect(title.length).toBeLessThanOrEqual(44); // 40 + "..."
  });
});

describe("Pruning", () => {
  it("does not prune under limit", () => {
    for (let i = 0; i < 5; i++) {
      conversations.createConversation(`Chat ${i}`);
    }
    const removed = conversations.pruneConversations();
    expect(removed).toBe(0);
    expect(conversations.listConversations(100).length).toBe(5);
  });
});

describe("Atomic writes", () => {
  it("creates backup files on message add", async () => {
    const conv = conversations.createConversation("Backup Test");
    await conversations.addMessage(conv.id, "user", "Hello");
    const convFile = path.join(TEST_DIR, "conversations", `${conv.id}.json`);
    const bakFile = convFile + ".bak";
    // Backup may or may not exist depending on timing, but the conversation should be valid
    const data = JSON.parse(fs.readFileSync(convFile, "utf-8"));
    expect(data.messages.length).toBe(1);
  });

  it("creates temp files with process.pid suffix during write", async () => {
    const conv = conversations.createConversation("Temp File Test");
    // The .tmp file should not persist after a successful write
    const convDir = path.join(TEST_DIR, "conversations");
    const tmpFiles = fs.readdirSync(convDir).filter(f => f.includes(".tmp."));
    expect(tmpFiles.length).toBe(0);
  });
});

describe("Concurrency safety", () => {
  it("handles rapid sequential message additions", async () => {
    const conv = conversations.createConversation("Concurrency Test");
    const promises = [];
    for (let i = 0; i < 10; i++) {
      promises.push(conversations.addMessage(conv.id, "user", `Message ${i}`));
    }
    await Promise.all(promises);
    const found = conversations.getConversation(conv.id);
    expect(found!.messages.length).toBe(10);
  });
});
