import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { motion } from 'motion/react';
import { Heart } from 'lucide-react';
import { MyraaAudioSession } from '../lib/audio';
import type { LiveState } from '../lib/audio';
import type { AvatarMainState } from '../avatar/contracts';
import { AvatarEngine } from '../avatar';
import type { ChatMessage, VoiceState as CompanionVoiceState } from './events';
import { MyraaEnvironment } from './MyraaEnvironment';
import { MyraaCharacter } from './MyraaCharacter';
import { CompanionChat } from './CompanionChat';
import { useAppStore } from '../core/store';

// ============================================================================
// State mappers
// ============================================================================

function mapVoiceState(live: LiveState): CompanionVoiceState {
  switch (live) {
    case 'listening': return 'listening';
    case 'speaking': return 'speaking';
    case 'reconnecting': return 'reconnecting';
    case 'connecting': return 'processing';
    default: return 'idle';
  }
}

function mapAvatarState(live: LiveState, hasActiveTask: boolean): AvatarMainState {
  if (hasActiveTask) return 'WORKING';
  switch (live) {
    case 'listening': return 'LISTENING';
    case 'speaking': return 'SPEAKING';
    case 'reconnecting': return 'THINKING';
    case 'connecting': return 'THINKING';
    default: return 'IDLE';
  }
}

// ============================================================================
// MyraaCompanion — reference layout: scenic left + glass chat right
// Fresh sessions start with a clean empty state (no seeded/demo messages).
// ============================================================================

export default function MyraaCompanion() {
  const { dispatch } = useAppStore();
  void dispatch;

  const [liveState, setLiveState] = useState<LiveState>('disconnected');
  const [modelCaption, setModelCaption] = useState('');
  const [isOnline, setIsOnline] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const avatarRef = useRef<AvatarEngine | null>(null);
  const [avatarState, setAvatarState] = useState<AvatarMainState>('IDLE');
  const sessionRef = useRef<MyraaAudioSession | null>(null);
  const voiceState = useMemo(() => mapVoiceState(liveState), [liveState]);

  const [clock, setClock] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 10000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const engine = new AvatarEngine({ updateRate: 24 });
    avatarRef.current = engine;
    engine.start();
    const tick = setInterval(() => setAvatarState(engine.getMainState()), 200);
    return () => { clearInterval(tick); engine.destroy(); };
  }, []);

  useEffect(() => {
    if (!avatarRef.current) return;
    const hasTask = false;
    const newState = mapAvatarState(liveState, hasTask);
    avatarRef.current.updateContext({
      voiceState: mapVoiceState(liveState) as unknown as never,
      taskState: hasTask ? 'executing' : 'idle',
      userInterruption: false,
    });
    avatarRef.current.requestTransition(newState, `voice state: ${liveState}`);
  }, [liveState]);

  const handleAddMessage = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev.slice(-100), msg]);
  }, []);

  const handleUpdateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...updates } : m)));
  }, []);

  const handleToggleVoice = useCallback(async () => {
    if (!sessionRef.current) return;
    if (liveState === 'disconnected') {
      await sessionRef.current.connect();
      setIsOnline(true);
    } else {
      sessionRef.current.disconnect();
      setIsOnline(false);
    }
  }, [liveState]);

  useEffect(() => {
    sessionRef.current = new MyraaAudioSession({
      onStateChange: (s) => {
        setLiveState(s);
        if (s === 'disconnected') setModelCaption('');
      },
      onTranscription: (role, text) => {
        if (role === 'user') {
          setModelCaption('');
          setMessages((prev) => [...prev.slice(-100), {
            id: `voice-user-${Date.now()}`, role: 'user', content: text,
            timestamp: new Date().toISOString(), isStreaming: false,
          }]);
        } else {
          setModelCaption((prev) => prev + text);
        }
      },
      onToolCall: async (name, args, callback) => {
        // Connect voice-driven tool calls to the real desktop agent when it is
        // reachable, so the companion shell is not a dead-end for tools.
        try {
          const r = await fetch('http://127.0.0.1:8765/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tool: name, args: args ?? {}, request_id: 'companion-voice' }),
            signal: AbortSignal.timeout(15000),
          });
          if (r.ok) {
            const data = await r.json();
            callback(data);
            return;
          }
          callback({ error: `Tool ${name} failed (${r.status})`, meta: { degraded: true } });
        } catch {
          callback({ error: `Tools not reachable in companion mode (${name} requires the desktop agent).` });
        }
      },
      onError: () => {},
      onMemorySync: () => {},
      onToolResponse: () => {},
    });
    return () => { sessionRef.current?.disconnect(); };
  }, []);

  useEffect(() => {
    if (modelCaption && liveState === 'speaking') {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant' && last.id.startsWith('voice-model-')) {
          return prev.map((m) => (m.id === last.id ? { ...m, content: modelCaption } : m));
        }
        return [...prev.slice(-100), {
          id: `voice-model-${Date.now()}`, role: 'assistant' as const,
          content: modelCaption, timestamp: new Date().toISOString(), isStreaming: true,
        }];
      });
    }
  }, [modelCaption, liveState]);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const r = await fetch('/api/agent-health');
        const data = await r.json();
        setIsOnline(data.online === true);
      } catch { setIsOnline(false); }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const timeStr = clock.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  const dateStr = clock.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

  // Subtle assistant state label — quiet, no gaming-HUD styling.
  const stateLabel: Record<AvatarMainState, string> = {
    IDLE: 'Ready', LISTENING: 'Listening', THINKING: 'Thinking', WORKING: 'Working',
    SPEAKING: 'Speaking', VERIFYING: 'Verifying', RECOVERY: 'Recovering',
    ERROR: 'Error', RELAXED: 'Relaxed', SLEEPING: 'Sleeping',
  };

  return (
    <div className="fixed inset-0 overflow-hidden" style={{ fontFamily: '"Inter", sans-serif', background: '#241434' }}>
      <MyraaEnvironment />

      {/* ── Main split ── */}
      <div className="relative flex h-full" style={{ zIndex: 1 }}>
        {/* ═══ LEFT — scenic companion ═══ */}
        <div className="relative flex-1 overflow-hidden" style={{ minWidth: 0 }}>
          {/* branding */}
          <motion.div
            className="absolute flex items-center gap-2.5"
            style={{ top: 18, left: 22 }}
            initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
          >
            <div style={{
              width: 38, height: 38, borderRadius: 12,
              background: 'linear-gradient(135deg, #c084fc 0%, #8b5cf6 60%, #6d4aa8 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 6px 20px rgba(139,92,246,0.5), inset 0 1px 0 rgba(255,255,255,0.35)',
            }}>
              <Heart size={19} style={{ color: '#fff', fill: 'rgba(255,255,255,0.85)' }} />
            </div>
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: '0.06em', color: '#fff', lineHeight: 1 }}>MYRAA</div>
              <div className="flex items-center gap-1.5" style={{ fontSize: 11, color: 'rgba(255,235,245,0.75)', marginTop: 2 }}>
                <span style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: isOnline ? '#4ade80' : '#fb7185',
                  boxShadow: isOnline ? '0 0 6px rgba(74,222,128,0.8)' : '0 0 6px rgba(251,113,133,0.7)',
                  transition: 'background 400ms ease',
                }} />
                {isOnline ? 'Always with you...' : 'Reconnecting...'}
              </div>
            </div>
            <div className="flex-1" />
            <div
              role="status"
              aria-label={`Assistant state: ${stateLabel[avatarState]}`}
              style={{
                marginTop: 2, padding: '4px 12px', borderRadius: 999,
                background: 'rgba(20, 10, 34, 0.45)', border: '1px solid rgba(255,255,255,0.10)',
                backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
                fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
                color: 'rgba(233,216,255,0.9)', transition: 'color 500ms ease',
              }}
            >
              {stateLabel[avatarState]}
            </div>
          </motion.div>

          {/* clock */}
          <motion.div className="absolute" style={{ top: 74, left: 24 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15, duration: 0.6 }}>
            <div style={{ fontSize: 21, fontWeight: 300, color: '#fff', letterSpacing: '0.04em', textShadow: '0 2px 14px rgba(60,20,60,0.5)' }}>{timeStr}</div>
            <div style={{ fontSize: 11, color: 'rgba(255,240,248,0.72)', marginTop: 1 }}>{dateStr}</div>
          </motion.div>

          {/* sleeping cat on a cushion */}
          <motion.div className="absolute" style={{ left: 22, top: '46%' }} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4, duration: 0.7 }}>
            <div style={{ position: 'relative', width: 150 }}>
              {/* cat */}
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: -6, zIndex: 2, position: 'relative' }}>
                <svg width="86" height="34" viewBox="0 0 86 34">
                  <ellipse cx="43" cy="22" rx="30" ry="11" fill="#efe7dc" />
                  <ellipse cx="43" cy="20" rx="22" ry="8" fill="#f7f1e8" />
                  <circle cx="20" cy="16" r="9" fill="#efe7dc" />
                  <path d="M14 9 L12 2 L19 7 Z M26 7 L28 0 L31 8 Z" fill="#efe7dc" />
                  <path d="M63 14 L70 8 L70 17 Z" fill="#8a6a55" />
                  <ellipse cx="60" cy="20" rx="12" ry="8" fill="#8a6a55" opacity="0.55" />
                  <path d="M17 17 L22 17 M62 28 C70 28 76 24 80 20" stroke="#8a7a68" strokeWidth="1.4" fill="none" />
                  <path d="M18 16 q2 1.5 4 0" stroke="#5a4a3a" strokeWidth="1.2" fill="none" />
                </svg>
              </div>
              {/* cushion */}
              <div style={{ width: 150, height: 30, borderRadius: 16, background: 'linear-gradient(180deg,#6d5a86,#4a3a62)', border: '1px solid rgba(255,255,255,0.12)', boxShadow: '0 8px 20px rgba(0,0,0,0.4)' }} />
            </div>
          </motion.div>

          {/* character */}
          <motion.div
            className="absolute"
            style={{ left: '50%', transform: 'translateX(-50%)', bottom: '6%', width: 'min(40vw, 500px)', height: 'min(72vh, 640px)' }}
            initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, ease: [0.4, 0, 0.2, 1] }}
          >
            <MyraaCharacter state={avatarState} />
          </motion.div>

          {/* mug + phone on table */}
          <div className="absolute flex items-end gap-4" style={{ left: '7%', bottom: '7%' }}>
            <div style={{ position: 'relative' }}>
              <div style={{
                width: 92, height: 96, borderRadius: '6px 6px 14px 14px',
                background: 'linear-gradient(180deg, #f4ede4 0%, #d9cfc2 100%)',
                border: '1px solid rgba(90,60,50,0.35)', boxShadow: '0 10px 24px rgba(0,0,0,0.4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="26" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M12 20 C5 14 3 10 5.5 7 C7.5 4.8 10.6 5.4 12 8 C13.4 5.4 16.5 4.8 18.5 7 C21 10 19 14 12 20 Z" stroke="#b09a8a" strokeWidth="1.4" fill="none" opacity="0.7" />
                </svg>
              </div>
              <div style={{ position: 'absolute', right: -16, top: 22, width: 24, height: 36, border: '7px solid #e8ded2', borderLeft: 'none', borderRadius: '0 12px 12px 0' }} />
              <div style={{ position: 'absolute', top: -4, left: 8, right: 8, height: 8, borderRadius: '50%', background: '#6b4632' }} />
            </div>
            <div style={{ width: 120, height: 14, borderRadius: 4, background: 'linear-gradient(180deg,#2c2138,#141020)', border: '1px solid rgba(255,255,255,0.15)', transform: 'rotate(-4deg)', boxShadow: '0 6px 14px rgba(0,0,0,0.45)' }} />
          </div>

          {/* foreground plant blur */}
          <div className="pointer-events-none absolute" style={{ left: -24, bottom: 0, width: 130, height: '46%', background: 'linear-gradient(180deg, transparent, rgba(10,25,12,0.55))', filter: 'blur(6px)' }} />
        </div>

        {/* ═══ RIGHT — glass chat ═══ */}
        <motion.div
          className="flex-shrink-0 h-full"
          style={{ width: 'min(37vw, 432px)', padding: '12px 14px 12px 6px' }}
          initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, delay: 0.15, ease: [0.4, 0, 0.2, 1] }}
        >
          <CompanionChat
            messages={messages}
            onAddMessage={handleAddMessage}
            onUpdateMessage={handleUpdateMessage}
            voiceState={voiceState}
            onToggleVoice={handleToggleVoice}
            online={isOnline}
          />
        </motion.div>
      </div>

    </div>
  );
}
