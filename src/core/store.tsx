/**
 * MYRAA Application State Management
 *
 * Replaces the 8 dead singleton modules in src/core/ with a real
 * React Context + useReducer state management system.
 *
 * State domains: system, chat, task, world, memory, agents, vision,
 * voice, trading, notifications, settings.
 */
import React, { createContext, useContext, useReducer, useEffect, useCallback, useRef } from "react";

// ── State Types ──────────────────────────────────────────────

export type MyraaViewState =
  | "home"
  | "chat"
  | "projects"
  | "agents"
  | "memory"
  | "files"
  | "images"
  | "videos"
  | "tools"
  | "trading"
  | "vision"
  | "automation"
  | "system"
  | "settings";

export type SystemHealth = "healthy" | "degraded" | "error" | "offline";
export type ConnectionStatus = "connected" | "reconnecting" | "degraded" | "offline";
export type MyraaCoreState = "idle" | "listening" | "thinking" | "planning" | "executing" | "observing" | "verifying" | "recovering" | "degraded" | "error" | "speaking";

export interface SystemState {
  health: SystemHealth;
  healthScore: number; // 0-100, computed from real subsystem state
  nodeConnection: ConnectionStatus;
  pythonConnection: ConnectionStatus;
  uptime: number; // seconds
  startTime: number; // epoch ms
  cpuPercent: number;
  ramPercent: number;
  diskPercent: number;
  activeTasks: number;
  coreState: MyraaCoreState;
}

export interface ChatMessage {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: string;
  toolCalls?: ToolCallEvent[];
  streaming?: boolean;
}

export interface ToolCallEvent {
  name: string;
  id: string;
  args: Record<string, unknown>;
  result?: string;
  status: "pending" | "running" | "completed" | "error";
}

export interface TaskState {
  activeGoal: string | null;
  currentStep: string | null;
  completedSteps: string[];
  nextSteps: string[];
  progress: number; // 0-1
  startTime: number | null;
  warnings: string[];
}

export interface Notification {
  id: string;
  type: "task_complete" | "task_failed" | "approval_needed" | "alert" | "system";
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
  priority: "low" | "medium" | "high";
}

export interface MemoryEntry {
  id: string;
  category: string;
  text: string;
  importance: number;
  created_at: string;
  updated_at: string;
}

export interface AgentState {
  id: string;
  name: string;
  skill: string;
  status: "queued" | "running" | "waiting" | "verifying" | "completed" | "failed" | "cancelled" | "recovering";
  progress: number;
  currentStep: string | null;
  latency: number;
  result: string | null;
  error: string | null;
}

export interface TelemetryEvent {
  request_id: string;
  task_id: string;
  timestamp: string;
  component: string;
  route: string;
  intent: string;
  domain: string;
  tool: string;
  status: string;
  latency_ms: number;
}

export interface VoiceState {
  connected: boolean;
  listening: boolean;
  speaking: boolean;
  muted: boolean;
  vadProbability: number;
}

export interface TradingState {
  connected: boolean;
  portfolioLoaded: boolean;
  alertCount: number;
}

export interface WorldModelState {
  entityCount: number;
  relationshipCount: number;
  lastUpdate: string | null;
}

export interface AppState {
  // UI
  activeView: MyraaViewState;
  sidebarOpen: boolean;
  chatOpen: boolean;
  commandPaletteOpen: boolean;

  // System
  system: SystemState;

  // Chat
  chatMessages: ChatMessage[];

  // Task
  task: TaskState;

  // Notifications
  notifications: Notification[];

  // Memory
  memories: MemoryEntry[];

  // Agents
  agents: AgentState[];

  // Telemetry (recent events)
  telemetry: TelemetryEvent[];

  // Voice
  voice: VoiceState;

  // Trading
  trading: TradingState;

  // World Model
  worldModel: WorldModelState;

  // Settings
  settings: Record<string, unknown>;
}

// ── Actions ──────────────────────────────────────────────────

export type AppAction =
  | { type: "SET_VIEW"; view: MyraaViewState }
  | { type: "TOGGLE_SIDEBAR" }
  | { type: "TOGGLE_CHAT" }
  | { type: "TOGGLE_COMMAND_PALETTE" }
  | { type: "SET_SYSTEM_HEALTH"; health: SystemHealth; score: number }
  | { type: "SET_CORE_STATE"; coreState: MyraaCoreState }
  | { type: "SET_CONNECTIONS"; node: ConnectionStatus; python: ConnectionStatus }
  | { type: "SET_SYSTEM_METRICS"; cpu: number; ram: number; disk: number }
  | { type: "SET_UPTIME"; uptime: number }
  | { type: "ADD_CHAT_MESSAGE"; message: ChatMessage }
  | { type: "UPDATE_CHAT_MESSAGE"; id: string; updates: Partial<ChatMessage> }
  | { type: "SET_TASK"; task: Partial<TaskState> }
  | { type: "ADD_NOTIFICATION"; notification: Notification }
  | { type: "MARK_NOTIFICATION_READ"; id: string }
  | { type: "CLEAR_NOTIFICATIONS" }
  | { type: "SET_MEMORIES"; memories: MemoryEntry[] }
  | { type: "SET_AGENTS"; agents: AgentState[] }
  | { type: "ADD_TELEMETRY_EVENT"; event: TelemetryEvent }
  | { type: "SET_VOICE"; voice: Partial<VoiceState> }
  | { type: "SET_TRADING"; trading: Partial<TradingState> }
  | { type: "SET_WORLD_MODEL"; wm: Partial<WorldModelState> }
  | { type: "SET_SETTINGS"; settings: Record<string, unknown> };

// ── Reducer ──────────────────────────────────────────────────

const initialState: AppState = {
  activeView: "home",
  sidebarOpen: false,
  chatOpen: true,
  commandPaletteOpen: false,

  system: {
    health: "healthy",
    healthScore: 100,
    nodeConnection: "offline",
    pythonConnection: "offline",
    uptime: 0,
    startTime: Date.now(),
    cpuPercent: 0,
    ramPercent: 0,
    diskPercent: 0,
    activeTasks: 0,
    coreState: "idle",
  },

  chatMessages: [],
  task: {
    activeGoal: null,
    currentStep: null,
    completedSteps: [],
    nextSteps: [],
    progress: 0,
    startTime: null,
    warnings: [],
  },
  notifications: [],
  memories: [],
  agents: [],
  telemetry: [],
  voice: { connected: false, listening: false, speaking: false, muted: false, vadProbability: 0 },
  trading: { connected: false, portfolioLoaded: false, alertCount: 0 },
  worldModel: { entityCount: 0, relationshipCount: 0, lastUpdate: null },
  settings: {},
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_VIEW":
      return { ...state, activeView: action.view };
    case "TOGGLE_SIDEBAR":
      return { ...state, sidebarOpen: !state.sidebarOpen };
    case "TOGGLE_CHAT":
      return { ...state, chatOpen: !state.chatOpen };
    case "TOGGLE_COMMAND_PALETTE":
      return { ...state, commandPaletteOpen: !state.commandPaletteOpen };
    case "SET_SYSTEM_HEALTH":
      return { ...state, system: { ...state.system, health: action.health, healthScore: action.score } };
    case "SET_CORE_STATE":
      return { ...state, system: { ...state.system, coreState: action.coreState } };
    case "SET_CONNECTIONS":
      return { ...state, system: { ...state.system, nodeConnection: action.node, pythonConnection: action.python } };
    case "SET_SYSTEM_METRICS":
      return { ...state, system: { ...state.system, cpuPercent: action.cpu, ramPercent: action.ram, diskPercent: action.disk } };
    case "SET_UPTIME":
      return { ...state, system: { ...state.system, uptime: action.uptime } };
    case "ADD_CHAT_MESSAGE":
      return { ...state, chatMessages: [...state.chatMessages, action.message].slice(-200) };
    case "UPDATE_CHAT_MESSAGE":
      return {
        ...state,
        chatMessages: state.chatMessages.map(m =>
          m.id === action.id ? { ...m, ...action.updates } : m
        ),
      };
    case "SET_TASK":
      return { ...state, task: { ...state.task, ...action.task } };
    case "ADD_NOTIFICATION":
      return { ...state, notifications: [action.notification, ...state.notifications].slice(0, 100) };
    case "MARK_NOTIFICATION_READ":
      return {
        ...state,
        notifications: state.notifications.map(n =>
          n.id === action.id ? { ...n, read: true } : n
        ),
      };
    case "CLEAR_NOTIFICATIONS":
      return { ...state, notifications: state.notifications.map(n => ({ ...n, read: true })) };
    case "SET_MEMORIES":
      return { ...state, memories: action.memories };
    case "SET_AGENTS":
      return { ...state, agents: action.agents };
    case "ADD_TELEMETRY_EVENT":
      return { ...state, telemetry: [...state.telemetry, action.event].slice(-100) };
    case "SET_VOICE":
      return { ...state, voice: { ...state.voice, ...action.voice } };
    case "SET_TRADING":
      return { ...state, trading: { ...state.trading, ...action.trading } };
    case "SET_WORLD_MODEL":
      return { ...state, worldModel: { ...state.worldModel, ...action.wm } };
    case "SET_SETTINGS":
      return { ...state, settings: action.settings };
    default:
      return state;
  }
}

// ── Context ──────────────────────────────────────────────────

interface AppContextValue {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function useAppStore() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppStore must be used within AppProvider");
  return ctx;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  return React.createElement(AppContext.Provider, { value: { state, dispatch } }, children);
}

// ── Selectors (for memoization) ──────────────────────────────

export const selectSystemHealth = (s: AppState) => s.system;
export const selectChatMessages = (s: AppState) => s.chatMessages;
export const selectActiveView = (s: AppState) => s.activeView;
export const selectNotifications = (s: AppState) => s.notifications;
export const selectAgents = (s: AppState) => s.agents;
export const selectTelemetry = (s: AppState) => s.telemetry;
export const selectVoice = (s: AppState) => s.voice;
export const selectTrading = (s: AppState) => s.trading;
