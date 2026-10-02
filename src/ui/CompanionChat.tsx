import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Loader2, Square, Eye, Database, Wrench, MessageCircle,
  Heart, Mic, CheckCheck, ArrowUp,
  Folder, Search, FileText, Check,
} from 'lucide-react';
import { streamChat, cancelStream } from '../core/api';
import type { ChatMessage, CompanionTab, TaskProgress, VoiceState } from './events';

// ============================================================================
// CompanionChat — glass panel matching reference mock
// Header (MYRAA + Online + window controls) / pill tabs / bubbles /
// task card / waveform + mic / Talk-to-MYRAA input.
// ============================================================================

export interface CompanionChatProps {
  messages: ChatMessage[];
  onAddMessage: (msg: ChatMessage) => void;
  onUpdateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  voiceState?: VoiceState;
  onToggleVoice?: () => void;
  /** Real backend/agent availability (from /api/agent-health). */
  online?: boolean;
}

export function CompanionChat({
  messages,
  onAddMessage,
  onUpdateMessage,
  voiceState = 'idle',
  onToggleVoice,
  online = false,
}: CompanionChatProps) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTab, setActiveTab] = useState<CompanionTab>('chat');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearBottomRef = useRef(true);
  const streamCtrlRef = useRef<AbortController | null>(null);
  const streamTextRef = useRef('');

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) nearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 90;
  }, []);

  // Auto-scroll only while the user is already near the bottom — never fight
  // someone reading history.
  useEffect(() => {
    if (nearBottomRef.current) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
      isStreaming: false,
    };
    onAddMessage(userMsg);
    setInput('');

    const assistantMsgId = `asst-${Date.now()}`;
    onAddMessage({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    });
    setIsStreaming(true);
    streamTextRef.current = '';

    const ctrl = streamChat(text, {
      onConversationId: (id) => setConversationId(id),
      onChunk: (chunk) => {
        streamTextRef.current += chunk;
        onUpdateMessage(assistantMsgId, { content: streamTextRef.current });
      },
      onDone: (fullText) => {
        onUpdateMessage(assistantMsgId, {
          content: fullText || streamTextRef.current,
          isStreaming: false,
        });
        setIsStreaming(false);
        streamCtrlRef.current = null;
        streamTextRef.current = '';
      },
      onError: (msg) => {
        onUpdateMessage(assistantMsgId, { content: `Error: ${msg}`, isStreaming: false });
        setIsStreaming(false);
        streamCtrlRef.current = null;
      },
    }, conversationId || undefined);
    streamCtrlRef.current = ctrl;
  }, [input, isStreaming, conversationId, onAddMessage, onUpdateMessage]);

  const handleStop = useCallback(() => {
    if (streamCtrlRef.current) {
      streamCtrlRef.current.abort();
      if (conversationId) cancelStream(conversationId);
      setIsStreaming(false);
      streamCtrlRef.current = null;
      for (const m of messages) {
        if (m.isStreaming) onUpdateMessage(m.id, { isStreaming: false });
      }
    }
  }, [conversationId, messages, onUpdateMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) return;
      handleSend();
    }
  }, [isStreaming, handleSend]);

  const tabs: { id: CompanionTab; label: string; icon: React.ReactNode }[] = useMemo(() => [
    { id: 'chat', label: 'Chat', icon: <MessageCircle size={13} /> },
    { id: 'vision', label: 'Vision', icon: <Eye size={13} /> },
    { id: 'memory', label: 'Memory', icon: <Database size={13} /> },
    { id: 'tools', label: 'Tools', icon: <Wrench size={13} /> },
  ], []);

  return (
    <div className="flex flex-col h-full myraa-glass" style={{ borderRadius: 20, overflow: 'hidden' }}>
      {/* ── Header ── */}
      <div style={{ padding: '14px 16px 10px' }}>
        <div className="flex items-center gap-2">
          <div>
            <div style={{ fontFamily: '"Space Grotesk", sans-serif', fontSize: 19, fontWeight: 700, letterSpacing: '0.04em', color: '#fff', lineHeight: 1.1 }}>
              MYRAA
            </div>
            <div className="flex items-center gap-1.5" style={{ marginTop: 3 }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: online ? '#4ade80' : '#f59e0b',
                boxShadow: online ? '0 0 8px rgba(74,222,128,0.9)' : '0 0 8px rgba(245,158,11,0.8)',
                transition: 'background 400ms ease, box-shadow 400ms ease',
              }} />
              <span style={{ fontSize: 11, fontWeight: 500, color: online ? '#9ee6b8' : '#fcd9a0', transition: 'color 400ms ease' }}>
                {online ? 'Online' : 'Connecting…'}
              </span>
            </div>
          </div>
          <div className="flex-1" />
          <Heart size={15} style={{ color: '#f9a8d4', fill: '#f9a8d4' }} aria-hidden="true" />
        </div>
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.08)', margin: '0 14px' }} />

      {/* ── Tabs ── */}
      <div className="flex items-center gap-2" style={{ padding: '10px 14px 4px' }}>
        {tabs.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex items-center justify-center gap-1.5 flex-1 transition-all"
              style={{
                padding: '7px 0',
                borderRadius: 999,
                fontSize: 12,
                fontWeight: 600,
                color: active ? '#2a1845' : '#cdbce9',
                background: active ? '#cfa8ff' : 'transparent',
                boxShadow: active ? '0 4px 16px rgba(201,163,255,0.35)' : 'none',
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Content ── */}
      {activeTab === 'chat' ? (
        <>
          <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto myraa-no-scrollbar" style={{ padding: '10px 14px 6px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {messages.length === 0 && <ChatEmptyState />}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* ── Voice waveform + mic ── */}
          <VoiceStrip voiceState={voiceState} onToggleVoice={onToggleVoice} />

          {/* ── Input ── */}
          <div style={{ padding: '8px 12px 12px' }}>
            <div
              className="flex items-center gap-2 flex-1"
              style={{
                background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)',
                borderRadius: 999, padding: '4px 4px 4px 16px', height: 44,
                transition: 'border-color 200ms ease, box-shadow 200ms ease',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'rgba(201,163,255,0.55)'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(201,163,255,0.14)'; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.10)'; e.currentTarget.style.boxShadow = 'none'; }}
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isStreaming ? 'MYRAA is responding...' : 'Talk to MYRAA...'}
                className="flex-1 bg-transparent outline-none"
                style={{ fontSize: 13, color: '#fff', minWidth: 0 }}
                aria-label="Message MYRAA"
                disabled={isStreaming}
              />
                {isStreaming ? (
                  <button
                    onClick={handleStop}
                    className="flex items-center justify-center"
                    style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(251,113,133,0.25)', color: '#fecdd3', flexShrink: 0 }}
                    title="Stop generating"
                  >
                    <Square size={13} />
                  </button>
                ) : (
                  <button
                    onClick={handleSend}
                    className="flex items-center justify-center transition-all"
                    style={{
                      width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
                      background: input.trim() ? '#8b7cf6' : 'rgba(255,255,255,0.08)',
                      color: input.trim() ? '#fff' : '#8f7fb3',
                      boxShadow: input.trim() ? '0 4px 14px rgba(139,124,246,0.5)' : 'none',
                    }}
                    disabled={!input.trim()}
                    title="Send"
                  >
                    <ArrowUp size={16} />
                  </button>
                )}
              </div>
          </div>
        </>
      ) : (
        <TabPlaceholder tab={activeTab} />
      )}
    </div>
  );
}

// ============================================================================
// Empty state
// ============================================================================

function ChatEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3" style={{ padding: '40px 12px', opacity: 0.9 }}>
      <div
        className="flex items-center justify-center"
        style={{
          width: 52, height: 52, borderRadius: '50%',
          background: 'radial-gradient(circle at 35% 30%, rgba(216,180,254,0.35) 0%, rgba(139,92,246,0.18) 60%, transparent 100%)',
          border: '1px solid rgba(201,163,255,0.28)',
          boxShadow: '0 0 24px rgba(192,132,252,0.18)',
        }}
      >
        <span style={{ fontSize: 18, fontWeight: 800, color: '#e9d8ff', letterSpacing: '0.04em' }}>M</span>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 13, color: '#e5d6f7', fontWeight: 700, letterSpacing: '0.03em' }}>Namaste! Main MYRAA hoon</div>
        <div style={{ fontSize: 11.5, color: '#9a8ab8', textAlign: 'center', marginTop: 5, lineHeight: 1.5 }}>
          How can I help?<br />Type below or tap the mic and just speak.
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Message bubble (reference: user right purple / assistant left light)
// ============================================================================

const MessageBubble = React.memo(function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  if (isUser) {
    return (
      <div className="flex flex-col items-end">
        <div style={{
          maxWidth: '88%', background: 'var(--myraa-user-bubble)', border: '1px solid var(--myraa-user-border)',
          borderRadius: '14px 14px 5px 14px', padding: '10px 13px',
          fontSize: 12.5, lineHeight: 1.55, color: '#fff', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          boxShadow: '0 6px 18px rgba(80,60,160,0.3)',
        }}>
          {message.content}
        </div>
        <div className="flex items-center gap-1" style={{ marginTop: 3, paddingRight: 4 }}>
          <span style={{ fontSize: 10, color: '#a892c8' }}>{formatTime(message.timestamp)}</span>
          <CheckCheck size={13} style={{ color: '#9fd8ff' }} />
        </div>
      </div>
    );
  }

  const hasTasks = message.taskProgress && message.taskProgress.length > 0;
  return (
    <div className="flex gap-2" style={{ maxWidth: '94%' }}>
      <div style={{
        width: 27, height: 27, borderRadius: '50%', flexShrink: 0, marginTop: 18,
        background: 'radial-gradient(circle at 35% 30%, #ffd9e8 0%, #c084fc 45%, #6d4aa8 100%)',
        border: '1px solid rgba(255,255,255,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, fontWeight: 800, color: '#fff',
      }}>
        M
      </div>
      <div style={{ minWidth: 0 }}>
        <div className="flex items-center gap-2" style={{ marginBottom: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.04em', color: '#fff' }}>MYRAA</span>
          <span style={{ fontSize: 10, color: '#a892c8' }}>{formatTime(message.timestamp)}</span>
        </div>
        <div style={{
          background: 'var(--myraa-asst-bubble)', border: '1px solid var(--myraa-asst-border)',
          borderRadius: '5px 14px 14px 14px', padding: '10px 13px',
          fontSize: 12.5, lineHeight: 1.55, color: '#f1e7ff', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {message.isStreaming && !message.content ? (
            <span className="flex items-center gap-2" style={{ color: '#b9a3e3' }}>
              <Loader2 size={12} className="animate-spin" /> Typing...
            </span>
          ) : (
            <>
              {message.content}
              {message.isStreaming && (
                <span className="inline-block animate-pulse" style={{ width: 6, height: 13, marginLeft: 3, background: '#d8b4fe', verticalAlign: 'text-bottom', borderRadius: 2 }} />
              )}
            </>
          )}
        </div>
        {hasTasks && (
          <div style={{
            marginTop: 8, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.09)',
            borderRadius: 12, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 9, minWidth: 220,
          }}>
            {message.taskProgress!.map((t, i) => (
              <TaskRow key={i} task={t} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
});

// ============================================================================
// Task row (Scanning / Analyzing / Checking)
// ============================================================================

function TaskRow({ task }: { task: TaskProgress }) {
  const icon = /scan|file/i.test(task.label)
    ? <Folder size={14} style={{ color: '#c9b8e6' }} />
    : /analy|search|code/i.test(task.label)
      ? <Search size={14} style={{ color: '#c9b8e6' }} />
      : <FileText size={14} style={{ color: '#c9b8e6' }} />;
  return (
    <div className="flex items-center gap-2.5">
      {icon}
      <span style={{ fontSize: 12, color: '#e2d4f7', flex: 1 }}>{task.label}</span>
      {task.status === 'complete' && <Check size={15} style={{ color: '#4ade80' }} />}
      {task.status === 'active' && <Loader2 size={14} className="animate-spin" style={{ color: '#7cc7ff' }} />}
      {task.status === 'pending' && <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#8f7fb3' }} />}
      {task.status === 'error' && <span style={{ fontSize: 12, color: '#fb7185' }}>✕</span>}
    </div>
  );
}

// ============================================================================
// Voice strip — waveform + glowing mic (reference mock)
// Bars are CSS-animated (GPU compositing only) — no per-frame React renders.
// ============================================================================

const WAVE_BARS = 44;

interface WaveBarProfile {
  duration: number;
  delay: number;
  scale: number;
  idle: number;
}

function VoiceStrip({ voiceState, onToggleVoice }: { voiceState: VoiceState; onToggleVoice?: () => void }) {
  const active = voiceState === 'listening' || voiceState === 'speaking' || voiceState === 'processing' || voiceState === 'reconnecting';
  // Deterministic per-bar animation profile (stable across renders).
  const bars = useMemo(() =>
    Array.from({ length: WAVE_BARS }, (_, i) => ({
      duration: 0.9 + ((i * 7919) % 53) / 60,        // 0.9s–1.78s
      delay: ((i * 104729) % 97) / 100,               // 0s–0.96s
      scale: 0.35 + ((i * 15485863) % 65) / 100,      // 0.35–1.0
      idle: 3 + ((i * 7919) % 31) / 10,               // 3–6.1px
    })), []);
  const amp = voiceState === 'speaking' ? 15 : voiceState === 'listening' ? 9 : 6;
  const mid = Math.floor(WAVE_BARS / 2);
  const left = bars.slice(0, mid - 3);
  const right = bars.slice(mid + 3);

  const Wave = ({ bars, align }: { bars: WaveBarProfile[]; align: 'end' | 'start' }) => (
    <div className="flex items-center flex-1" aria-hidden="true" style={{ gap: 3, height: 34, justifyContent: align === 'end' ? 'flex-end' : 'flex-start', overflow: 'hidden' }}>
      {bars.map((b, i) => (
        <div
          key={i}
          className={active ? 'myraa-wave-bar' : undefined}
          style={{
            width: 3,
            height: active ? undefined : b.idle,
            borderRadius: 3,
            background: active ? '#c084fc' : 'rgba(200,160,255,0.30)',
            boxShadow: active ? '0 0 8px rgba(192,132,252,0.55)' : 'none',
            ...(active ? ({
              '--wave-scale': b.scale,
              '--wave-amp': `${amp}px`,
              animationDuration: `${b.duration}s`,
              animationDelay: `${b.delay}s`,
            } as React.CSSProperties) : {}),
          }}
        />
      ))}
    </div>
  );

  return (
    <div style={{ padding: '6px 16px 0' }}>
      <div className="flex items-center gap-3">
        <Wave bars={left} align="end" />
        <button
          onClick={onToggleVoice}
          title="Click or speak to talk"
          aria-label={voiceState === 'listening' ? 'Stop voice mode' : 'Start voice mode'}
          aria-pressed={voiceState === 'listening'}
          className="flex items-center justify-center transition-transform hover:scale-105 active:scale-95"
          style={{
            width: 48, height: 48, borderRadius: '50%', flexShrink: 0,
            background: 'radial-gradient(circle at 35% 30%, #d8b4fe 0%, #a78bfa 55%, #7c5cd6 100%)',
            border: '2px solid rgba(255,255,255,0.45)',
            boxShadow: '0 0 0 5px rgba(53, 21, 152, 0.18), 0 0 26px rgba(167,139,250,0.65)',
            color: '#fff', position: 'relative',
          }}
        >
          <Mic size={20} />
          {active && <span className="absolute inset-0" style={{ borderRadius: '50%', border: '2px solid rgba(216,180,254,0.6)', animation: 'mic-ring 1.6s ease-out infinite', pointerEvents: 'none' }} />}
        </button>
        <Wave bars={right} align="start" />
      </div>
      <div role="status" aria-live="polite" style={{ textAlign: 'center', fontSize: 11, color: '#b9a6da', marginTop: 5 }}>
        {voiceState === 'listening' ? 'Listening... tap mic to stop' : voiceState === 'speaking' ? 'MYRAA is speaking...' : voiceState === 'processing' ? 'Thinking...' : voiceState === 'reconnecting' ? 'Reconnecting... keep talking' : 'Click or speak to talk'}
      </div>
      <style>{`
        @keyframes mic-ring { 0% { transform: scale(1); opacity: 0.7; } 100% { transform: scale(1.55); opacity: 0; } }
        @keyframes myraa-wave-pulse {
          0%, 100% { transform: scaleY(0.25); }
          50% { transform: scaleY(var(--wave-scale, 0.8)); }
        }
        .myraa-wave-bar {
          height: calc(6px + var(--wave-amp, 8px));
          transform-origin: center;
          animation-name: myraa-wave-pulse;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
          will-change: transform;
        }
      `}</style>
    </div>
  );
}

// ============================================================================
// Tab placeholder + helpers
// ============================================================================

function TabPlaceholder({ tab }: { tab: CompanionTab }) {
  const labels: Record<CompanionTab, string> = {
    chat: '',
    vision: 'Vision feed will appear here',
    memory: 'Memory dashboard will appear here',
    tools: 'Tool panel will appear here',
  };
  const icons: Record<CompanionTab, React.ReactNode> = {
    chat: null,
    vision: <Eye size={20} />,
    memory: <Database size={20} />,
    tools: <Wrench size={20} />,
  };
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3" style={{ opacity: 0.45, paddingBottom: 40 }}>
      {icons[tab]}
      <span style={{ fontSize: 11, color: '#b9a6da' }}>{labels[tab]}</span>
    </div>
  );
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
}
