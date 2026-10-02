import {
  createConversation,
  getConversation,
  listConversations,
  deleteConversation,
  addMessage,
  buildContext,
  generateTitle,
  pruneConversations,
  type Conversation,
} from "../../server_conversations";
import { callBrain } from "../../services/desktop/desktop_agent";
import { DESKTOP_AGENT_URL } from "../../services/desktop/desktop_agent";
import { handleRequest, handleStreamRequest, type UnifiedEvent } from "../../src/core/unified_handler";
import { classifyInput } from "../../src/core/context_assembler";
// Canonical response fan-out (§11/26): typed responses auto-speak when a
// voice session is active. No-op when voice is off — same TTS path as voice.
import { speakTextToVoiceSessions } from "../../server_voice";
import type { ServerContext } from "./types";

export function registerConversationRoutes(app: any, ctx: ServerContext) {
  app.get("/api/conversations", (_req: any, res: any) => {
    try {
      const limit = parseInt(_req.query.limit as string) || 50;
      res.json(listConversations(limit));
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.post("/api/conversations", (req: any, res: any) => {
    try {
      const { title, model } = req.body || {};
      const conv = createConversation(title || "New Chat", model || "llama3.2:3b");
      res.status(201).json(conv);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.get("/api/conversations/:id", (req: any, res: any) => {
    try {
      const conv = getConversation(req.params.id);
      if (!conv) return res.status(404).json({ error: "Conversation not found" });
      res.json(conv);
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.delete("/api/conversations/:id", async (req: any, res: any) => {
    try {
      const ok = await deleteConversation(req.params.id);
      if (!ok) return res.status(404).json({ error: "Conversation not found" });
      res.json({ success: true });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });
}

export function registerChatRoutes(app: any, ctx: ServerContext) {
  app.post("/api/chat", async (req: any, res: any) => {
    try {
      const { text, context } = req.body;
      if (!text || typeof text !== "string") {
        return res.status(400).json({ error: "text is required" });
      }

      // Use unified handler for all chat requests
      const result = await handleRequest({
        text,
        inputType: 'text',
        conversationHistory: context?.conversation_history,
      });

      res.json({
        ok: true,
        result: result.response,
        requestId: result.requestId,
        route: result.route,
        model: result.model,
        classification: result.classification,
        latencyMs: result.latencyMs,
      });
    } catch (e: any) {
      res.status(502).json({ error: "Brain service unavailable", detail: e.message });
    }
  });

  const activeStreams = new Map<string, AbortController>();

  app.post("/api/chat/stream", async (req: any, res: any) => {
    const { text, conversationId, model } = req.body || {};
    if (!text || typeof text !== "string") {
      return res.status(400).json({ error: "text is required" });
    }

    let convId = conversationId;
    let conv: Conversation | null = convId ? getConversation(convId) : null;
    if (!conv) {
      conv = createConversation(generateTitle(text), model || "llama3.2:3b");
      convId = conv.id;
    }

    await addMessage(convId, "user", text);

    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.setHeader("X-Accel-Buffering", "no");
    res.flushHeaders();

    res.write(JSON.stringify({ type: "conversation_id", id: convId }) + "\n");

    const abortController = new AbortController();
    activeStreams.set(convId, abortController);

    try {
      const history = buildContext(convId, 10);

      // Unified handler: classify → route → execute
      const classification = classifyInput(text);
      const isComplexTask = ['VISION', 'COMPUTER_ACTION', 'AGENT_TASK', 'FILE_OPERATION', 'RESEARCH', 'FINANCE', 'QUANT'].includes(classification);

      if (isComplexTask) {
        // Complex tasks: use unified handler (agent path)
        const result = await handleRequest({
          text,
          inputType: 'text',
          conversationId: convId,
          conversationHistory: history,
          model,
          abortSignal: abortController.signal,
        });

        await addMessage(convId, "assistant", result.response);
        res.write(JSON.stringify({ type: "metadata", route: result.route, model: result.model, intent: result.classification, latencyMs: result.latencyMs }) + "\n");
        res.write(JSON.stringify({ type: "done", text: result.response }) + "\n");
        res.end();
        activeStreams.delete(convId);
        speakTextToVoiceSessions(result.response);
        return;
      }

      // Phase 29.7: ALL requests flow through the unified streaming handler.
      // Simple conversation streams through the brain fast path internally;
      // complex tasks use the agent path. No direct /brain/stream bypass.
      let fullResponse = "";

      for await (const event of handleStreamRequest({
        text,
        inputType: 'text',
        conversationId: convId,
        conversationHistory: history,
        model,
        abortSignal: abortController.signal,
      })) {
        const e = event as UnifiedEvent;
        if (e.type === "metadata") {
          res.write(JSON.stringify({ type: "metadata", route: e.route, model: e.model, intent: e.intent, requestId: e.requestId }) + "\n");
        } else if (e.type === "chunk" && e.text) {
          fullResponse += e.text;
          res.write(JSON.stringify({ type: "chunk", text: e.text }) + "\n");
        } else if (e.type === "error") {
          res.write(JSON.stringify({ type: "error", message: e.message }) + "\n");
        } else if (e.type === "done") {
          if (e.text) fullResponse = e.text;
          if (e.aborted) {
            res.write(JSON.stringify({ type: "done", text: fullResponse, aborted: true }) + "\n");
            break;
          }
        }
      }

      if (fullResponse.trim()) {
        await addMessage(convId, "assistant", fullResponse);
        speakTextToVoiceSessions(fullResponse);
      }

      res.write(JSON.stringify({ type: "done", text: fullResponse }) + "\n");
      res.end();
    } catch (e: any) {
      if (e.name === "AbortError") {
        res.write(JSON.stringify({ type: "done", text: "", aborted: true }) + "\n");
      } else {
        ctx.logError(`CHAT_STREAM_ERROR: ${e.message}`);
        res.write(JSON.stringify({ type: "error", message: e.message }) + "\n");
        res.write(JSON.stringify({ type: "done", text: "" }) + "\n");
      }
      res.end();
    } finally {
      activeStreams.delete(convId);
    }
  });

  app.post("/api/chat/cancel", (req: any, res: any) => {
    const { conversationId } = req.body || {};
    if (!conversationId) {
      return res.status(400).json({ error: "conversationId is required" });
    }
    const ctrl = activeStreams.get(conversationId);
    if (ctrl) {
      ctrl.abort();
      activeStreams.delete(conversationId);
      res.json({ success: true });
    } else {
      res.json({ success: false, message: "No active stream" });
    }
  });

  app.post("/api/chat/regenerate", async (req: any, res: any) => {
    const { conversationId } = req.body || {};
    if (!conversationId) {
      return res.status(400).json({ error: "conversationId is required" });
    }
    const conv = getConversation(conversationId);
    if (!conv || conv.messages.length === 0) {
      return res.status(404).json({ error: "Conversation not found or empty" });
    }

    const lastMsg = conv.messages[conv.messages.length - 1];
    if (lastMsg.role === "assistant") {
      conv.messages.pop();
      conv.totalTokens = conv.messages.reduce((sum, m) => sum + m.tokenEstimate, 0);
    }

    const lastUserMsg = conv.messages.filter(m => m.role === "user").pop();
    if (!lastUserMsg) {
      return res.status(400).json({ error: "No user message to regenerate from" });
    }

    req.body = { text: lastUserMsg.content, conversationId };
    return (app as any)._router.handle(req, res);
  });
}
