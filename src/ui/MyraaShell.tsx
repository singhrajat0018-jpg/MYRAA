import { useState, useCallback } from "react";
import { LiveState } from "../lib/audio";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { CoreVisualization } from "./CoreVisualization";
import { ChatPanel } from "./ChatPanel";
import { VoiceHUD } from "./VoiceHUD";
import { Footer } from "./Footer";

interface MyraaShellProps {
  voiceState: LiveState;
  onToggleVoice: () => void;
  onSettingsClick: () => void;
  userCaption: string;
  modelCaption: string;
  isScreenSharing: boolean;
  memoryCount: number;
  onSendMessage: (text: string) => void;
  hudMetadata?: Record<string, unknown>;
  onHudMetadata?: (metadata: Record<string, unknown>) => void;
}

const STATE_LABELS: Record<string, string> = {
  disconnected: "OFFLINE",
  connecting: "CONNECTING",
  listening: "LISTENING",
  speaking: "SPEAKING",
};

const STATE_COLORS: Record<string, string> = {
  disconnected: "var(--color-text-muted)",
  connecting: "var(--color-status-warning)",
  listening: "var(--color-text-accent)",
  speaking: "var(--color-status-success)",
};

export function MyraaShell({
  voiceState,
  onToggleVoice,
  onSettingsClick,
  userCaption,
  modelCaption,
  isScreenSharing,
  memoryCount,
  onSendMessage,
  hudMetadata,
  onHudMetadata,
}: MyraaShellProps) {
  const [activeNav, setActiveNav] = useState("home");

  const isSystemActive = voiceState !== "disconnected";
  const stateLabel = STATE_LABELS[voiceState] || voiceState.toUpperCase();
  const stateColor = STATE_COLORS[voiceState] || "var(--color-text-muted)";

  const renderWorkspace = useCallback(() => {
    switch (activeNav) {
      case "home":
        return renderVoiceFirst();
      case "chats":
        return (
          <div className="h-full">
            <ChatPanel
              voiceState={voiceState}
              userCaption={userCaption}
              modelCaption={modelCaption}
              onSendMessage={onSendMessage}
              onToggleVoice={onToggleVoice}
              onMetadata={onHudMetadata}
            />
          </div>
        );
      case "trading":
        return <WorkspacePlaceholder title="TRADING" subtitle="Market analysis & advisory" />;
      case "agents":
        return <WorkspacePlaceholder title="AGENTS" subtitle="Multi-agent orchestration" />;
      case "memory":
        return <WorkspacePlaceholder title="MEMORY" subtitle="Knowledge base & recollections" />;
      case "files":
        return <WorkspacePlaceholder title="FILES" subtitle="File system browser" />;
      case "tools":
        return <WorkspacePlaceholder title="TOOLS" subtitle="60+ desktop tools" />;
      case "automation":
        return <WorkspacePlaceholder title="AUTOMATION" subtitle="Autonomous task engine" />;
      case "projects":
        return <WorkspacePlaceholder title="PROJECTS" subtitle="Project builder" />;
      case "images":
        return <WorkspacePlaceholder title="IMAGES" subtitle="Image assets" />;
      case "videos":
        return <WorkspacePlaceholder title="VIDEOS" subtitle="Video assets" />;
      case "settings":
        return <WorkspacePlaceholder title="SETTINGS" subtitle="System configuration" />;
      default:
        return renderVoiceFirst();
    }
  }, [activeNav, voiceState, userCaption, modelCaption, onSendMessage, onToggleVoice]);

  const renderVoiceFirst = () => (
    <div className="flex flex-col items-center justify-center h-full relative">
      {/* Central core visualization — the PRIMARY UI */}
      <div className="relative">
        <CoreVisualization state={voiceState} size={480} />

        {/* State label — centered below core */}
        <div className="absolute bottom-8 left-0 right-0 flex flex-col items-center gap-2">
          {/* State indicator dot + label */}
          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full"
              style={{
                backgroundColor: stateColor,
                boxShadow: `0 0 8px ${stateColor}80`,
                animation: voiceState === "listening" ? "pulse 2s ease-in-out infinite" : undefined,
              }}
            />
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.2em",
                color: stateColor,
                fontFamily: "var(--font-display)",
              }}
            >
              {stateLabel}
            </span>
          </div>

          {/* User caption — when speaking */}
          {userCaption && voiceState === "listening" && (
            <div
              className="max-w-md text-center px-4"
              style={{
                fontSize: 13,
                color: "var(--color-text-primary)",
                fontFamily: "var(--font-display)",
                opacity: 0.8,
              }}
            >
              {userCaption}
            </div>
          )}

          {/* Model caption — when responding */}
          {modelCaption && (
            <div
              className="max-w-md text-center px-4"
              style={{
                fontSize: 13,
                color: "var(--color-text-accent)",
                fontFamily: "var(--font-display)",
                opacity: 0.9,
              }}
            >
              {modelCaption}
            </div>
          )}
        </div>
      </div>

      {/* Temporary HUD — weather/news/info results */}
      <div className="mt-4">
        <VoiceHUD metadata={hudMetadata} />
      </div>

      {/* Orbital waveform — minimal audio visualization */}
      {isSystemActive && (
        <div className="flex items-center gap-1 mt-6">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="rounded-full"
              style={{
                width: 2,
                height: voiceState === "speaking" ? 8 + Math.sin(Date.now() / 200 + i) * 8 : 3,
                backgroundColor: voiceState === "speaking" ? "var(--color-text-accent)" : "var(--color-myraa-glow)",
                transition: "height 0.15s ease, background-color 0.3s ease",
              }}
            />
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="flex flex-col w-full h-screen overflow-hidden select-none" style={{ background: "var(--color-bg-base)" }}>
      <TopBar
        voiceState={voiceState}
        onSettingsClick={onSettingsClick}
        isSystemActive={isSystemActive}
        onToggleSystem={onToggleVoice}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          activeNav={activeNav}
          onNavChange={setActiveNav}
          voiceState={voiceState}
          onSettingsClick={onSettingsClick}
        />
        <div
          className="flex-1 overflow-y-auto"
          style={{
            background: "var(--color-bg-base)",
            backgroundImage: "linear-gradient(var(--color-bg-hover) 1px, transparent 1px), linear-gradient(90deg, var(--color-bg-hover) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        >
          {renderWorkspace()}
        </div>
      </div>
      <Footer />
    </div>
  );
}

function WorkspacePlaceholder({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div style={{ fontSize: 24, fontWeight: 700, color: "var(--color-text-accent)", fontFamily: "var(--font-display)", letterSpacing: "0.1em" }}>
          {title}
        </div>
        <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>{subtitle}</div>
        <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 16, opacity: 0.5 }}>Coming soon</div>
      </div>
    </div>
  );
}
