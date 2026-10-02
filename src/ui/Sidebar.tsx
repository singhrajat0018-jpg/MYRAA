import {
  Home, MessageSquare, Folder, TrendingUp,
  Users, Brain, FileText, Image, Video, Wrench,
  Zap, Settings, User, Circle,
} from "lucide-react";

interface SidebarProps {
  activeNav: string;
  onNavChange: (nav: string) => void;
  voiceState: string;
  onSettingsClick: () => void;
}

const NAV_ITEMS = [
  { id: "home", label: "HOME", icon: Home },
  { id: "chats", label: "CHATS", icon: MessageSquare },
  { id: "projects", label: "PROJECTS", icon: Folder },
  { id: "trading", label: "TRADING", icon: TrendingUp },
  { id: "agents", label: "AGENTS", icon: Users },
  { id: "memory", label: "MEMORY", icon: Brain },
  { id: "files", label: "FILES", icon: FileText },
  { id: "images", label: "IMAGES", icon: Image },
  { id: "videos", label: "VIDEOS", icon: Video },
  { id: "tools", label: "TOOLS", icon: Wrench },
  { id: "automation", label: "AUTOMATION", icon: Zap },
  { id: "settings", label: "SETTINGS", icon: Settings },
];

export function Sidebar({ activeNav, onNavChange, voiceState, onSettingsClick }: SidebarProps) {
  const voiceActive = voiceState !== "disconnected";

  return (
    <aside
      className="flex flex-col h-full border-r"
      style={{
        width: 200,
        minWidth: 200,
        background: "var(--color-bg-elevated)",
        borderColor: "var(--color-border-secondary)",
      }}
    >
      {/* Logo */}
      <div className="px-5 pt-5 pb-3">
        <div
          style={{
            fontFamily: "var(--font-display)",
            fontSize: 22,
            fontWeight: 700,
            color: "var(--color-text-accent)",
            letterSpacing: "0.05em",
          }}
        >
          MYRAA
        </div>
        <div
          style={{
            fontSize: 9,
            fontWeight: 500,
            letterSpacing: "0.15em",
            color: "var(--color-text-muted)",
            marginTop: 2,
          }}
        >
          AI ASSISTANT SYSTEM
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeNav === item.id;
          const isSettingsItem = item.id === "settings";

          return (
            <button
              key={item.id}
              onClick={() => isSettingsItem ? onSettingsClick() : onNavChange(item.id)}
              className="sidebar-nav-item w-full"
              style={isActive ? {
                color: "var(--color-text-accent)",
                background: "var(--color-bg-active)",
              } : undefined}
            >
              <Icon size={15} style={{ opacity: isActive ? 1 : 0.5 }} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* User card */}
      <div
        className="mx-3 mb-3 p-3 rounded-lg"
        style={{
          background: "var(--color-bg-hover)",
          border: "1px solid var(--color-border-secondary)",
        }}
      >
        {/* Core version */}
        <div className="flex items-center gap-2 mb-2">
          <div
            className="flex items-center justify-center rounded"
            style={{
              width: 28,
              height: 28,
              background: "var(--color-bg-active)",
              border: "1px solid var(--color-border-primary)",
            }}
          >
            <Brain size={14} style={{ color: "var(--color-text-accent)" }} />
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-primary)" }}>
              MYRAA CORE
            </div>
            <div style={{ fontSize: 9, color: "var(--color-text-accent)", fontFamily: "var(--font-mono)" }}>
              v3.1.0 EPIC-11
            </div>
          </div>
        </div>

        {/* User info */}
        <div className="flex items-center gap-2 mb-2">
          <User size={12} style={{ color: "var(--color-text-muted)" }} />
          <div>
            <div style={{ fontSize: 9, color: "var(--color-text-muted)", letterSpacing: "0.1em" }}>USER</div>
            <div style={{ fontSize: 11, color: "var(--color-text-primary)", fontWeight: 500 }}>User</div>
          </div>
        </div>

        {/* Status */}
        <div className="flex items-center gap-2 mb-3">
          <Circle size={8} style={{ color: "var(--color-status-success)", fill: "var(--color-status-success)" }} />
          <div>
            <div style={{ fontSize: 9, color: "var(--color-text-muted)", letterSpacing: "0.1em" }}>STATUS</div>
            <div style={{ fontSize: 11, color: "var(--color-status-success)", fontWeight: 500 }}>Online</div>
          </div>
        </div>

        {/* Voice state */}
        <div
          className="flex items-center justify-center gap-2 py-2 rounded-md"
          style={{
            background: voiceActive ? "var(--color-bg-active)" : "var(--color-bg-hover)",
            border: `1px solid ${voiceActive ? "var(--color-border-primary)" : "var(--color-border-subtle)"}`,
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={voiceActive ? "var(--color-text-accent)" : "var(--color-text-muted)"} strokeWidth="2" strokeLinecap="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: "0.1em",
              color: voiceActive ? "var(--color-text-accent)" : "var(--color-text-muted)",
            }}
          >
            {voiceActive ? "VOICE ACTIVE" : "VOICE OFF"}
          </span>
        </div>
      </div>
    </aside>
  );
}
