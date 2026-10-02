// MYRAA Design System — Component Registry
// Canonical component definitions with states, categories, and implementation mapping

import type {
  ComponentDefinition,
  ComponentCategory,
  ComponentState,
  SemanticColors,
} from "../contracts/index";

// ── Foundation Components ───────────────────────────────────
const FOUNDATION_COMPONENTS: readonly ComponentDefinition[] = [
  {
    id: "foundation.box",
    name: "Box",
    category: "foundation",
    description: "Primitive container with token-driven styling",
    states: ["default", "hover", "active", "disabled"],
    tokenDependencies: ["colors.background", "colors.border", "radius"],
    responsiveRules: [],
    accessibility: { role: "presentation" },
    implementation: { componentPath: "div", componentName: "Box", status: "mapped" },
    childConstraints: { layout: "自由" },
  },
  {
    id: "foundation.stack",
    name: "Stack",
    category: "foundation",
    description: "Vertical flex container with spacing",
    states: ["default"],
    tokenDependencies: ["spacing"],
    responsiveRules: [],
    accessibility: { role: "presentation" },
    implementation: { componentPath: "div", componentName: "Stack", status: "mapped" },
    childConstraints: { layout: "stack" },
  },
  {
    id: "foundation.row",
    name: "Row",
    category: "foundation",
    description: "Horizontal flex container with spacing",
    states: ["default"],
    tokenDependencies: ["spacing"],
    responsiveRules: [],
    accessibility: { role: "presentation" },
    implementation: { componentPath: "div", componentName: "Row", status: "mapped" },
    childConstraints: { layout: "row" },
  },
  {
    id: "foundation.grid",
    name: "Grid",
    category: "foundation",
    description: "CSS Grid layout with configurable columns",
    states: ["default"],
    tokenDependencies: ["spacing", "breakpoints"],
    responsiveRules: [
      { breakpoint: "sm", behavior: "resize", value: 1 },
      { breakpoint: "md", behavior: "resize", value: 2 },
      { breakpoint: "lg", behavior: "resize", value: 4 },
    ],
    accessibility: { role: "presentation" },
    implementation: { componentPath: "div", componentName: "Grid", status: "mapped" },
    childConstraints: { layout: "grid" },
  },
  {
    id: "foundation.surface",
    name: "Surface",
    category: "foundation",
    description: "Themed surface with glass-morphism support",
    states: ["default", "hover", "active"],
    tokenDependencies: ["colors.background", "colors.border", "elevation", "radius", "opacity"],
    responsiveRules: [],
    accessibility: { role: "presentation" },
    implementation: { componentPath: "div", componentName: "Surface", status: "mapped" },
  },
  {
    id: "foundation.text",
    name: "Text",
    category: "foundation",
    description: "Themed text with hierarchy levels",
    states: ["default", "disabled"],
    tokenDependencies: ["colors.text", "typography"],
    responsiveRules: [],
    accessibility: {},
    implementation: { componentPath: "span", componentName: "Text", status: "mapped" },
  },
  {
    id: "foundation.icon",
    name: "Icon",
    category: "foundation",
    description: "Icon wrapper with standard sizing",
    states: ["default", "disabled"],
    tokenDependencies: ["colors.text", "sizing.icon"],
    responsiveRules: [],
    accessibility: { role: "img" },
    implementation: { componentPath: "lucide-react", componentName: "Icon", status: "mapped" },
  },
  {
    id: "foundation.divider",
    name: "Divider",
    category: "foundation",
    description: "Horizontal/vertical separator line",
    states: ["default"],
    tokenDependencies: ["colors.border", "spacing"],
    responsiveRules: [],
    accessibility: { role: "separator" },
    implementation: { componentPath: "hr", componentName: "Divider", status: "mapped" },
  },
] as const;

// ── Input Components ────────────────────────────────────────
const INPUT_COMPONENTS: readonly ComponentDefinition[] = [
  {
    id: "input.button",
    name: "Button",
    category: "input",
    description: "Standard action button",
    states: ["default", "hover", "focus", "active", "disabled", "loading"],
    tokenDependencies: ["colors.accent", "colors.text", "spacing", "radius", "motion"],
    responsiveRules: [],
    accessibility: {
      role: "button",
      keyboardInteraction: "Enter/Space activates",
      focusBehavior: "visible focus ring",
    },
    implementation: { componentPath: "components/Button.tsx", componentName: "Button", status: "partial" },
    variants: [
      { id: "primary", name: "Primary", description: "Accent-colored action button", tokenOverrides: {} as Partial<SemanticColors>, styleOverrides: { fontWeight: "600" } },
      { id: "secondary", name: "Secondary", description: "Subtle action button", tokenOverrides: {} as Partial<SemanticColors>, styleOverrides: { background: "rgba(255,255,255,0.05)" } },
      { id: "danger", name: "Danger", description: "Destructive action button", tokenOverrides: {} as Partial<SemanticColors>, styleOverrides: {} },
    ],
  },
  {
    id: "input.icon-button",
    name: "IconButton",
    category: "input",
    description: "Icon-only action button",
    states: ["default", "hover", "focus", "active", "disabled"],
    tokenDependencies: ["colors.accent", "spacing", "radius"],
    responsiveRules: [],
    accessibility: { role: "button", keyboardInteraction: "Enter/Space activates" },
    implementation: { componentPath: "components/IconButton.tsx", componentName: "IconButton", status: "partial" },
  },
  {
    id: "input.text-input",
    name: "TextInput",
    category: "input",
    description: "Single-line text input",
    states: ["default", "hover", "focus", "active", "disabled", "error"],
    tokenDependencies: ["colors.background", "colors.border", "colors.text", "spacing", "radius", "typography"],
    responsiveRules: [],
    accessibility: { role: "textbox", focusBehavior: "visible focus ring" },
    implementation: { componentPath: "components/TextInput.tsx", componentName: "TextInput", status: "partial" },
  },
  {
    id: "input.search",
    name: "Search",
    category: "input",
    description: "Search input with icon",
    states: ["default", "hover", "focus", "active", "disabled"],
    tokenDependencies: ["colors.background", "colors.border", "colors.text", "spacing", "radius"],
    responsiveRules: [],
    accessibility: { role: "searchbox" },
    implementation: { componentPath: "components/Search.tsx", componentName: "Search", status: "partial" },
  },
  {
    id: "input.toggle",
    name: "Toggle",
    category: "input",
    description: "On/off toggle switch",
    states: ["default", "hover", "focus", "disabled"],
    tokenDependencies: ["colors.accent", "colors.background", "spacing", "radius", "motion"],
    responsiveRules: [],
    accessibility: { role: "switch", keyboardInteraction: "Enter/Space toggles" },
    implementation: { componentPath: "components/Toggle.tsx", componentName: "Toggle", status: "partial" },
  },
  {
    id: "input.command-input",
    name: "CommandInput",
    category: "input",
    description: "MYRAA voice/text command input",
    states: ["default", "hover", "focus", "listening", "thinking", "processing"],
    tokenDependencies: ["colors.accent", "colors.background", "colors.text", "spacing", "radius", "motion"],
    responsiveRules: [],
    accessibility: { role: "textbox" },
    implementation: { componentPath: "ui/ChatPanel.tsx", componentName: "ChatPanel", status: "partial" },
  },
] as const;

// ── Feedback Components ─────────────────────────────────────
const FEEDBACK_COMPONENTS: readonly ComponentDefinition[] = [
  {
    id: "feedback.status",
    name: "Status",
    category: "feedback",
    description: "Status indicator dot with label",
    states: ["default", "success", "error", "warning"],
    tokenDependencies: ["colors.status", "spacing", "typography"],
    responsiveRules: [],
    accessibility: { role: "status" },
    implementation: { componentPath: "ui/CoreStatus.tsx", componentName: "CoreStatus", status: "partial" },
  },
  {
    id: "feedback.badge",
    name: "Badge",
    category: "feedback",
    description: "Small status/count badge",
    states: ["default", "success", "error", "warning"],
    tokenDependencies: ["colors.status", "colors.text", "radius", "typography"],
    responsiveRules: [],
    accessibility: {},
    implementation: { componentPath: "components/Badge.tsx", componentName: "Badge", status: "partial" },
  },
  {
    id: "feedback.progress",
    name: "Progress",
    category: "feedback",
    description: "Progress indicator bar",
    states: ["default", "loading", "success", "error"],
    tokenDependencies: ["colors.accent", "colors.status", "radius", "motion"],
    responsiveRules: [],
    accessibility: { role: "progressbar" },
    implementation: { componentPath: "components/Progress.tsx", componentName: "Progress", status: "partial" },
  },
  {
    id: "feedback.loader",
    name: "Loader",
    category: "feedback",
    description: "Loading spinner/indicator",
    states: ["loading"],
    tokenDependencies: ["colors.accent", "motion"],
    responsiveRules: [],
    accessibility: { role: "status" },
    implementation: { componentPath: "components/Loader.tsx", componentName: "Loader", status: "partial" },
  },
  {
    id: "feedback.toast",
    name: "Toast",
    category: "feedback",
    description: "Temporary notification popup",
    states: ["default", "success", "error", "warning"],
    tokenDependencies: ["colors.background", "colors.status", "colors.text", "elevation", "radius", "motion"],
    responsiveRules: [],
    accessibility: { role: "alert" },
    implementation: { componentPath: "components/Toast.tsx", componentName: "Toast", status: "partial" },
  },
] as const;

// ── MYRAA Core Components ───────────────────────────────────
const MYRAA_CORE_COMPONENTS: readonly ComponentDefinition[] = [
  {
    id: "myraa-core.visualizer",
    name: "CoreVisualizer",
    category: "myraa-core",
    description: "Central MYRAA core visualization (globe/orb)",
    states: ["idle", "listening", "thinking", "processing", "speaking", "offline", "degraded"],
    tokenDependencies: ["colors.myraa", "colors.accent", "motion", "sizing.core"],
    responsiveRules: [
      { breakpoint: "sm", behavior: "resize", value: 280 },
      { breakpoint: "md", behavior: "resize", value: 360 },
      { breakpoint: "lg", behavior: "resize", value: 420 },
    ],
    accessibility: { role: "img", ariaLabel: "MYRAA core visualization" },
    implementation: { componentPath: "ui/CoreVisualization.tsx", componentName: "CoreVisualization", status: "mapped" },
  },
  {
    id: "myraa-core.voice-hud",
    name: "VoiceHUD",
    category: "myraa-core",
    description: "Voice interaction status overlay",
    states: ["idle", "listening", "thinking", "processing", "speaking", "interrupted"],
    tokenDependencies: ["colors.myraa", "colors.text", "motion", "typography"],
    responsiveRules: [],
    accessibility: { role: "status", ariaLabel: "Voice interaction status" },
    implementation: { componentPath: "ui/VoiceHUD.tsx", componentName: "VoiceHUD", status: "mapped" },
  },
  {
    id: "myraa-core.waveform",
    name: "Waveform",
    category: "myraa-core",
    description: "Audio waveform visualization",
    states: ["idle", "listening", "speaking"],
    tokenDependencies: ["colors.accent", "colors.myraa", "motion", "sizing"],
    responsiveRules: [],
    accessibility: { role: "img", ariaLabel: "Audio waveform" },
    implementation: { componentPath: "ui/ChatPanel.tsx", componentName: "ChatPanel", status: "partial" },
  },
  {
    id: "myraa-core.caption",
    name: "Caption",
    category: "myraa-core",
    description: "Voice transcription caption overlay",
    states: ["default", "listening", "speaking"],
    tokenDependencies: ["colors.text", "colors.background", "typography", "radius"],
    responsiveRules: [],
    accessibility: { role: "status" },
    implementation: { componentPath: "ui/VoiceHUD.tsx", componentName: "VoiceHUD", status: "partial" },
  },
  {
    id: "myraa-core.status-indicator",
    name: "StatusIndicator",
    category: "myraa-core",
    description: "MYRAA overall status (online/offline/degraded)",
    states: ["default", "offline", "degraded"],
    tokenDependencies: ["colors.status", "colors.text", "spacing", "typography"],
    responsiveRules: [],
    accessibility: { role: "status" },
    implementation: { componentPath: "ui/CoreStatus.tsx", componentName: "CoreStatus", status: "mapped" },
  },
] as const;

// ── Navigation Components ───────────────────────────────────
const NAVIGATION_COMPONENTS: readonly ComponentDefinition[] = [
  {
    id: "navigation.sidebar",
    name: "Sidebar",
    category: "navigation",
    description: "Primary navigation sidebar",
    states: ["default", "collapsed"],
    tokenDependencies: ["colors.background", "colors.border", "colors.text", "colors.accent", "sizing.panel", "spacing", "radius", "zIndex"],
    responsiveRules: [
      { breakpoint: "sm", behavior: "collapse" },
      { breakpoint: "md", behavior: "resize", value: 64 },
    ],
    accessibility: { role: "navigation", keyboardInteraction: "Arrow keys navigate" },
    implementation: { componentPath: "ui/Sidebar.tsx", componentName: "Sidebar", status: "mapped" },
  },
  {
    id: "navigation.top-bar",
    name: "TopBar",
    category: "navigation",
    description: "Top status and action bar",
    states: ["default"],
    tokenDependencies: ["colors.background", "colors.border", "colors.status", "colors.text", "sizing.panel", "spacing", "zIndex"],
    responsiveRules: [],
    accessibility: { role: "banner" },
    implementation: { componentPath: "ui/TopBar.tsx", componentName: "TopBar", status: "mapped" },
  },
  {
    id: "navigation.footer",
    name: "Footer",
    category: "navigation",
    description: "Bottom status bar",
    states: ["default"],
    tokenDependencies: ["colors.background", "colors.text", "sizing.panel", "spacing"],
    responsiveRules: [],
    accessibility: { role: "contentinfo" },
    implementation: { componentPath: "ui/Footer.tsx", componentName: "Footer", status: "mapped" },
  },
] as const;

// ── Content Components ──────────────────────────────────────
const CONTENT_COMPONENTS: readonly ComponentDefinition[] = [
  {
    id: "content.card",
    name: "Card",
    category: "content",
    description: "Content card container",
    states: ["default", "hover", "active"],
    tokenDependencies: ["colors.background", "colors.border", "radius", "elevation", "spacing"],
    responsiveRules: [],
    accessibility: {},
    implementation: { componentPath: "div", componentName: "Card", status: "mapped" },
  },
  {
    id: "content.panel",
    name: "Panel",
    category: "content",
    description: "Side panel container",
    states: ["default", "expanded", "collapsed"],
    tokenDependencies: ["colors.background", "colors.border", "sizing.panel", "spacing", "radius", "zIndex"],
    responsiveRules: [
      { breakpoint: "sm", behavior: "collapse" },
    ],
    accessibility: { role: "complementary" },
    implementation: { componentPath: "div", componentName: "Panel", status: "mapped" },
    variants: [
      { id: "glass", name: "Glass", description: "Glassmorphism panel", tokenOverrides: {}, styleOverrides: { backdropFilter: "blur(12px)" } },
      { id: "solid", name: "Solid", description: "Solid opaque panel", tokenOverrides: {}, styleOverrides: { backdropFilter: "none" } },
    ],
  },
  {
    id: "content.chat-panel",
    name: "ChatPanel",
    category: "content",
    description: "Chat message list and input",
    states: ["default", "loading", "error"],
    tokenDependencies: ["colors.background", "colors.text", "colors.accent", "spacing", "radius", "sizing.panel"],
    responsiveRules: [
      { breakpoint: "sm", behavior: "resize", value: "100%" },
      { breakpoint: "lg", behavior: "resize", value: 280 },
    ],
    accessibility: { role: "log" },
    implementation: { componentPath: "ui/ChatPanel.tsx", componentName: "ChatPanel", status: "mapped" },
  },
  {
    id: "content.weather-card",
    name: "WeatherCard",
    category: "content",
    description: "Weather information display",
    states: ["default", "loading", "error"],
    tokenDependencies: ["colors.background", "colors.text", "colors.accent", "spacing", "radius"],
    responsiveRules: [],
    accessibility: { role: "region", ariaLabel: "Weather" },
    implementation: { componentPath: "ui/WeatherCard.tsx", componentName: "WeatherCard", status: "mapped" },
  },
  {
    id: "content.news-card",
    name: "NewsCard",
    category: "content",
    description: "News item display",
    states: ["default", "loading", "error"],
    tokenDependencies: ["colors.background", "colors.text", "colors.accent", "spacing", "radius"],
    responsiveRules: [],
    accessibility: { role: "article" },
    implementation: { componentPath: "ui/NewsCard.tsx", componentName: "NewsCard", status: "mapped" },
  },
  {
    id: "content.system-monitor",
    name: "SystemMonitor",
    category: "content",
    description: "System metrics display",
    states: ["default", "loading", "error", "offline"],
    tokenDependencies: ["colors.background", "colors.status", "colors.text", "spacing", "radius", "sizing.panel"],
    responsiveRules: [
      { breakpoint: "sm", behavior: "hide" },
    ],
    accessibility: { role: "region", ariaLabel: "System monitor" },
    implementation: { componentPath: "ui/SystemMonitor.tsx", componentName: "SystemMonitor", status: "mapped" },
  },
] as const;

// ── Overlay Components ──────────────────────────────────────
const OVERLAY_COMPONENTS: readonly ComponentDefinition[] = [
  {
    id: "overlay.modal",
    name: "Modal",
    category: "overlay",
    description: "Modal dialog overlay",
    states: ["default", "loading", "error"],
    tokenDependencies: ["colors.background", "colors.border", "elevation", "radius", "zIndex", "motion"],
    responsiveRules: [],
    accessibility: { role: "dialog", keyboardInteraction: "Escape closes, Tab traps focus" },
    implementation: { componentPath: "components/Modal.tsx", componentName: "Modal", status: "partial" },
    variants: [
      { id: "default", name: "Default", description: "Standard modal dialog", tokenOverrides: {}, styleOverrides: {} },
      { id: "fullscreen", name: "Fullscreen", description: "Full viewport modal", tokenOverrides: {}, styleOverrides: { width: "100%", height: "100%" } },
    ],
  },
  {
    id: "overlay.drawer",
    name: "Drawer",
    category: "overlay",
    description: "Slide-in drawer panel",
    states: ["default"],
    tokenDependencies: ["colors.background", "colors.border", "sizing.panel", "zIndex", "motion"],
    responsiveRules: [
      { breakpoint: "sm", behavior: "resize", value: "100%" },
      { breakpoint: "lg", behavior: "resize", value: 400 },
    ],
    accessibility: { role: "dialog", keyboardInteraction: "Escape closes" },
    implementation: { componentPath: "components/Drawer.tsx", componentName: "Drawer", status: "partial" },
  },
] as const;

// ── All Components ──────────────────────────────────────────
export const ALL_COMPONENTS: readonly ComponentDefinition[] = [
  ...FOUNDATION_COMPONENTS,
  ...INPUT_COMPONENTS,
  ...FEEDBACK_COMPONENTS,
  ...MYRAA_CORE_COMPONENTS,
  ...NAVIGATION_COMPONENTS,
  ...CONTENT_COMPONENTS,
  ...OVERLAY_COMPONENTS,
];

// ── Component Registry ──────────────────────────────────────
const componentMap = new Map<string, ComponentDefinition>();
for (const comp of ALL_COMPONENTS) {
  componentMap.set(comp.id, comp);
}

export function getComponent(id: string): ComponentDefinition | undefined {
  return componentMap.get(id);
}

export function getComponentsByCategory(category: ComponentCategory): readonly ComponentDefinition[] {
  return ALL_COMPONENTS.filter((c) => c.category === category);
}

export function getComponentIds(): readonly string[] {
  return ALL_COMPONENTS.map((c) => c.id);
}

export function isValidComponentId(id: string): boolean {
  return componentMap.has(id);
}

export function getComponentStates(id: string): readonly ComponentState[] | undefined {
  return componentMap.get(id)?.states;
}

export function validateComponentState(id: string, state: string): boolean {
  const comp = componentMap.get(id);
  if (!comp) return false;
  return (comp.states as readonly string[]).includes(state);
}
