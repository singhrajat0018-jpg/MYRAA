// MYRAA Design System — Public API
// Single entry point for the entire design system

// ── Version ─────────────────────────────────────────────────
export const DESIGN_SYSTEM_VERSION = "1.0.0";

// ── Contracts ───────────────────────────────────────────────
export type {
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
  ComponentDefinition,
  ComponentVariant,
  ComponentState,
  ComponentCategory,
  AccessibilityMetadata,
  ImplementationMapping,
  ChildConstraints,
  ResponsiveRule,
  RegionDefinition,
  RegionChild,
  DesignConstraint,
  WireframeDefinition,
  WireframeMetadata,
  ScreenDefinition,
  ScreenId,
  ScreenRegistryEntry,
  DesignValidationResult,
  DesignValidationIssue,
  DesignValidationSeverity,
  DesignLintRule,
  DesignLintResult,
  DesignLabState,
  MotionPreset,
  MyraaCoreState,
  MyraaCoreTransition,
} from "./contracts/index";

// ── Tokens ──────────────────────────────────────────────────
export {
  designTokens,
  semanticColors,
  typography,
  spacing,
  sizing,
  radius,
  elevation,
  opacity,
  motion,
  zIndex,
  breakpoints,
  getToken,
  generateThemeCSS,
  colors,
  typo,
  sp,
  sz,
  rad,
  elev,
  op,
  mot,
  z,
  bp,
} from "./tokens/index";

// ── Components ──────────────────────────────────────────────
export {
  ALL_COMPONENTS,
  getComponent,
  getComponentsByCategory,
  getComponentIds,
  isValidComponentId,
  getComponentStates,
  validateComponentState,
} from "./components/index";

// ── Wireframes ──────────────────────────────────────────────
export {
  ALL_WIREFRAMES,
  HOME_WIREFRAME,
  CHAT_WIREFRAME,
  BROWSER_WIREFRAME,
  TRADING_WIREFRAME,
  SETTINGS_WIREFRAME,
  getWireframe,
  getWireframeByScreen,
} from "./wireframes/index";

// ── Screens ─────────────────────────────────────────────────
export {
  getScreen,
  getScreenRegistryEntry,
  getAllScreens,
  getAllScreenIds,
  isValidScreenId,
  getCanonicalScreens,
  getScreenImplementationStatus,
} from "./screens/index";

// ── Validation ──────────────────────────────────────────────
export {
  validateDesignSystem,
  validateWireframeDef,
} from "./validation/index";

// ── Lint ────────────────────────────────────────────────────
export {
  LINT_RULES,
  lintHardcodedColors,
  lintHardcodedSpacing,
  lintFile,
  lintDesignSystem,
  getLintRule,
} from "./validation/lint";

// ── Mapping ─────────────────────────────────────────────────
export {
  buildImplementationMap,
  findUnmappedComponents,
  findPartiallyMappedComponents,
  validateImplementationMapping,
  getScreenImplementationCoverage,
  getOverallImplementationCoverage,
} from "./mapping/index";
export type { ImplementationMapEntry } from "./mapping/index";

// ── Design Lab ──────────────────────────────────────────────
export { DesignLab } from "./lab/DesignLab";
