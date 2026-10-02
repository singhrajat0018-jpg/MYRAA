import { useState, useRef, useEffect, useCallback } from "react";
import {
  Settings, Maximize2, Send, Mic, MicOff, Square, RotateCcw,
  Plus, MessageSquare, Trash2, ChevronLeft, Pencil, Check, X,
  Loader2, Copy, CheckCheck,
} from "lucide-react";
import {
  streamChat, cancelStream, conversationsApi,
  type ConversationSummary, type ConversationMessage,
} from "../core/api";

interface ChatPanelProps {
  voiceState: string;
  userCaption: string;
  modelCaption: string;
  onSendMessage: (text: string) => void;
  onToggleVoice: () => void;
  onMetadata?: (metadata: Record<string, unknown>) => void;
}

type DisplayMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  isStreaming?: boolean;
  isPending?: boolean;
  error?: boolean;
};

export function ChatPanel({
  voiceState,
  userCaption,
  modelCaption,
  onSendMessage,
  onToggleVoice,
  onMetadata,
}: ChatPanelProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamAbort, setStreamAbort] = useState<AbortController | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [editingMsgId, setEditingMsgId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const streamTextRef = useRef("");

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load conversation list on mount
  useEffect(() => {
    conversationsApi.list().then(setConversations).catch(() => {});
  }, []);

  // Load conversation messages when active conversation changes
  useEffect(() => {
    if (!activeConvId) {
      setMessages([{
        id: "welcome",
        role: "assistant",
        content: "Hello Rajat! I'm MYRAA, your AI assistant. How can I help you today?",
        timestamp: Date.now(),
      }]);
      return;
    }
    conversationsApi.get(activeConvId).then(conv => {
      if (conv?.messages) {
        setMessages(conv.messages.map(m => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        })));
      }
    }).catch(() => {});
  }, [activeConvId]);

  // Sync voice captions to messages
  useEffect(() => {
    if (userCaption) {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === "user" && last.content === userCaption) return prev;
        return [...prev, {
          id: `user-${Date.now()}`,
          role: "user",
          content: userCaption,
          timestamp: Date.now(),
        }];
      });
    }
  }, [userCaption]);

  useEffect(() => {
    if (modelCaption) {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.id.startsWith("model-")) {
          return prev.map(m => m.id === last.id ? { ...m, content: modelCaption } : m);
        }
        return [...prev, {
          id: `model-${Date.now()}`,
          role: "assistant",
          content: modelCaption,
          timestamp: Date.now(),
        }];
      });
    }
  }, [modelCaption]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    // Add user message
    const userMsg: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput("");

    // Add placeholder for streaming response
    const assistantMsgId = `assistant-${Date.now()}`;
    const assistantMsg: DisplayMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: Date.now(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, assistantMsg]);
    setIsStreaming(true);
    streamTextRef.current = "";

    // Start streaming
    const ctrl = streamChat(text, {
      onConversationId: (id) => {
        if (!activeConvId) {
          setActiveConvId(id);
          // Refresh conversation list
          conversationsApi.list().then(setConversations).catch(() => {});
        }
      },
      onMetadata: (meta) => {
        if (onMetadata) onMetadata(meta);
      },
      onChunk: (chunk) => {
        streamTextRef.current += chunk;
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: streamTextRef.current }
            : m
        ));
      },
      onDone: (fullText, aborted) => {
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: fullText || streamTextRef.current, isStreaming: false, isPending: false }
            : m
        ));
        setIsStreaming(false);
        setStreamAbort(null);
        streamTextRef.current = "";
        // Refresh conversation list
        conversationsApi.list().then(setConversations).catch(() => {});
      },
      onError: (message) => {
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: `Error: ${message}`, isStreaming: false, error: true }
            : m
        ));
        setIsStreaming(false);
        setStreamAbort(null);
      },
    }, activeConvId || undefined);
    setStreamAbort(ctrl);
  }, [input, isStreaming, activeConvId]);

  const handleStop = useCallback(() => {
    if (streamAbort) {
      streamAbort.abort();
      if (activeConvId) cancelStream(activeConvId);
      setIsStreaming(false);
      setStreamAbort(null);
      setMessages(prev => prev.map(m =>
        m.isStreaming ? { ...m, isStreaming: false } : m
      ));
    }
  }, [streamAbort, activeConvId]);

  const handleRegenerate = useCallback(() => {
    if (isStreaming || !activeConvId) return;
    // Remove last assistant message
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant") {
        return prev.slice(0, -1);
      }
      return prev;
    });
    // Re-send the last user message
    const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
    if (lastUserMsg) {
      setInput(lastUserMsg.content);
      // Trigger send after a tick
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  }, [isStreaming, activeConvId, messages]);

  const handleNewChat = useCallback(() => {
    setActiveConvId(null);
    setMessages([{
      id: "welcome",
      role: "assistant",
      content: "Hello Rajat! I'm MYRAA, your AI assistant. How can I help you today?",
      timestamp: Date.now(),
    }]);
    setShowHistory(false);
  }, []);

  const handleDeleteConversation = useCallback(async (id: string) => {
    await conversationsApi.delete(id).catch(() => {});
    setConversations(prev => prev.filter(c => c.id !== id));
    if (activeConvId === id) handleNewChat();
  }, [activeConvId, handleNewChat]);

  const handleCopyMessage = useCallback((content: string, id: string) => {
    navigator.clipboard.writeText(content).catch(() => {});
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }, []);

  const handleEditStart = useCallback((msg: DisplayMessage) => {
    setEditingMsgId(msg.id);
    setEditContent(msg.content);
  }, []);

  const handleEditSave = useCallback(() => {
    if (!editingMsgId || !editContent.trim()) return;
    setMessages(prev => prev.map(m =>
      m.id === editingMsgId ? { ...m, content: editContent.trim() } : m
    ));
    setEditingMsgId(null);
    setEditContent("");
  }, [editingMsgId, editContent]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) return;
      handleSend();
    }
  };

  const isVoiceActive = voiceState !== "disconnected";

  return (
    <div
      className="flex h-full rounded-xl overflow-hidden"
      style={{
        background: "var(--color-bg-panel)",
        border: "1px solid var(--color-border-primary)",
      }}
    >
      {/* Conversation History Sidebar */}
      {showHistory && (
        <div
          className="flex flex-col border-r"
          style={{
            width: 220,
            borderColor: "var(--color-border-secondary)",
            background: "rgba(0, 0, 0, 0.2)",
          }}
        >
          <div className="flex items-center justify-between px-3 py-2 border-b" style={{ borderColor: "var(--color-border-secondary)" }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-primary)", letterSpacing: "0.1em" }}>
              HISTORY
            </span>
            <button
              onClick={handleNewChat}
              className="p-1 rounded hover:bg-white/5"
              style={{ color: "var(--color-text-accent)" }}
              title="New chat"
            >
              <Plus size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversations.length === 0 && (
              <div style={{ fontSize: 10, color: "var(--color-text-muted)", textAlign: "center", padding: "16px 0" }}>
                No conversations yet
              </div>
            )}
            {conversations.map(conv => (
              <div
                key={conv.id}
                className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer group transition-colors"
                style={{
                  background: conv.id === activeConvId ? "var(--color-border-primary)" : "transparent",
                  border: conv.id === activeConvId ? "1px solid rgba(0, 212, 255, 0.2)" : "1px solid transparent",
                }}
                onClick={() => { setActiveConvId(conv.id); setShowHistory(false); }}
              >
                <MessageSquare size={12} style={{ color: "var(--color-text-muted)", flexShrink: 0 }} />
                <span
                  className="flex-1 truncate"
                  style={{ fontSize: 11, color: conv.id === activeConvId ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}
                >
                  {conv.title}
                </span>
                <button
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-500/20"
                  onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }}
                  style={{ color: "var(--color-status-error)" }}
                >
                  <Trash2 size={10} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-2 border-b"
          style={{ borderColor: "var(--color-border-secondary)" }}
        >
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="p-1.5 rounded-md hover:bg-white/5"
              style={{ color: showHistory ? "var(--color-text-accent)" : "var(--color-text-muted)" }}
              title="Toggle history"
            >
              {showHistory ? <ChevronLeft size={14} /> : <MessageSquare size={14} />}
            </button>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.12em",
                color: "var(--color-text-primary)",
                fontFamily: '"Space Grotesk", sans-serif',
              }}
            >
              {activeConvId ? "MYRAA CHAT" : "NEW CHAT"}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleNewChat}
              className="p-1.5 rounded-md hover:bg-white/5"
              style={{ color: "var(--color-text-muted)" }}
              title="New chat"
            >
              <Plus size={13} />
            </button>
            <button className="p-1.5 rounded-md hover:bg-white/5" style={{ color: "var(--color-text-muted)" }}>
              <Settings size={13} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] ${msg.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}`}
                style={{ position: "relative" }}
              >
                {msg.role === "assistant" && (
                  <div className="flex items-center gap-1.5 mb-1">
                    <div
                      style={{
                        width: 20,
                        height: 20,
                        borderRadius: "50%",
                        background: "rgba(0, 212, 255, 0.15)",
                        border: "1px solid rgba(0, 212, 255, 0.3)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 8,
                        color: "var(--color-text-accent)",
                        fontWeight: 700,
                      }}
                    >
                      AI
                    </div>
                  </div>
                )}

                {editingMsgId === msg.id ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleEditSave(); if (e.key === "Escape") setEditingMsgId(null); }}
                      className="flex-1 bg-transparent outline-none px-2 py-1 rounded"
                      style={{ fontSize: 12, color: "var(--color-text-primary)", border: "1px solid rgba(0, 212, 255, 0.3)" }}
                      autoFocus
                    />
                    <button onClick={handleEditSave} style={{ color: "var(--color-text-accent)" }}><Check size={14} /></button>
                    <button onClick={() => setEditingMsgId(null)} style={{ color: "var(--color-status-error)" }}><X size={14} /></button>
                  </div>
                ) : (
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      {msg.isStreaming && !msg.content && (
                        <div className="flex items-center gap-2" style={{ color: "var(--color-text-muted)" }}>
                          <Loader2 size={12} className="animate-spin" />
                          <span style={{ fontSize: 12 }}>Thinking...</span>
                        </div>
                      )}
                      <div
                        style={{
                          fontSize: 12,
                          lineHeight: "1.6",
                          color: msg.role === "user" ? "var(--color-text-primary)" : "var(--color-text-primary)",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                        }}
                      >
                        {msg.content}
                        {msg.isStreaming && (
                          <span className="inline-block w-1.5 h-3 ml-0.5 animate-pulse" style={{ background: "var(--color-text-accent)", verticalAlign: "text-bottom" }} />
                        )}
                      </div>
                    </div>

                    {/* Action buttons */}
                    {!msg.isStreaming && msg.id !== "welcome" && (
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        <button
                          onClick={() => handleCopyMessage(msg.content, msg.id)}
                          className="p-1 rounded hover:bg-white/5"
                          style={{ color: copiedId === msg.id ? "var(--color-text-accent)" : "var(--color-text-muted)" }}
                          title="Copy"
                        >
                          {copiedId === msg.id ? <CheckCheck size={11} /> : <Copy size={11} />}
                        </button>
                        {msg.role === "user" && (
                          <button
                            onClick={() => handleEditStart(msg)}
                            className="p-1 rounded hover:bg-white/5"
                            style={{ color: "var(--color-text-muted)" }}
                            title="Edit"
                          >
                            <Pencil size={11} />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}

                <span
                  style={{
                    fontSize: 9,
                    color: "var(--color-text-muted)",
                    display: "block",
                    marginTop: 4,
                    textAlign: msg.role === "user" ? "right" : "left",
                  }}
                >
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="p-3 border-t" style={{ borderColor: "var(--color-border-secondary)" }}>
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{
              background: "rgba(0, 0, 0, 0.3)",
              border: "1px solid rgba(0, 212, 255, 0.1)",
            }}
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isStreaming ? "MYRAA is responding..." : "Type a message..."}
              className="flex-1 bg-transparent outline-none"
              style={{
                fontSize: 12,
                color: "var(--color-text-primary)",
                border: "none",
                opacity: isStreaming ? 0.5 : 1,
              }}
              disabled={isStreaming}
            />
            {isStreaming ? (
              <button
                onClick={handleStop}
                className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                style={{ color: "var(--color-status-error)" }}
                title="Stop generating"
              >
                <Square size={14} />
              </button>
            ) : (
              <button
                onClick={handleSend}
                className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                style={{ color: input.trim() ? "var(--color-text-accent)" : "var(--color-text-muted)" }}
                disabled={!input.trim()}
              >
                <Send size={14} />
              </button>
            )}
          </div>

          {/* Voice controls + waveform + regenerate */}
          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={onToggleVoice}
              className="p-2 rounded-lg transition-all"
              style={{
                background: isVoiceActive ? "rgba(0, 212, 255, 0.15)" : "rgba(255, 255, 255, 0.03)",
                border: `1px solid ${isVoiceActive ? "var(--color-border-primary)" : "rgba(255, 255, 255, 0.05)"}`,
                color: isVoiceActive ? "var(--color-text-accent)" : "var(--color-text-muted)",
              }}
            >
              {isVoiceActive ? <Mic size={16} /> : <MicOff size={16} />}
            </button>

            {!isStreaming && messages.length > 1 && messages[messages.length - 1].role === "assistant" && (
              <button
                onClick={handleRegenerate}
                className="p-2 rounded-lg transition-all hover:bg-white/5"
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.05)",
                  color: "var(--color-text-muted)",
                }}
                title="Regenerate response"
              >
                <RotateCcw size={14} />
              </button>
            )}

            {/* Waveform */}
            <div className="flex items-center gap-0.5 flex-1" style={{ height: 20 }}>
              {Array.from({ length: 24 }).map((_, i) => {
                let h = 3;
                if (voiceState === "speaking") {
                  h = 3 + Math.sin(Date.now() * 0.015 + i * 0.4) * 8;
                } else if (voiceState === "listening") {
                  h = 3 + Math.sin(Date.now() * 0.008 + i * 0.3) * 4;
                }
                return (
                  <div
                    key={i}
                    className="waveform-bar"
                    style={{
                      height: Math.max(2, h),
                      background: isVoiceActive
                        ? voiceState === "speaking" ? "var(--color-text-accent)" : "rgba(0, 212, 255, 0.4)"
                        : "rgba(255, 255, 255, 0.08)",
                    }}
                  />
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
