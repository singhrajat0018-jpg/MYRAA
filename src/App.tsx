import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAppStore } from "./core/store";
import HomeWorkspace from "./components/HomeWorkspace";
import AgentWorkspace from "./components/AgentWorkspace";
import SystemWorkspace from "./components/SystemWorkspace";
import TradingDashboard from "./components/TradingDashboard";
import { MemoryDashboard } from "./components/MemoryDashboard";
import { SettingsPanel } from "./components/SettingsPanel";
import { ChatPanel } from "./components/ChatPanel";
import { BrowserAgent } from "./components/BrowserAgent";
import { MyraaSettings, loadSettings, saveSettings } from "./lib/settingsStore";
import { Memory, MemoryCategory } from "./lib/memoryTypes";
import { MyraaAudioSession } from "./lib/audio";
import {
  Globe,
  Bot,
  Activity,
  TrendingUp,
  Brain,
  Settings,
  MessageSquare,
  Compass,
  Mic,
  MicOff,
  Sparkles,
} from "lucide-react";

export default function App() {
  const { state, dispatch } = useAppStore();
  const [settings, setSettingsState] = useState<MyraaSettings>(() => loadSettings());
  const [isMemoryOpen, setIsMemoryOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isBrowserOpen, setIsBrowserOpen] = useState(false);
  const [browserUrl, setBrowserUrl] = useState("https://www.google.com");
  const [memories, setMemories] = useState<Memory[]>([]);
  const [isListening, setIsListening] = useState(false);

  const audioSessionRef = useRef<MyraaAudioSession | null>(null);

  // Load memories
  const refreshMemories = useCallback(async () => {
    try {
      const res = await fetch("/api/memories");
      if (res.ok) {
        const data = await res.json();
        setMemories(data);
      }
    } catch (e) {
      console.warn("Failed to load memories:", e);
    }
  }, []);

  useEffect(() => {
    refreshMemories();
  }, [refreshMemories]);

  // Polling system health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/agent-health");
        if (res.ok) {
          const data = await res.json();
          dispatch({
            type: "SET_CONNECTIONS",
            node: "connected",
            python: data.online ? "connected" : "offline",
          });
          if (data.system) {
            dispatch({
              type: "SET_SYSTEM_METRICS",
              cpu: data.system.cpu_percent || 0,
              ram: data.system.ram_percent || 0,
              disk: data.system.disk_usage_percent || 0,
            });
          }
        }
      } catch {
        dispatch({
          type: "SET_CONNECTIONS",
          node: "connected",
          python: "offline",
        });
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 8000);
    return () => clearInterval(interval);
  }, [dispatch]);

  // Settings update
  const handleSettingsChange = (patch: Partial<MyraaSettings>) => {
    const updated = saveSettings(patch);
    setSettingsState(updated);
  };

  // Memory operations
  const handleAddMemory = async (category: MemoryCategory, text: string) => {
    try {
      const res = await fetch("/api/memories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, text }),
      });
      if (res.ok) {
        await refreshMemories();
      }
    } catch (e) {
      console.error("Failed to add memory:", e);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      const res = await fetch(`/api/memories/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await refreshMemories();
      }
    } catch (e) {
      console.error("Failed to delete memory:", e);
    }
  };

  // Chat message send
  const handleSendMessage = async (text: string) => {
    const userMsgId = `usr-${Date.now()}`;
    const assistantMsgId = `ast-${Date.now() + 1}`;

    dispatch({
      type: "ADD_CHAT_MESSAGE",
      message: {
        id: userMsgId,
        text,
        isUser: true,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    });

    dispatch({ type: "SET_CORE_STATE", coreState: "thinking" });

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (res.ok) {
        const data = await res.json();
        const replyText = data.text || data.response || data.result || "Command acknowledged.";
        dispatch({
          type: "ADD_CHAT_MESSAGE",
          message: {
            id: assistantMsgId,
            text: replyText,
            isUser: false,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        });
      } else {
        throw new Error(`Chat returned ${res.status}`);
      }
    } catch (err: any) {
      dispatch({
        type: "ADD_CHAT_MESSAGE",
        message: {
          id: assistantMsgId,
          text: `Error processing request: ${err.message || "Network issue"}`,
          isUser: false,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      });
    } finally {
      dispatch({ type: "SET_CORE_STATE", coreState: "idle" });
    }
  };

  // Toggle voice
  const handleToggleVoice = () => {
    if (isListening) {
      audioSessionRef.current?.disconnect();
      audioSessionRef.current = null;
      setIsListening(false);
      dispatch({ type: "SET_VOICE", voice: { connected: false, listening: false } });
      dispatch({ type: "SET_CORE_STATE", coreState: "idle" });
    } else {
      const session = new MyraaAudioSession({
        onStateChange: (state) => {
          if (state === "listening") {
            setIsListening(true);
            dispatch({ type: "SET_VOICE", voice: { connected: true, listening: true, speaking: false } });
            dispatch({ type: "SET_CORE_STATE", coreState: "listening" });
          } else if (state === "speaking") {
            dispatch({ type: "SET_VOICE", voice: { speaking: true, listening: true } });
            dispatch({ type: "SET_CORE_STATE", coreState: "speaking" });
          } else if (state === "thinking") {
            dispatch({ type: "SET_CORE_STATE", coreState: "thinking" });
          } else if (state === "interrupted") {
            dispatch({ type: "SET_VOICE", voice: { speaking: false, listening: true } });
            dispatch({ type: "SET_CORE_STATE", coreState: "listening" });
          } else if (state === "reconnecting") {
            dispatch({ type: "SET_VOICE", voice: { connected: false, listening: false, speaking: false } });
            dispatch({ type: "SET_CORE_STATE", coreState: "recovering" });
          } else if (state === "disconnected" || state === "closed" || state === "error" || state === "degraded") {
            setIsListening(false);
            dispatch({ type: "SET_VOICE", voice: { connected: false, listening: false, speaking: false } });
            dispatch({ type: "SET_CORE_STATE", coreState: "idle" });
          }
        },
        onTranscription: (role, text) => {
          dispatch({
            type: "ADD_CHAT_MESSAGE",
            message: {
              id: `voice-${Date.now()}`,
              text,
              isUser: role === "user",
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            },
          });
        },
      });
      session.connect();
      audioSessionRef.current = session;
      setIsListening(true);
    }
  };

  const navItems = [
    { id: "home", label: "Core", icon: Globe },
    { id: "agents", label: "Agents", icon: Bot },
    { id: "system", label: "Diagnostics", icon: Activity },
    { id: "trading", label: "Trading", icon: TrendingUp },
  ];

  return (
    <div className="flex h-screen w-screen bg-[#030712] text-slate-100 overflow-hidden select-none">
      {/* ── LEFT MINIMAL ICON RAIL ── */}
      <aside className="w-16 flex flex-col items-center py-4 border-r border-white/5 bg-black/40 backdrop-blur-xl z-20 shrink-0">
        {/* Logo */}
        <button
          onClick={() => dispatch({ type: "SET_VIEW", view: "home" })}
          className="mb-8 p-2.5 rounded-2xl bg-gradient-to-tr from-cyan-600 to-indigo-600 text-white shadow-lg shadow-cyan-500/20 hover:scale-105 active:scale-95 transition cursor-pointer"
          title="MYRAA AI"
        >
          <Sparkles size={20} className="animate-pulse" />
        </button>

        {/* Main Navigation */}
        <nav className="flex-1 flex flex-col gap-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = state.activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => dispatch({ type: "SET_VIEW", view: item.id as any })}
                className={`p-3 rounded-xl transition duration-200 cursor-pointer flex flex-col items-center gap-1 ${
                  active
                    ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.25)]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent"
                }`}
                title={item.label}
              >
                <Icon size={18} />
                <span className="text-[8px] font-mono tracking-wider">{item.label}</span>
              </button>
            );
          })}

          {/* Browser Workspace button */}
          <button
            onClick={() => setIsBrowserOpen(true)}
            className="p-3 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent transition cursor-pointer flex flex-col items-center gap-1"
            title="Browser"
          >
            <Compass size={18} />
            <span className="text-[8px] font-mono tracking-wider">Browser</span>
          </button>
        </nav>

        {/* Bottom utility icons */}
        <div className="flex flex-col gap-3 pt-4 border-t border-white/5">
          {/* Voice activation */}
          <button
            onClick={handleToggleVoice}
            className={`p-3 rounded-xl transition cursor-pointer flex flex-col items-center gap-1 ${
              isListening
                ? "bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse"
                : "text-slate-400 hover:text-cyan-400 hover:bg-white/5"
            }`}
            title={isListening ? "Mute Voice" : "Activate Voice"}
          >
            {isListening ? <Mic size={18} /> : <MicOff size={18} />}
            <span className="text-[8px] font-mono tracking-wider">Voice</span>
          </button>

          {/* Chat panel */}
          <button
            onClick={() => dispatch({ type: "TOGGLE_CHAT" })}
            className={`p-3 rounded-xl transition cursor-pointer flex flex-col items-center gap-1 ${
              state.chatOpen
                ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}
            title="Chat Panel"
          >
            <MessageSquare size={18} />
            <span className="text-[8px] font-mono tracking-wider">Chat</span>
          </button>

          {/* Memories */}
          <button
            onClick={() => setIsMemoryOpen(true)}
            className="p-3 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-white/5 transition cursor-pointer flex flex-col items-center gap-1"
            title="Memories"
          >
            <Brain size={18} />
            <span className="text-[8px] font-mono tracking-wider">Memory</span>
          </button>

          {/* Settings */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-3 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-white/5 transition cursor-pointer flex flex-col items-center gap-1"
            title="Settings"
          >
            <Settings size={18} />
            <span className="text-[8px] font-mono tracking-wider">Config</span>
          </button>
        </div>
      </aside>

      {/* ── WORKSPACE VIEWPORT ── */}
      <main className="flex-1 relative overflow-hidden flex flex-col">
        {state.activeView === "home" && <HomeWorkspace />}
        {state.activeView === "agents" && <AgentWorkspace />}
        {state.activeView === "system" && <SystemWorkspace />}
        {state.activeView === "trading" && (
          <TradingDashboard onClose={() => dispatch({ type: "SET_VIEW", view: "home" })} />
        )}
      </main>

      {/* ── OVERLAYS & MODALS ── */}
      {/* Chat drawer */}
      <ChatPanel
        isOpen={state.chatOpen}
        onClose={() => dispatch({ type: "TOGGLE_CHAT" })}
        themeColor={settings.themeColor}
        onSendMessage={handleSendMessage}
        onToggleMic={handleToggleVoice}
        isListening={isListening}
        messages={state.chatMessages}
      />

      {/* Memory Dashboard */}
      <MemoryDashboard
        isOpen={isMemoryOpen}
        onClose={() => setIsMemoryOpen(false)}
        memories={memories}
        onAddMemory={handleAddMemory}
        onDeleteMemory={handleDeleteMemory}
        themeColor={settings.themeColor}
      />

      {/* Settings Panel */}
      <SettingsPanel
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onChange={handleSettingsChange}
        themeColor={settings.themeColor}
      />

      {/* Browser Agent */}
      {isBrowserOpen && (
        <BrowserAgent
          url={browserUrl}
          onClose={() => setIsBrowserOpen(false)}
        />
      )}
    </div>
  );
}
