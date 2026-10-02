import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, MicOff, Send, Paperclip, Loader2, Brain, Volume2 } from 'lucide-react';
import type { VoiceState } from './events';

// ============================================================================
// CompanionVoice
// ============================================================================

export interface CompanionVoiceProps {
  voiceState: VoiceState;
  onToggleVoice: () => void;
  onSendText: (text: string) => void;
}

const WAVEFORM_BARS = 32;

export function CompanionVoice({
  voiceState,
  onToggleVoice,
  onSendText,
}: CompanionVoiceProps) {
  const [input, setInput] = useState('');
  const [isListening, setIsListening] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [waveHeights, setWaveHeights] = useState<number[]>(() =>
    Array.from({ length: WAVEFORM_BARS }, () => 2)
  );

  // Animate waveform
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);

    if (voiceState === 'listening' || voiceState === 'speaking') {
      setIsListening(true);
      intervalRef.current = setInterval(() => {
        const t = Date.now();
        const speeds = voiceState === 'speaking' ? 0.02 : 0.012;
        const amplitude = voiceState === 'speaking' ? 12 : 6;
        setWaveHeights(
          Array.from({ length: WAVEFORM_BARS }, (_, i) =>
            2 + Math.sin(t * speeds + i * 0.4) * amplitude * (0.5 + Math.random() * 0.5)
          )
        );
      }, 50);
    } else {
      setIsListening(false);
      setWaveHeights(Array.from({ length: WAVEFORM_BARS }, () => 2));
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [voiceState]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    onSendText(text);
    setInput('');
  }, [input, onSendText]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const statusLabel = getStatusLabel(voiceState);
  const statusColor = getStatusColor(voiceState);

  return (
    <div
      className="absolute bottom-0 left-0 right-0 px-6 pb-5"
      style={{ zIndex: 10 }}
    >
      <div
        className="mx-auto"
        style={{
          maxWidth: 700,
          background: 'rgba(10, 14, 28, 0.65)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 20,
          padding: '12px 16px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 0 20px rgba(0, 212, 255, 0.03)',
        }}
      >
        {/* Voice state indicator */}
        {(voiceState !== 'idle' && voiceState !== 'error') && (
          <div className="flex items-center justify-center gap-2 mb-2">
            {voiceState === 'listening' && <Mic size={10} style={{ color: statusColor }} />}
            {voiceState === 'processing' && <Brain size={10} style={{ color: statusColor }} />}
            {voiceState === 'speaking' && <Volume2 size={10} style={{ color: statusColor }} />}
            <span style={{ fontSize: 9, color: statusColor, letterSpacing: '0.1em', fontWeight: 600 }}>
              {statusLabel}
            </span>
          </div>
        )}

        {/* Main input row */}
        <div className="flex items-center gap-3">
          {/* Attachment button */}
          <button
            className="p-2 rounded-xl transition-colors hover:bg-white/5"
            style={{ color: 'var(--color-text-muted)', flexShrink: 0 }}
            title="Attach file"
          >
            <Paperclip size={16} />
          </button>

          {/* Waveform visualization */}
          <div
            className="flex items-center gap-px flex-1 overflow-hidden"
            style={{ height: 28 }}
          >
            {waveHeights.map((h, i) => (
              <div
                key={i}
                style={{
                  width: 2,
                  height: Math.max(2, h),
                  borderRadius: 1,
                  background: isListening
                    ? voiceState === 'speaking'
                      ? 'var(--color-text-accent)'
                      : 'rgba(0, 212, 255, 0.4)'
                    : 'rgba(255, 255, 255, 0.06)',
                  transition: 'height 60ms ease-out, background 200ms ease',
                }}
              />
            ))}
          </div>

          {/* Text input */}
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Talk to MYRAA..."
            className="flex-1 bg-transparent outline-none"
            style={{
              fontSize: 13,
              color: 'var(--color-text-primary)',
              minWidth: 140,
              maxWidth: 200,
              letterSpacing: '0.01em',
            }}
          />

          {/* Send / Mic button */}
          {input.trim() ? (
            <button
              onClick={handleSend}
              className="p-2.5 rounded-xl transition-all"
              style={{
                background: 'rgba(0, 212, 255, 0.15)',
                border: '1px solid rgba(0, 212, 255, 0.25)',
                color: 'var(--color-text-accent)',
                flexShrink: 0,
              }}
            >
              <Send size={15} />
            </button>
          ) : (
            <button
              onClick={onToggleVoice}
              className="p-2.5 rounded-xl transition-all"
              style={{
                background: isListening ? 'rgba(0, 212, 255, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${isListening ? 'rgba(0, 212, 255, 0.25)' : 'rgba(255, 255, 255, 0.06)'}`,
                color: isListening ? 'var(--color-text-accent)' : 'var(--color-text-muted)',
                flexShrink: 0,
                position: 'relative',
              }}
            >
              {isListening ? (
                <>
                  <MicOff size={15} />
                  <span className="absolute inset-0 rounded-xl companion-mic-ring" />
                </>
              ) : (
                <Mic size={15} />
              )}
            </button>
          )}
        </div>
      </div>

      <style>{`
        .companion-mic-ring {
          border: 1px solid rgba(0, 212, 255, 0.3);
          animation: mic-ring-pulse 1.5s ease-out infinite;
          pointer-events: none;
        }
        @keyframes mic-ring-pulse {
          0% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(1.5); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function getStatusLabel(state: VoiceState): string {
  switch (state) {
    case 'listening': return 'Listening...';
    case 'processing': return 'Thinking...';
    case 'speaking': return 'Speaking...';
    case 'interrupted': return 'Interrupted';
    case 'reconnecting': return 'Reconnecting...';
    case 'error': return 'Error';
    default: return '';
  }
}

function getStatusColor(state: VoiceState): string {
  switch (state) {
    case 'listening': return 'var(--color-text-accent)';
    case 'processing': return 'var(--color-accent-tertiary)';
    case 'speaking': return 'var(--color-status-success)';
    case 'interrupted': return 'var(--color-status-warning)';
    case 'reconnecting': return 'var(--color-status-warning)';
    case 'error': return 'var(--color-status-error)';
    default: return 'var(--color-text-muted)';
  }
}
