// MYRAA Design System — React Hooks
// Provides typed access to design tokens in React components

import { useMemo } from "react";
import { designTokens, semanticColors, typography, spacing, sizing, radius, elevation, opacity, motion, zIndex, breakpoints, getToken } from "../tokens/index";
import type { ComponentState, ScreenId } from "../contracts/index";

// ── useDesignTokens ──────────────────────────────────────
/** Returns the complete design token object */
export function useDesignTokens() {
  return useMemo(() => designTokens, []);
}

// ── useSemanticColors ────────────────────────────────────
/** Returns semantic color tokens */
export function useSemanticColors() {
  return useMemo(() => semanticColors, []);
}

// ── useTokenValue ────────────────────────────────────────
/** Access any token by dot path. Example: useTokenValue("colors.accent.primary") */
export function useTokenValue(path: string): unknown {
  return useMemo(() => getToken(path), [path]);
}

// ── useCSSVariable ───────────────────────────────────────
/** Returns a CSS var() reference for a design token path */
export function useCSSVariable(tokenPath: string): string {
  return useMemo(() => `var(--${tokenPath.replace(/\./g, "-")})`, [tokenPath]);
}

// ── useComponentStateStyle ───────────────────────────────
/** Returns common style props for a given component state */
export function useStateStyle(state: ComponentState): React.CSSProperties {
  return useMemo(() => {
    switch (state) {
      case "disabled":
        return { opacity: opacity.disabled };
      case "loading":
        return { opacity: opacity.muted };
      case "error":
        return { color: semanticColors.status.error };
      case "success":
        return { color: semanticColors.status.success };
      case "warning":
        return { color: semanticColors.status.warning };
      case "listening":
        return { color: semanticColors.accent.primary };
      case "thinking":
      case "processing":
        return { color: semanticColors.status.info };
      case "speaking":
        return { color: semanticColors.status.success };
      default:
        return {};
    }
  }, [state]);
}

// ── useMYRAAStateColor ───────────────────────────────────
/** Returns the color for a MYRAA voice/core state */
export function useMYRAAStateColor(state: string): string {
  return useMemo(() => {
    switch (state) {
      case "listening": return semanticColors.accent.primary;
      case "thinking":
      case "processing": return semanticColors.status.info;
      case "speaking": return semanticColors.status.success;
      case "interrupted": return semanticColors.status.warning;
      case "offline":
      case "disconnected": return semanticColors.text.muted;
      case "degraded": return semanticColors.status.error;
      default: return semanticColors.text.muted;
    }
  }, [state]);
}

// ── useMYRAAStateLabel ───────────────────────────────────
/** Returns the human-readable label for a MYRAA state */
export function useMYRAAStateLabel(state: string): string {
  return useMemo(() => {
    switch (state) {
      case "disconnected": return "OFFLINE";
      case "connecting": return "CONNECTING";
      case "idle": return "IDLE";
      case "listening": return "LISTENING";
      case "thinking": return "THINKING";
      case "processing": return "PROCESSING";
      case "speaking": return "SPEAKING";
      case "interrupted": return "INTERRUPTED";
      case "offline": return "OFFLINE";
      case "degraded": return "DEGRADED";
      default: return state.toUpperCase();
    }
  }, [state]);
}

// ── useResponsiveValue ───────────────────────────────────
/** Returns a value based on current viewport width vs breakpoints */
export function useResponsiveValue<T>(values: { sm?: T; md?: T; lg?: T; xl?: T; xxl?: T }, fallback: T): T {
  return useMemo(() => {
    if (typeof window === "undefined") return fallback;
    const w = window.innerWidth;
    if (w >= breakpoints.xxl && values.xxl !== undefined) return values.xxl;
    if (w >= breakpoints.xl && values.xl !== undefined) return values.xl;
    if (w >= breakpoints.lg && values.lg !== undefined) return values.lg;
    if (w >= breakpoints.md && values.md !== undefined) return values.md;
    if (w >= breakpoints.sm && values.sm !== undefined) return values.sm;
    return fallback;
  }, [fallback, values.sm, values.md, values.lg, values.xl, values.xxl]);
}

// ── Convenience: commonly used inline styles ─────────────
export const panelStyle: React.CSSProperties = {
  background: semanticColors.background.panel,
  border: `1px solid ${semanticColors.border.secondary}`,
};

export const elevatedPanelStyle: React.CSSProperties = {
  background: semanticColors.background.elevated,
  border: `1px solid ${semanticColors.border.secondary}`,
};

export const accentTextStyle: React.CSSProperties = {
  fontFamily: typography.fontFamily.display,
  color: semanticColors.accent.primary,
  letterSpacing: "0.1em",
};

export const secondaryTextStyle: React.CSSProperties = {
  fontSize: typography.fontSize.sm,
  color: semanticColors.text.secondary,
};

export const mutedTextStyle: React.CSSProperties = {
  fontSize: typography.fontSize.sm,
  color: semanticColors.text.muted,
};
