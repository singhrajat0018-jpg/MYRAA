// MYRAA Design System — Typed Contracts
// Single source of truth for all design system types

// ── Schema Version ──────────────────────────────────────────
export const DESIGN_SCHEMA_VERSION = "1.0.0";

// ── Color Tokens ────────────────────────────────────────────
export interface ColorToken {
  readonly value: string;
  readonly description?: string;
}

export interface ColorScale {
  readonly 50: string;
  readonly 100: string;
  readonly 200: string;
  readonly 300: string;
  readonly 400: string;
  readonly 500: string;
  readonly 600: string;
  readonly 700: string;
  readonly 800: string;
  readonly 900: string;
}

export interface SemanticColors {
  readonly background: {
    readonly base: string;
    readonly panel: string;
    readonly card: string;
    readonly elevated: string;
    readonly hover: string;
    readonly active: string;
    readonly overlay: string;
  };
  readonly border: {
    readonly primary: string;
    readonly secondary: string;
    readonly subtle: string;
    readonly active: string;
    readonly focus: string;
  };
  readonly text: {
    readonly primary: string;
    readonly secondary: string;
    readonly muted: string;
    readonly accent: string;
    readonly inverse: string;
    readonly disabled: string;
  };
  readonly status: {
    readonly success: string;
    readonly successDim: string;
    readonly warning: string;
    readonly warningDim: string;
    readonly error: string;
    readonly errorDim: string;
    readonly info: string;
    readonly infoDim: string;
  };
  readonly accent: {
    readonly primary: string;
    readonly primaryDim: string;
    readonly secondary: string;
    readonly secondaryDim: string;
    readonly tertiary: string;
  };
  readonly myraa: {
    readonly glow: string;
    readonly glowStrong: string;
    readonly core: string;
    readonly voice: string;
  };
}

// ── Typography Tokens ───────────────────────────────────────
export interface TypographyTokens {
  readonly fontFamily: {
    readonly sans: string;
    readonly display: string;
    readonly mono: string;
  };
  readonly fontSize: {
    readonly xs: number;
    readonly sm: number;
    readonly md: number;
    readonly base: number;
    readonly lg: number;
    readonly xl: number;
    readonly xxl: number;
    readonly display: number;
  };
  readonly fontWeight: {
    readonly normal: number;
    readonly medium: number;
    readonly semibold: number;
    readonly bold: number;
  };
  readonly lineHeight: {
    readonly tight: number;
    readonly normal: number;
    readonly relaxed: number;
  };
  readonly letterSpacing: {
    readonly tight: string;
    readonly normal: string;
    readonly wide: string;
    readonly wider: string;
    readonly widest: string;
  };
}

// ── Spacing Tokens ──────────────────────────────────────────
export interface SpacingTokens {
  readonly 0: 0;
  readonly xs: number;
  readonly sm: number;
  readonly md: number;
  readonly lg: number;
  readonly xl: number;
  readonly xxl: number;
  readonly xxxl: number;
}

// ── Sizing Tokens ───────────────────────────────────────────
export interface SizingTokens {
  readonly control: {
    readonly heightSm: number;
    readonly heightMd: number;
    readonly heightLg: number;
    readonly widthSm: number;
    readonly widthMd: number;
    readonly widthLg: number;
  };
  readonly icon: {
    readonly sm: number;
    readonly md: number;
    readonly lg: number;
  };
  readonly panel: {
    readonly sidebarWidth: number;
    readonly topBarHeight: number;
    readonly footerHeight: number;
    readonly chatWidth: number;
    readonly systemMonitorWidth: number;
  };
  readonly core: {
    readonly globeSize: number;
    readonly visualizerSize: number;
  };
  readonly modal: {
    readonly sm: number;
    readonly md: number;
    readonly lg: number;
  };
}

// ── Radius Tokens ───────────────────────────────────────────
export interface RadiusTokens {
  readonly none: 0;
  readonly sm: number;
  readonly md: number;
  readonly lg: number;
  readonly xl: number;
  readonly full: string;
}

// ── Elevation Tokens ────────────────────────────────────────
export interface ElevationTokens {
  readonly shadow: {
    readonly sm: string;
    readonly md: string;
    readonly lg: string;
    readonly xl: string;
  };
  readonly glow: {
    readonly sm: string;
    readonly md: string;
    readonly lg: string;
    readonly xl: string;
    readonly cyan: string;
    readonly cyanStrong: string;
    readonly blue: string;
  };
}

// ── Opacity Tokens ──────────────────────────────────────────
export interface OpacityTokens {
  readonly disabled: number;
  readonly overlay: number;
  readonly subtle: number;
  readonly muted: number;
  readonly active: number;
  readonly hover: number;
}

// ── Motion Tokens ───────────────────────────────────────────
export interface MotionTokens {
  readonly duration: {
    readonly instant: number;
    readonly fast: number;
    readonly normal: number;
    readonly slow: number;
    readonly slower: number;
  };
  readonly easing: {
    readonly default: string;
    readonly in: string;
    readonly out: string;
    readonly inOut: string;
    readonly spring: string;
  };
  readonly stagger: {
    readonly sm: number;
    readonly md: number;
    readonly lg: number;
  };
}

// ── Z-Index Tokens ──────────────────────────────────────────
export interface ZIndexTokens {
  readonly base: 0;
  readonly content: 1;
  readonly navigation: 10;
  readonly floating: 20;
  readonly overlay: 30;
  readonly modal: 40;
  readonly system: 50;
  readonly debug: 100;
}

// ── Breakpoint Tokens ───────────────────────────────────────
export interface BreakpointTokens {
  readonly sm: number;
  readonly md: number;
  readonly lg: number;
  readonly xl: number;
  readonly xxl: number;
}

// ── Complete Design Tokens ──────────────────────────────────
export interface DesignTokens {
  readonly version: string;
  readonly colors: SemanticColors;
  readonly typography: TypographyTokens;
  readonly spacing: SpacingTokens;
  readonly sizing: SizingTokens;
  readonly radius: RadiusTokens;
  readonly elevation: ElevationTokens;
  readonly opacity: OpacityTokens;
  readonly motion: MotionTokens;
  readonly zIndex: ZIndexTokens;
  readonly breakpoints: BreakpointTokens;
}

// ── Component State ─────────────────────────────────────────
export type ComponentState =
  | "default"
  | "hover"
  | "focus"
  | "active"
  | "disabled"
  | "loading"
  | "error"
  | "success"
  | "warning"
  // MYRAA-specific states
  | "idle"
  | "listening"
  | "thinking"
  | "processing"
  | "speaking"
  // Panel states
  | "collapsed"
  | "expanded"
  | "interrupted"
  | "offline"
  | "degraded";

// ── Component Category ──────────────────────────────────────
export type ComponentCategory =
  | "foundation"
  | "input"
  | "feedback"
  | "myraa-core"
  | "navigation"
  | "content"
  | "overlay";

// ── Component Definition ────────────────────────────────────
export interface ComponentDefinition {
  readonly id: string;
  readonly name: string;
  readonly category: ComponentCategory;
  readonly description: string;
  readonly states: readonly ComponentState[];
  readonly tokenDependencies: readonly string[];
  readonly responsiveRules: readonly ResponsiveRule[];
  readonly accessibility: AccessibilityMetadata;
  readonly implementation: ImplementationMapping;
  readonly variants?: readonly ComponentVariant[];
  readonly childConstraints?: ChildConstraints;
}

export interface ComponentVariant {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly tokenOverrides: Partial<SemanticColors>;
  readonly styleOverrides?: Readonly<Record<string, string | number>>;
}

export interface AccessibilityMetadata {
  readonly role?: string;
  readonly ariaLabel?: string;
  readonly keyboardInteraction?: string;
  readonly focusBehavior?: string;
  readonly reducedMotion?: string;
}

export interface ImplementationMapping {
  readonly componentPath: string;
  readonly componentName: string;
  readonly status: "mapped" | "partial" | "unmapped";
  readonly notes?: string;
}

export interface ChildConstraints {
  readonly minChildren?: number;
  readonly maxChildren?: number;
  readonly allowedCategories?: readonly ComponentCategory[];
  readonly layout?: "stack" | "row" | "grid" | "自由";
}

// ── Responsive Rule ─────────────────────────────────────────
export interface ResponsiveRule {
  readonly breakpoint: "sm" | "md" | "lg" | "xl" | "xxl";
  readonly behavior: "show" | "hide" | "collapse" | "resize" | "reposition" | "reorder";
  readonly value?: number | string;
}

// ── Region Definition ───────────────────────────────────────
export interface RegionDefinition {
  readonly id: string;
  readonly name: string;
  readonly gridArea?: string;
  readonly position?: { readonly x: number; readonly y: number };
  readonly size?: { readonly width: number | string; readonly height: number | string };
  readonly constraints?: readonly DesignConstraint[];
  readonly responsiveRules?: readonly ResponsiveRule[];
  readonly children?: readonly RegionChild[];
}

export interface RegionChild {
  readonly componentId: string;
  readonly instanceId: string;
  readonly props?: Record<string, unknown>;
  readonly position?: { readonly x: number; readonly y: number };
  readonly size?: { readonly width: number | string; readonly height: number | string };
}

// ── Design Constraint ───────────────────────────────────────
export interface DesignConstraint {
  readonly type: "minWidth" | "maxWidth" | "minHeight" | "maxHeight" | "aspectRatio" | "alignment";
  readonly value: number | string;
}

// ── Wireframe Definition ────────────────────────────────────
export interface WireframeDefinition {
  readonly id: string;
  readonly version: string;
  readonly screenId: string;
  readonly viewport: "narrow" | "desktop" | "wide" | "ultraWide";
  readonly regions: readonly RegionDefinition[];
  readonly constraints: readonly DesignConstraint[];
  readonly responsiveRules: readonly ResponsiveRule[];
  readonly metadata: WireframeMetadata;
}

export interface WireframeMetadata {
  readonly title: string;
  readonly description: string;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly author?: string;
  readonly tags?: readonly string[];
}

// ── Screen Definition ───────────────────────────────────────
export type ScreenId =
  | "HOME"
  | "CHAT"
  | "VISION"
  | "DESKTOP"
  | "BROWSER"
  | "MEMORY"
  | "TRADING"
  | "RESEARCH"
  | "SETTINGS"
  | "DESIGN_LAB";

export interface ScreenDefinition {
  readonly id: ScreenId;
  readonly title: string;
  readonly purpose: string;
  readonly wireframe: WireframeDefinition;
  readonly supportedStates: readonly ComponentState[];
  readonly responsiveBehavior: readonly ResponsiveRule[];
  readonly implementationMapping: readonly ImplementationMapping[];
}

// ── Screen Registry Entry ───────────────────────────────────
export interface ScreenRegistryEntry {
  readonly screen: ScreenDefinition;
  readonly isCanonical: boolean;
  readonly implementationStatus: "complete" | "partial" | "stub";
}

// ── Design Validation ───────────────────────────────────────
export type DesignValidationSeverity = "error" | "warning" | "info";

export interface DesignValidationResult {
  readonly valid: boolean;
  readonly issues: readonly DesignValidationIssue[];
  readonly timestamp: string;
}

export interface DesignValidationIssue {
  readonly severity: DesignValidationSeverity;
  readonly code: string;
  readonly message: string;
  readonly path?: string;
  readonly suggestion?: string;
}

// ── Design Lint ─────────────────────────────────────────────
export interface DesignLintRule {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly severity: DesignValidationSeverity;
  readonly category: "token" | "component" | "wireframe" | "accessibility" | "responsive";
}

export interface DesignLintResult {
  readonly ruleId: string;
  readonly severity: DesignValidationSeverity;
  readonly message: string;
  readonly file?: string;
  readonly line?: number;
  readonly column?: number;
}

// ── Design Lab ──────────────────────────────────────────────
export interface DesignLabState {
  readonly selectedScreen: ScreenId;
  readonly selectedComponent?: string;
  readonly selectedState: ComponentState;
  readonly viewport: "narrow" | "desktop" | "wide" | "ultraWide";
  readonly showGrid: boolean;
  readonly showGuides: boolean;
  readonly showRegionOutlines: boolean;
  readonly showComponentIds: boolean;
  readonly showDimensions: boolean;
  readonly showSpacing: boolean;
  readonly showTokenInspection: boolean;
  readonly designMode: boolean;
}

// ── Motion Preset ───────────────────────────────────────────
export interface MotionPreset {
  readonly name: string;
  readonly enter: { readonly duration: number; readonly easing: string };
  readonly exit: { readonly duration: number; readonly easing: string };
  readonly hover?: { readonly duration: number; readonly easing: string };
  readonly focus?: { readonly duration: number; readonly easing: string };
}

// ── MYRAA Core State Machine ────────────────────────────────
export type MyraaCoreState =
  | "idle"
  | "listening"
  | "thinking"
  | "processing"
  | "speaking"
  | "interrupted"
  | "offline"
  | "degraded";

export interface MyraaCoreTransition {
  readonly from: MyraaCoreState;
  readonly to: MyraaCoreState;
  readonly trigger: string;
  readonly description: string;
}
