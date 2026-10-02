import { useClock } from "../hooks";
import { Minus, Square, Maximize2, Sun, Power, Loader2 } from "lucide-react";

interface TopBarProps {
  voiceState: string;
  onSettingsClick: () => void;
  isSystemActive: boolean;
  onToggleSystem: () => void;
}

export function TopBar({ voiceState, onSettingsClick, isSystemActive, onToggleSystem }: TopBarProps) {
  const time = useClock();
  const isOnline = voiceState !== "disconnected";
  const isTransitioning = voiceState === "connecting";

  const formatTime = (d: Date) => {
    const h = d.getHours();
    const m = d.getMinutes().toString().padStart(2, "0");
    const ampm = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    return `${h12}:${m} ${ampm}`;
  };

  return (
    <header
      className="flex items-center justify-between px-5 border-b"
      style={{ height: 52, background: "var(--color-bg-elevated)", borderColor: "var(--color-border-secondary)" }}
    >
      {/* Left: Stark Industries branding */}
      <div className="flex flex-col">
        <span style={{ fontFamily: "var(--font-display)", fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", color: "var(--color-text-primary)" }}>
          STARK INDUSTRIES
        </span>
        <span style={{ fontSize: 8, fontWeight: 500, letterSpacing: "0.2em", color: "var(--color-text-muted)", marginTop: 1 }}>
          BUILDING A BETTER TOMORROW
        </span>
      </div>

      {/* Center: System status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div style={{
            width: 6, height: 6, borderRadius: "50%",
            background: isOnline ? "var(--color-status-success)" : isTransitioning ? "var(--color-status-warning)" : "var(--color-status-error)",
            boxShadow: isOnline ? "0 0 8px rgba(0, 232, 138, 0.5)" : isTransitioning ? "0 0 8px rgba(255, 170, 0, 0.5)" : "none",
            animation: isTransitioning ? "pulse 1.5s ease-in-out infinite" : undefined,
          }} />
          <span style={{
            fontSize: 11, fontWeight: 600, letterSpacing: "0.12em",
            color: isOnline ? "var(--color-status-success)" : isTransitioning ? "var(--color-status-warning)" : "var(--color-status-error)",
            fontFamily: "var(--font-display)",
          }}>
            {isTransitioning ? "STARTING" : isOnline ? "SYSTEM ACTIVE" : "SYSTEM OFF"}
          </span>
        </div>
        <div style={{ width: 1, height: 16, background: "var(--color-border-primary)" }} />
        <div className="flex items-center gap-2">
          <div style={{
            width: 6, height: 6, borderRadius: "50%",
            background: isOnline ? "var(--color-text-accent)" : "var(--color-text-muted)",
            boxShadow: isOnline ? "0 0 8px rgba(0, 212, 255, 0.4)" : "none",
          }} />
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", fontFamily: "var(--font-display)" }}>
            NEURAL CORE: <span style={{ color: isOnline ? "var(--color-text-accent)" : "var(--color-text-muted)" }}>{isOnline ? "ONLINE" : "OFFLINE"}</span>
          </span>
        </div>
      </div>

      {/* Right: Start/Stop + Clock + Controls */}
      <div className="flex items-center gap-3">
        {/* Global Start/Stop Button */}
        <button
          onClick={onToggleSystem}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-300"
          style={{
            background: isOnline ? "var(--color-bg-active)" : "var(--color-bg-hover)",
            border: `1px solid ${isOnline ? "var(--color-status-success)" : "var(--color-border-primary)"}`,
            color: isOnline ? "var(--color-status-success)" : "var(--color-text-accent)",
          }}
        >
          {isTransitioning ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Power size={13} />
          )}
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", fontFamily: "var(--font-display)" }}>
            {isTransitioning ? "STARTING" : isOnline ? "STOP" : "START"}
          </span>
        </button>

        <span style={{ fontSize: 13, fontWeight: 600, fontFamily: "var(--font-display)", color: "var(--color-text-primary)", letterSpacing: "0.05em" }}>
          {formatTime(time)}
        </span>

        <button className="p-1.5 rounded-md transition-colors hover:bg-white/5" style={{ color: "var(--color-text-secondary)" }} title="Theme">
          <Sun size={15} />
        </button>
        <button className="p-1.5 rounded-md transition-colors hover:bg-white/5" style={{ color: "var(--color-text-secondary)" }} title="Fullscreen">
          <Maximize2 size={15} />
        </button>
        <button className="p-1.5 rounded-md transition-colors hover:bg-white/5" style={{ color: "var(--color-text-secondary)" }} title="Minimize">
          <Minus size={15} />
        </button>
        <button className="p-1.5 rounded-md transition-colors hover:bg-white/5" style={{ color: "var(--color-text-secondary)" }} title="Close">
          <Square size={12} />
        </button>
      </div>
    </header>
  );
}
