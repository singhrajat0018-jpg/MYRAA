/**
 * MYRAA API Client
 *
 * Typed client for all Node backend endpoints.
 * All calls go through Node (port 3000) which proxies to Python.
 * API keys never leave the server.
 */

const TIMEOUT = 15000;

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT);
  try {
    const r = await fetch(path, { ...options, signal: ctrl.signal });
    clearTimeout(timer);
    if (!r.ok) {
      const err = await r.text().catch(() => r.statusText);
      throw new Error(`API ${r.status}: ${err}`);
    }
    return r.json();
  } catch (e: any) {
    clearTimeout(timer);
    if (e.name === "AbortError") throw new Error("Request timed out");
    throw e;
  }
}

// ── Memories ─────────────────────────────────────────────────

export interface Memory {
  id: string;
  category: string;
  text: string;
  importance: number;
  created_at: string;
  updated_at: string;
}

export const memoriesApi = {
  list: () => apiFetch<Memory[]>("/api/memories"),
  add: (category: string, text: string) =>
    apiFetch<{ success: boolean }>("/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, text }),
    }),
  delete: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/memories/${id}`, { method: "DELETE" }),
};

// ── Settings ─────────────────────────────────────────────────

export const settingsApi = {
  get: () => apiFetch<Record<string, unknown>>("/api/settings"),
  // POST /api/settings returns the merged settings object (not a {success}).
  update: (patch: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
};

// ── Config ───────────────────────────────────────────────────

export const configApi = {
  check: () =>
    apiFetch<{
      hasApiKey: boolean;
      mode?: string;
      providers?: { gemini: boolean; tavily: boolean };
    }>("/api/config"),
  // Field name MUST be `apiKey` — that is what the server reads; sending `key`
  // silently stored nothing and surfaced as "API key is required".
  // `name` selects which server-side key to write (defaults to GEMINI_API_KEY).
  setApiKey: (key: string, name: "GEMINI_API_KEY" | "TAVILY_API_KEY" = "GEMINI_API_KEY") =>
    apiFetch<{ success: boolean; requiresRestart?: boolean; error?: string }>(
      "/api/config/apikey",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: key, name }),
      },
    ),
};

// ── Agent Health ─────────────────────────────────────────────

export interface AgentHealth {
  online: boolean;
  tool_count?: number;
  version?: string;
  system?: { cpu_percent: number; ram_percent: number; disk_usage_percent: number };
}

export const agentApi = {
  health: () => apiFetch<AgentHealth>("/api/agent-health"),
};

// ── Trading ──────────────────────────────────────────────────

export const tradingApi = {
  health: () => apiFetch<unknown>("/api/trading/health"),
  portfolio: () => apiFetch<unknown>("/api/groww/portfolio"),
  analyze: () => apiFetch<unknown>("/api/groww/analyze"),
  alerts: (limit = 30) => apiFetch<unknown>(`/api/trading/alerts?limit=${limit}`),
  stock: (symbol: string) => apiFetch<unknown>(`/api/groww/stock/${symbol}`),
};

// ── Chat ─────────────────────────────────────────────────────

export interface ChatResponse {
  response?: string;
  text?: string;
  result?: string;
  route?: string;
  tool?: string;
  success?: boolean;
}

export const chatApi = {
  send: (text: string, context?: Record<string, unknown>) =>
    apiFetch<ChatResponse>("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, context }),
    }),
};

// ── Conversations ───────────────────────────────────────────

export interface ConversationSummary {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  model: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  tokenEstimate: number;
  toolCalls?: Array<{ name: string; args: Record<string, unknown>; result?: string }>;
  metadata?: Record<string, unknown>;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ConversationMessage[];
  model: string;
  totalTokens: number;
}

export interface StreamEvent {
  type: "conversation_id" | "chunk" | "done" | "error" | "metadata";
  id?: string;
  text?: string;
  message?: string;
  aborted?: boolean;
  intent?: string;
  complexity?: string;
  model_route?: string;
  confidence?: number;
  fastcore_latency_ms?: number;
  provider?: string;
  model?: string;
  total_latency_ms?: number;
  data?: unknown;
  sources?: Array<{ title: string; url: string }>;
}

export const conversationsApi = {
  list: (limit = 50) =>
    apiFetch<ConversationSummary[]>(`/api/conversations?limit=${limit}`),

  get: (id: string) =>
    apiFetch<Conversation>(`/api/conversations/${id}`),

  create: (title?: string, model?: string) =>
    apiFetch<Conversation>("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, model }),
    }),

  delete: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/conversations/${id}`, { method: "DELETE" }),
};

// ── Streaming Chat ──────────────────────────────────────────

export interface StreamCallbacks {
  onChunk: (text: string) => void;
  onDone: (fullText: string, aborted?: boolean) => void;
  onError: (message: string) => void;
  onConversationId: (id: string) => void;
  onMetadata?: (metadata: Partial<StreamEvent>) => void;
}

/**
 * Send a message and receive a streaming response via SSE.
 * Returns an AbortController for cancellation.
 */
export function streamChat(
  text: string,
  callbacks: StreamCallbacks,
  conversationId?: string,
): AbortController {
  const ctrl = new AbortController();

  (async () => {
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, conversationId }),
        signal: ctrl.signal,
      });

      if (!response.ok) {
        callbacks.onError(`Server returned ${response.status}`);
        callbacks.onDone("");
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError("No response body");
        callbacks.onDone("");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event: StreamEvent = JSON.parse(line);
            switch (event.type) {
              case "conversation_id":
                if (event.id) callbacks.onConversationId(event.id);
                break;
              case "chunk":
                if (event.text) callbacks.onChunk(event.text);
                break;
              case "done":
                callbacks.onDone(event.text || "", event.aborted);
                break;
              case "error":
                callbacks.onError(event.message || "Unknown error");
                break;
              case "metadata":
                if (callbacks.onMetadata) callbacks.onMetadata(event);
                break;
            }
          } catch { /* skip malformed lines */ }
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        try {
          const event: StreamEvent = JSON.parse(buffer);
          if (event.type === "done") {
            callbacks.onDone(event.text || "", event.aborted);
          }
        } catch { /* ignore */ }
      }
    } catch (e: any) {
      if (e.name === "AbortError") {
        callbacks.onDone("", true);
      } else {
        callbacks.onError(e.message || "Stream failed");
        callbacks.onDone("");
      }
    }
  })();

  return ctrl;
}

/**
 * Cancel an active stream.
 */
export async function cancelStream(conversationId: string): Promise<void> {
  try {
    await fetch("/api/chat/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversationId }),
    });
  } catch { /* best-effort */ }
}

// ── Telemetry ────────────────────────────────────────────────

export const telemetryApi = {
  stream: (count = 20) => apiFetch<{ events: unknown[] }>(`/api/telemetry/stream?count=${count}`),
  status: () => apiFetch<unknown>("/api/telemetry/status"),
};

// ── Logs ─────────────────────────────────────────────────────

export const logsApi = {
  get: (file: "commands" | "startup" | "errors") =>
    apiFetch<{ lines: string[] }>(`/api/logs/${file}`),
};
