// MYRAA Design System — Screen Registry
// Canonical screen definitions with wireframes and implementation mapping

import type {
  ScreenDefinition,
  ScreenRegistryEntry,
  ScreenId,
  ResponsiveRule,
  ImplementationMapping,
  ComponentState,
} from "../contracts/index";
import {
  HOME_WIREFRAME,
  CHAT_WIREFRAME,
  VISION_WIREFRAME,
  DESKTOP_WIREFRAME,
  BROWSER_WIREFRAME,
  MEMORY_WIREFRAME,
  TRADING_WIREFRAME,
  RESEARCH_WIREFRAME,
  SETTINGS_WIREFRAME,
  DESIGN_LAB_WIREFRAME,
} from "../wireframes/index";

// ── Screen Definitions ──────────────────────────────────────
const HOME_SCREEN: ScreenDefinition = {
  id: "HOME",
  title: "Home",
  purpose: "MYRAA voice-first default experience — core visualization, state, voice interaction",
  wireframe: HOME_WIREFRAME,
  supportedStates: ["idle", "listening", "thinking", "processing", "speaking", "interrupted", "offline", "degraded"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
    { breakpoint: "md", behavior: "reorder" },
  ],
  implementationMapping: [
    { componentPath: "ui/CoreVisualization.tsx", componentName: "CoreVisualization", status: "mapped" },
    { componentPath: "ui/VoiceHUD.tsx", componentName: "VoiceHUD", status: "mapped" },
    { componentPath: "ui/Sidebar.tsx", componentName: "Sidebar", status: "mapped" },
    { componentPath: "ui/TopBar.tsx", componentName: "TopBar", status: "mapped" },
  ],
};

const CHAT_SCREEN: ScreenDefinition = {
  id: "CHAT",
  title: "Chat",
  purpose: "Conversational interface with message history and context",
  wireframe: CHAT_WIREFRAME,
  supportedStates: ["default", "loading", "error"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [
    { componentPath: "ui/ChatPanel.tsx", componentName: "ChatPanel", status: "mapped" },
    { componentPath: "ui/Sidebar.tsx", componentName: "Sidebar", status: "mapped" },
  ],
};

const VISION_SCREEN: ScreenDefinition = {
  id: "VISION",
  title: "Vision",
  purpose: "Screen capture and vision analysis workspace",
  wireframe: VISION_WIREFRAME,
  supportedStates: ["default", "loading"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [
    { componentPath: "ui/CoreVisualization.tsx", componentName: "CoreVisualization", status: "partial" },
  ],
};

const DESKTOP_SCREEN: ScreenDefinition = {
  id: "DESKTOP",
  title: "Desktop",
  purpose: "Desktop control and automation workspace",
  wireframe: DESKTOP_WIREFRAME,
  supportedStates: ["default", "loading"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [
    { componentPath: "components/AgentWorkspace.tsx", componentName: "AgentWorkspace", status: "partial" },
  ],
};

const BROWSER_SCREEN: ScreenDefinition = {
  id: "BROWSER",
  title: "Browser",
  purpose: "Web browsing workspace — opens the user's Windows default browser (browser-agnostic)",
  wireframe: BROWSER_WIREFRAME,
  supportedStates: ["default", "loading", "error"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [
    { componentPath: "components/BrowserAgent.tsx", componentName: "BrowserAgent", status: "mapped" },
  ],
};

const MEMORY_SCREEN: ScreenDefinition = {
  id: "MEMORY",
  title: "Memory",
  purpose: "Memory management and review workspace",
  wireframe: MEMORY_WIREFRAME,
  supportedStates: ["default", "loading"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [
    { componentPath: "components/MemoryDashboard.tsx", componentName: "MemoryDashboard", status: "mapped" },
  ],
};

const TRADING_SCREEN: ScreenDefinition = {
  id: "TRADING",
  title: "Trading",
  purpose: "Trading workspace — market analysis, portfolio, advisory",
  wireframe: TRADING_WIREFRAME,
  supportedStates: ["default", "loading", "error", "offline"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [
    { componentPath: "components/TradingDashboard.tsx", componentName: "TradingDashboard", status: "mapped" },
  ],
};

const RESEARCH_SCREEN: ScreenDefinition = {
  id: "RESEARCH",
  title: "Research",
  purpose: "Web research and information synthesis workspace",
  wireframe: RESEARCH_WIREFRAME,
  supportedStates: ["default", "loading"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [],
};

const SETTINGS_SCREEN: ScreenDefinition = {
  id: "SETTINGS",
  title: "Settings",
  purpose: "Application settings and configuration",
  wireframe: SETTINGS_WIREFRAME,
  supportedStates: ["default"],
  responsiveBehavior: [
    { breakpoint: "sm", behavior: "reposition" },
  ],
  implementationMapping: [
    { componentPath: "components/SettingsPanel.tsx", componentName: "SettingsPanel", status: "mapped" },
  ],
};

const DESIGN_LAB_SCREEN: ScreenDefinition = {
  id: "DESIGN_LAB",
  title: "Design Lab",
  purpose: "Developer-only design inspection and validation tool",
  wireframe: DESIGN_LAB_WIREFRAME,
  supportedStates: ["default"],
  responsiveBehavior: [],
  implementationMapping: [
    { componentPath: "design/lab/DesignLab.tsx", componentName: "DesignLab", status: "partial" },
  ],
};

// ── Screen Registry ─────────────────────────────────────────
const ALL_SCREENS: readonly ScreenDefinition[] = [
  HOME_SCREEN,
  CHAT_SCREEN,
  VISION_SCREEN,
  DESKTOP_SCREEN,
  BROWSER_SCREEN,
  MEMORY_SCREEN,
  TRADING_SCREEN,
  RESEARCH_SCREEN,
  SETTINGS_SCREEN,
  DESIGN_LAB_SCREEN,
];

const screenRegistry = new Map<ScreenId, ScreenRegistryEntry>();
for (const screen of ALL_SCREENS) {
  screenRegistry.set(screen.id, {
    screen,
    isCanonical: true,
    implementationStatus: screen.implementationMapping.length > 0 ? "complete" : "stub",
  });
}

export function getScreen(id: ScreenId): ScreenDefinition | undefined {
  return screenRegistry.get(id)?.screen;
}

export function getScreenRegistryEntry(id: ScreenId): ScreenRegistryEntry | undefined {
  return screenRegistry.get(id);
}

export function getAllScreens(): readonly ScreenDefinition[] {
  return ALL_SCREENS;
}

export function getAllScreenIds(): readonly ScreenId[] {
  return ALL_SCREENS.map((s) => s.id);
}

export function isValidScreenId(id: string): id is ScreenId {
  return screenRegistry.has(id as ScreenId);
}

export function getCanonicalScreens(): readonly ScreenDefinition[] {
  return ALL_SCREENS.filter((_, i) => screenRegistry.get(ALL_SCREENS[i].id)?.isCanonical);
}

export function getScreenImplementationStatus(id: ScreenId): "complete" | "partial" | "stub" | undefined {
  return screenRegistry.get(id)?.implementationStatus;
}
