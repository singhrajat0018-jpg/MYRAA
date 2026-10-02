// MYRAA Design Tokens — Canonical Source of Truth
// All visual values live here. Components import from this file only.

import type {
  DesignTokens,
  SemanticColors,
  TypographyTokens,
  SpacingTokens,
  SizingTokens,
  RadiusTokens,
  ElevationTokens,
  OpacityTokens,
  MotionTokens,
  ZIndexTokens,
  BreakpointTokens,
} from "../contracts";

// ── Semantic Colors ─────────────────────────────────────────
export const semanticColors: SemanticColors = {
  background: {
    base: "#070b14",
    panel: "rgba(8, 12, 24, 0.85)",
    card: "rgba(12, 18, 35, 0.9)",
    elevated: "rgba(16, 22, 40, 0.95)",
    hover: "rgba(0, 212, 255, 0.05)",
    active: "rgba(0, 212, 255, 0.08)",
    overlay: "rgba(0, 0, 0, 0.6)",
  },
  border: {
    primary: "rgba(0, 212, 255, 0.15)",
    secondary: "rgba(0, 212, 255, 0.08)",
    subtle: "rgba(255, 255, 255, 0.04)",
    active: "rgba(0, 212, 255, 0.4)",
    focus: "rgba(0, 212, 255, 0.6)",
  },
  text: {
    primary: "#e0e8ff",
    secondary: "#7a8599",
    muted: "#4a5568",
    accent: "#00d4ff",
    inverse: "#070b14",
    disabled: "rgba(224, 232, 255, 0.35)",
  },
  status: {
    success: "#00e88a",
    successDim: "#00aa55",
    warning: "#ffaa00",
    warningDim: "#cc8800",
    error: "#ff4466",
    errorDim: "#cc3355",
    info: "#3388ff",
    infoDim: "#2266cc",
  },
  accent: {
    primary: "#00d4ff",
    primaryDim: "#0088aa",
    secondary: "#3388ff",
    secondaryDim: "#2266cc",
    tertiary: "#7c3aed",
  },
  myraa: {
    glow: "rgba(0, 212, 255, 0.15)",
    glowStrong: "rgba(0, 212, 255, 0.25)",
    core: "#00d4ff",
    voice: "#38bdf8",
  },
} as const;

// ── Typography ──────────────────────────────────────────────
export const typography: TypographyTokens = {
  fontFamily: {
    sans: '"Inter", ui-sans-serif, system-ui, sans-serif',
    display: '"Space Grotesk", sans-serif',
    mono: '"JetBrains Mono", ui-monospace, SFMono-Regular, monospace',
  },
  fontSize: {
    xs: 10,
    sm: 11,
    md: 12,
    base: 13,
    lg: 14,
    xl: 16,
    xxl: 20,
    display: 28,
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  lineHeight: {
    tight: 1.2,
    normal: 1.5,
    relaxed: 1.7,
  },
  letterSpacing: {
    tight: "-0.01em",
    normal: "0",
    wide: "0.05em",
    wider: "0.1em",
    widest: "0.15em",
  },
} as const;

// ── Spacing ─────────────────────────────────────────────────
export const spacing: SpacingTokens = {
  0: 0,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
} as const;

// ── Sizing ──────────────────────────────────────────────────
export const sizing: SizingTokens = {
  control: {
    heightSm: 28,
    heightMd: 32,
    heightLg: 40,
    widthSm: 80,
    widthMd: 120,
    widthLg: 200,
  },
  icon: {
    sm: 14,
    md: 18,
    lg: 24,
  },
  panel: {
    sidebarWidth: 200,
    topBarHeight: 52,
    footerHeight: 36,
    chatWidth: 280,
    systemMonitorWidth: 220,
  },
  core: {
    globeSize: 420,
    visualizerSize: 500,
  },
  modal: {
    sm: 400,
    md: 560,
    lg: 720,
  },
} as const;

// ── Radius ──────────────────────────────────────────────────
export const radius: RadiusTokens = {
  none: 0,
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: "9999px",
} as const;

// ── Elevation ───────────────────────────────────────────────
export const elevation: ElevationTokens = {
  shadow: {
    sm: "0 1px 2px rgba(0, 0, 0, 0.3)",
    md: "0 4px 12px rgba(0, 0, 0, 0.4)",
    lg: "0 8px 24px rgba(0, 0, 0, 0.5)",
    xl: "0 16px 48px rgba(0, 0, 0, 0.6)",
  },
  glow: {
    sm: "0 0 10px rgba(0, 212, 255, 0.1)",
    md: "0 0 20px rgba(0, 212, 255, 0.15)",
    lg: "0 0 30px rgba(0, 212, 255, 0.25)",
    xl: "0 0 40px rgba(0, 212, 255, 0.35)",
    cyan: "0 0 20px rgba(0, 212, 255, 0.15)",
    cyanStrong: "0 0 30px rgba(0, 212, 255, 0.25)",
    blue: "0 0 20px rgba(0, 102, 255, 0.15)",
  },
} as const;

// ── Opacity ─────────────────────────────────────────────────
export const opacity: OpacityTokens = {
  disabled: 0.35,
  overlay: 0.6,
  subtle: 0.05,
  muted: 0.5,
  active: 0.8,
  hover: 0.9,
} as const;

// ── Motion ──────────────────────────────────────────────────
export const motion: MotionTokens = {
  duration: {
    instant: 50,
    fast: 100,
    normal: 200,
    slow: 350,
    slower: 500,
  },
  easing: {
    default: "cubic-bezier(0.4, 0, 0.2, 1)",
    in: "cubic-bezier(0.4, 0, 1, 1)",
    out: "cubic-bezier(0, 0, 0.2, 1)",
    inOut: "cubic-bezier(0.4, 0, 0.2, 1)",
    spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
  },
  stagger: {
    sm: 30,
    md: 60,
    lg: 100,
  },
} as const;

// ── Z-Index ─────────────────────────────────────────────────
export const zIndex: ZIndexTokens = {
  base: 0,
  content: 1,
  navigation: 10,
  floating: 20,
  overlay: 30,
  modal: 40,
  system: 50,
  debug: 100,
} as const;

// ── Breakpoints ─────────────────────────────────────────────
export const breakpoints: BreakpointTokens = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  xxl: 1536,
} as const;

// ── Complete Token Export ───────────────────────────────────
export const designTokens: DesignTokens = {
  version: "1.0.0",
  colors: semanticColors,
  typography,
  spacing,
  sizing,
  radius,
  elevation,
  opacity,
  motion,
  zIndex,
  breakpoints,
} as const;

// ── Convenience Exports ─────────────────────────────────────
export { semanticColors as colors };
export { typography as typo };
export { spacing as sp };
export { sizing as sz };
export { radius as rad };
export { elevation as elev };
export { opacity as op };
export { motion as mot };
export { zIndex as z };
export { breakpoints as bp };

// ── Token Accessor ──────────────────────────────────────────
export function getToken<T>(path: string, tokens: T = designTokens as T): unknown {
  const keys = path.split(".");
  let current: unknown = tokens;
  for (const key of keys) {
    if (current === null || current === undefined) return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

// ── Tailwind Theme Config ───────────────────────────────────
// Generates CSS custom properties from tokens for Tailwind v4 @theme
export function generateThemeCSS(): string {
  return `
:root {
  /* Background */
  --color-bg-base: ${semanticColors.background.base};
  --color-bg-panel: ${semanticColors.background.panel};
  --color-bg-card: ${semanticColors.background.card};
  --color-bg-elevated: ${semanticColors.background.elevated};
  --color-bg-hover: ${semanticColors.background.hover};
  --color-bg-active: ${semanticColors.background.active};
  --color-bg-overlay: ${semanticColors.background.overlay};

  /* Border */
  --color-border-primary: ${semanticColors.border.primary};
  --color-border-secondary: ${semanticColors.border.secondary};
  --color-border-subtle: ${semanticColors.border.subtle};
  --color-border-active: ${semanticColors.border.active};
  --color-border-focus: ${semanticColors.border.focus};

  /* Text */
  --color-text-primary: ${semanticColors.text.primary};
  --color-text-secondary: ${semanticColors.text.secondary};
  --color-text-muted: ${semanticColors.text.muted};
  --color-text-accent: ${semanticColors.text.accent};
  --color-text-inverse: ${semanticColors.text.inverse};
  --color-text-disabled: ${semanticColors.text.disabled};

  /* Status */
  --color-status-success: ${semanticColors.status.success};
  --color-status-warning: ${semanticColors.status.warning};
  --color-status-error: ${semanticColors.status.error};
  --color-status-info: ${semanticColors.status.info};

  /* Accent */
  --color-accent-primary: ${semanticColors.accent.primary};
  --color-accent-secondary: ${semanticColors.accent.secondary};

  /* MYRAA */
  --color-myraa-glow: ${semanticColors.myraa.glow};
  --color-myraa-core: ${semanticColors.myraa.core};

  /* Spacing */
  --spacing-xs: ${spacing.xs}px;
  --spacing-sm: ${spacing.sm}px;
  --spacing-md: ${spacing.md}px;
  --spacing-lg: ${spacing.lg}px;
  --spacing-xl: ${spacing.xl}px;
  --spacing-xxl: ${spacing.xxl}px;
  --spacing-xxxl: ${spacing.xxxl}px;

  /* Radius */
  --radius-sm: ${radius.sm}px;
  --radius-md: ${radius.md}px;
  --radius-lg: ${radius.lg}px;
  --radius-xl: ${radius.xl}px;

  /* Typography */
  --font-sans: ${typography.fontFamily.sans};
  --font-display: ${typography.fontFamily.display};
  --font-mono: ${typography.fontFamily.mono};

  /* Sizing */
  --size-sidebar: ${sizing.panel.sidebarWidth}px;
  --size-topbar: ${sizing.panel.topBarHeight}px;
  --size-footer: ${sizing.panel.footerHeight}px;
  --size-chat: ${sizing.panel.chatWidth}px;

  /* Z-Index */
  --z-base: ${zIndex.base};
  --z-content: ${zIndex.content};
  --z-navigation: ${zIndex.navigation};
  --z-floating: ${zIndex.floating};
  --z-overlay: ${zIndex.overlay};
  --z-modal: ${zIndex.modal};
  --z-system: ${zIndex.system};
  --z-debug: ${zIndex.debug};
}
`;
}
