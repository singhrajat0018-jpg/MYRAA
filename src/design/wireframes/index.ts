// MYRAA Design System — Wireframe Model
// Serializable screen structure definitions

import type {
  WireframeDefinition,
  RegionDefinition,
  DesignConstraint,
  ResponsiveRule,
  ScreenId,
} from "../contracts/index";

// ── Wireframe Builder Helpers ───────────────────────────────
function region(
  id: string,
  name: string,
  opts: {
    gridArea?: string;
    size?: { width: number | string; height: number | string };
    constraints?: DesignConstraint[];
    responsiveRules?: ResponsiveRule[];
    children?: RegionDefinition["children"];
  } = {},
): RegionDefinition {
  return { id, name, ...opts };
}

function constraint(type: DesignConstraint["type"], value: number | string): DesignConstraint {
  return { type, value };
}

function responsive(bp: ResponsiveRule["breakpoint"], behavior: ResponsiveRule["behavior"], value?: number | string): ResponsiveRule {
  return { breakpoint: bp, behavior, value };
}

// ── HOME Wireframe ──────────────────────────────────────────
export const HOME_WIREFRAME: WireframeDefinition = {
  id: "wireframe-home",
  version: "1.0.0",
  screenId: "HOME",
  viewport: "desktop",
  regions: [
    region("home.core", "Core Visualization", {
      size: { width: "100%", height: "100%" },
      constraints: [constraint("alignment", "center")],
      responsiveRules: [responsive("sm", "resize", 280), responsive("lg", "resize", 420)],
      children: [
        { componentId: "myraa-core.visualizer", instanceId: "home-core-main" },
        { componentId: "myraa-core.waveform", instanceId: "home-waveform" },
        { componentId: "myraa-core.caption", instanceId: "home-caption" },
        { componentId: "myraa-core.status-indicator", instanceId: "home-status" },
      ],
    }),
    region("home.sidebar", "Navigation Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      constraints: [constraint("minWidth", 64)],
      responsiveRules: [responsive("sm", "collapse"), responsive("md", "resize", 64)],
      children: [
        { componentId: "navigation.sidebar", instanceId: "home-nav" },
      ],
    }),
    region("home.topbar", "Top Bar", {
      gridArea: "1 / 2 / 2 / 4",
      size: { width: "100%", height: 52 },
      children: [
        { componentId: "navigation.top-bar", instanceId: "home-topbar" },
      ],
    }),
    region("home.voice-hud", "Voice HUD Overlay", {
      size: { width: "auto", height: "auto" },
      constraints: [constraint("alignment", "center")],
      children: [
        { componentId: "myraa-core.voice-hud", instanceId: "home-voice-hud" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 480)],
  responsiveRules: [
    responsive("sm", "reposition"),
    responsive("md", "reorder"),
  ],
  metadata: {
    title: "Home",
    description: "MYRAA voice-first default experience — core visualization, state, voice interaction",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["voice-first", "core", "default"],
  },
};

// ── CHAT Wireframe ──────────────────────────────────────────
export const CHAT_WIREFRAME: WireframeDefinition = {
  id: "wireframe-chat",
  version: "1.0.0",
  screenId: "CHAT",
  viewport: "desktop",
  regions: [
    region("chat.messages", "Chat Messages", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.chat-panel", instanceId: "chat-main" },
      ],
    }),
    region("chat.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "chat-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 480)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Chat",
    description: "Conversational interface with message history",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["chat", "conversation"],
  },
};

// ── BROWSER Wireframe ───────────────────────────────────────
export const BROWSER_WIREFRAME: WireframeDefinition = {
  id: "wireframe-browser",
  version: "1.0.0",
  screenId: "BROWSER",
  viewport: "desktop",
  regions: [
    region("browser.content", "Browser Content", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.panel", instanceId: "browser-frame" },
      ],
    }),
    region("browser.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "browser-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 640)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Browser",
    description: "Web browser workspace — opens the user's Windows default browser (browser-agnostic, no Playwright)",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["browser", "web"],
  },
};

// ── TRADING Wireframe ───────────────────────────────────────
export const TRADING_WIREFRAME: WireframeDefinition = {
  id: "wireframe-trading",
  version: "1.0.0",
  screenId: "TRADING",
  viewport: "desktop",
  regions: [
    region("trading.dashboard", "Trading Dashboard", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.panel", instanceId: "trading-main" },
      ],
    }),
    region("trading.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "trading-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 640)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Trading",
    description: "Trading workspace — market analysis, portfolio, advisory",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["trading", "finance"],
  },
};

// ── SETTINGS Wireframe ──────────────────────────────────────
export const SETTINGS_WIREFRAME: WireframeDefinition = {
  id: "wireframe-settings",
  version: "1.0.0",
  screenId: "SETTINGS",
  viewport: "desktop",
  regions: [
    region("settings.content", "Settings Content", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.panel", instanceId: "settings-main" },
      ],
    }),
    region("settings.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "settings-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 480)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Settings",
    description: "Application settings and configuration",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["settings", "config"],
  },
};

// ── VISION Wireframe ─────────────────────────────────────
export const VISION_WIREFRAME: WireframeDefinition = {
  id: "wireframe-vision",
  version: "1.0.0",
  screenId: "VISION",
  viewport: "desktop",
  regions: [
    region("vision.stream", "Screen Vision Stream", {
      size: { width: "100%", height: "100%" },
      constraints: [constraint("alignment", "center")],
      responsiveRules: [responsive("sm", "resize", 320)],
      children: [
        { componentId: "myraa-core.visualizer", instanceId: "vision-core" },
      ],
    }),
    region("vision.overlay", "Vision Analysis Overlay", {
      size: { width: "100%", height: "auto" },
      constraints: [constraint("alignment", "bottom")],
      children: [
        { componentId: "myraa-core.caption", instanceId: "vision-caption" },
        { componentId: "myraa-core.status-indicator", instanceId: "vision-status" },
      ],
    }),
    region("vision.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "vision-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 480)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Vision",
    description: "Screen observation and vision analysis workspace",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["vision", "screen", "analysis"],
  },
};

// ── DESKTOP Wireframe ────────────────────────────────────
export const DESKTOP_WIREFRAME: WireframeDefinition = {
  id: "wireframe-desktop",
  version: "1.0.0",
  screenId: "DESKTOP",
  viewport: "desktop",
  regions: [
    region("desktop.workspace", "Desktop Control Workspace", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.panel", instanceId: "desktop-main" },
      ],
    }),
    region("desktop.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "desktop-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 640)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Desktop",
    description: "Desktop control and automation workspace",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["desktop", "control", "automation"],
  },
};

// ── MEMORY Wireframe ─────────────────────────────────────
export const MEMORY_WIREFRAME: WireframeDefinition = {
  id: "wireframe-memory",
  version: "1.0.0",
  screenId: "MEMORY",
  viewport: "desktop",
  regions: [
    region("memory.dashboard", "Memory Dashboard", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.panel", instanceId: "memory-main" },
      ],
    }),
    region("memory.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "memory-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 480)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Memory",
    description: "Knowledge base and recollections dashboard",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["memory", "knowledge", "dashboard"],
  },
};

// ── RESEARCH Wireframe ───────────────────────────────────
export const RESEARCH_WIREFRAME: WireframeDefinition = {
  id: "wireframe-research",
  version: "1.0.0",
  screenId: "RESEARCH",
  viewport: "desktop",
  regions: [
    region("research.content", "Research Workspace", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.panel", instanceId: "research-main" },
      ],
    }),
    region("research.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "research-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 640)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Research",
    description: "Web research and knowledge synthesis workspace",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["research", "web", "synthesis"],
  },
};

// ── DESIGN_LAB Wireframe ─────────────────────────────────
export const DESIGN_LAB_WIREFRAME: WireframeDefinition = {
  id: "wireframe-design-lab",
  version: "1.0.0",
  screenId: "DESIGN_LAB",
  viewport: "desktop",
  regions: [
    region("lab.inspector", "Design Inspector", {
      size: { width: 320, height: "100%" },
      constraints: [constraint("minWidth", 280)],
      children: [
        { componentId: "content.panel", instanceId: "lab-inspector" },
      ],
    }),
    region("lab.canvas", "Design Canvas", {
      size: { width: "100%", height: "100%" },
      children: [
        { componentId: "content.panel", instanceId: "lab-canvas" },
      ],
    }),
    region("lab.sidebar", "Sidebar", {
      gridArea: "1 / 1 / 2 / 2",
      size: { width: 200, height: "100%" },
      responsiveRules: [responsive("sm", "collapse")],
      children: [
        { componentId: "navigation.sidebar", instanceId: "lab-nav" },
      ],
    }),
  ],
  constraints: [constraint("minWidth", 800)],
  responsiveRules: [responsive("sm", "reposition")],
  metadata: {
    title: "Design Lab",
    description: "Developer-only design inspection and wireframe viewer",
    createdAt: "2026-09-02",
    updatedAt: "2026-09-02",
    tags: ["design", "lab", "debug", "developer"],
  },
};

// ── All Wireframes ──────────────────────────────────────────
export const ALL_WIREFRAMES: readonly WireframeDefinition[] = [
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
];

const wireframeMap = new Map<string, WireframeDefinition>();
for (const wf of ALL_WIREFRAMES) {
  wireframeMap.set(wf.id, wf);
}

export function getWireframe(id: string): WireframeDefinition | undefined {
  return wireframeMap.get(id);
}

export function getWireframeByScreen(screenId: ScreenId): WireframeDefinition | undefined {
  return ALL_WIREFRAMES.find((wf) => wf.screenId === screenId);
}
