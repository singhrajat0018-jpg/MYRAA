// MYRAA Design System — Validation Engine
// Validates design definitions for correctness and consistency

import type {
  DesignValidationResult,
  DesignValidationIssue,
  WireframeDefinition,
  ScreenDefinition,
  ComponentDefinition,
  DesignTokens,
  DesignValidationSeverity,
  ScreenId,
} from "../contracts/index";
import { ALL_COMPONENTS, getComponent, isValidComponentId } from "../components/index";
import { ALL_WIREFRAMES } from "../wireframes/index";
import { getAllScreenIds, isValidScreenId, getAllScreens } from "../screens/index";
import { designTokens } from "../tokens/index";

// ── Issue Builder ───────────────────────────────────────────
function issue(
  severity: DesignValidationSeverity,
  code: string,
  message: string,
  path?: string,
  suggestion?: string,
): DesignValidationIssue {
  return { severity, code, message, path, suggestion };
}

// ── Token Validation ────────────────────────────────────────
function validateTokens(tokens: DesignTokens): DesignValidationIssue[] {
  const issues: DesignValidationIssue[] = [];

  // Check required color categories
  const requiredColorKeys = ["background", "border", "text", "status", "accent", "myraa"] as const;
  for (const key of requiredColorKeys) {
    if (!tokens.colors[key]) {
      issues.push(issue("error", "TOKEN_MISSING_COLOR", `Missing color category: ${key}`, `colors.${key}`));
    }
  }

  // Check required typography
  if (!tokens.typography.fontFamily.sans) {
    issues.push(issue("error", "TOKEN_MISSING_FONT", "Missing sans font family", "typography.fontFamily.sans"));
  }

  // Check spacing scale is monotonic
  const spValues = Object.values(tokens.spacing).filter((v): v is number => typeof v === "number" && v > 0);
  for (let i = 1; i < spValues.length; i++) {
    if (spValues[i] <= spValues[i - 1]) {
      issues.push(issue("warning", "TOKEN_SPACING_NON_MONOTONIC", "Spacing scale is not strictly increasing", "spacing"));
    }
  }

  // Check breakpoints are monotonically increasing
  const bpValues = Object.values(tokens.breakpoints);
  for (let i = 1; i < bpValues.length; i++) {
    if (bpValues[i] <= bpValues[i - 1]) {
      issues.push(issue("error", "TOKEN_BREAKPOINTS_ORDER", "Breakpoints must be strictly increasing", "breakpoints"));
    }
  }

  return issues;
}

// ── Component Validation ────────────────────────────────────
function validateComponents(components: readonly ComponentDefinition[]): DesignValidationIssue[] {
  const issues: DesignValidationIssue[] = [];
  const ids = new Set<string>();

  for (const comp of components) {
    // Duplicate ID check
    if (ids.has(comp.id)) {
      issues.push(issue("error", "COMP_DUPLICATE_ID", `Duplicate component ID: ${comp.id}`, comp.id));
    }
    ids.add(comp.id);

    // ID format check (should be category.name)
    if (!comp.id.includes(".")) {
      issues.push(issue("warning", "COMP_ID_FORMAT", `Component ID should use dot notation: ${comp.id}`, comp.id, "Use category.name format"));
    }

    // States check
    if (comp.states.length === 0) {
      issues.push(issue("warning", "COMP_NO_STATES", `Component ${comp.id} has no defined states`, comp.id));
    }

    // Accessibility check for interactive components
    if (comp.category === "input" && !comp.accessibility.role) {
      issues.push(issue("warning", "COMP_MISSING_ROLE", `Interactive component ${comp.id} missing accessibility role`, comp.id));
    }

    // Token dependencies check
    for (const dep of comp.tokenDependencies) {
      const keys = dep.split(".");
      let current: unknown = designTokens;
      for (const key of keys) {
        if (current === null || current === undefined) {
          issues.push(issue("warning", "COMP_INVALID_TOKEN_DEP", `Component ${comp.id} depends on non-existent token: ${dep}`, comp.id));
          break;
        }
        current = (current as Record<string, unknown>)[key];
      }
    }

    // Implementation mapping check
    if (comp.implementation.status === "unmapped") {
      issues.push(issue("info", "COMP_UNMAPPED", `Component ${comp.id} has no implementation mapping`, comp.id));
    }
  }

  return issues;
}

// ── Wireframe Validation ────────────────────────────────────
function validateWireframe(wf: WireframeDefinition): DesignValidationIssue[] {
  const issues: DesignValidationIssue[] = [];

  // Screen ID check
  if (!isValidScreenId(wf.screenId)) {
    issues.push(issue("error", "WF_INVALID_SCREEN", `Wireframe ${wf.id} references invalid screen: ${wf.screenId}`, wf.id));
  }

  // Regions check
  if (wf.regions.length === 0) {
    issues.push(issue("warning", "WF_NO_REGIONS", `Wireframe ${wf.id} has no regions`, wf.id));
  }

  // Region ID uniqueness
  const regionIds = new Set<string>();
  for (const region of wf.regions) {
    if (regionIds.has(region.id)) {
      issues.push(issue("error", "WF_DUPLICATE_REGION", `Duplicate region ID: ${region.id}`, `${wf.id}.${region.id}`));
    }
    regionIds.add(region.id);

    // Component references check
    if (region.children) {
      for (const child of region.children) {
        if (!isValidComponentId(child.componentId)) {
          issues.push(issue("error", "WF_INVALID_COMPONENT", `Region ${region.id} references invalid component: ${child.componentId}`, `${wf.id}.${region.id}`));
        }
      }
    }
  }

  // Version check
  if (!wf.version) {
    issues.push(issue("warning", "WF_NO_VERSION", `Wireframe ${wf.id} has no version`, wf.id));
  }

  return issues;
}

// ── Screen Validation ───────────────────────────────────────
function validateScreens(screens: readonly ScreenDefinition[]): DesignValidationIssue[] {
  const issues: DesignValidationIssue[] = [];
  const ids = new Set<string>();

  for (const screen of screens) {
    // Duplicate check
    if (ids.has(screen.id)) {
      issues.push(issue("error", "SCREEN_DUPLICATE", `Duplicate screen: ${screen.id}`, screen.id));
    }
    ids.add(screen.id);

    // Wireframe validation
    issues.push(...validateWireframe(screen.wireframe));

    // Required HOME screen check
    if (screen.id === "HOME") {
      const hasCore = screen.wireframe.regions.some((r) =>
        r.children?.some((c) => c.componentId.startsWith("myraa-core.")),
      );
      if (!hasCore) {
        issues.push(issue("error", "HOME_NO_CORE", "HOME screen must include MYRAA core components", "HOME"));
      }
    }
  }

  // Check all canonical screens are registered
  const requiredScreens: ScreenId[] = ["HOME", "CHAT", "SETTINGS"];
  for (const req of requiredScreens) {
    if (!ids.has(req)) {
      issues.push(issue("error", "SCREEN_MISSING_REQUIRED", `Required screen not registered: ${req}`, req));
    }
  }

  return issues;
}

// ── Cross-Reference Validation ──────────────────────────────
function validateCrossReferences(): DesignValidationIssue[] {
  const issues: DesignValidationIssue[] = [];

  // Check all component implementation mappings resolve
  for (const comp of ALL_COMPONENTS) {
    if (comp.implementation.status === "mapped" && !comp.implementation.componentPath) {
      issues.push(issue("warning", "XREF_BROKEN_MAP", `Component ${comp.id} marked as mapped but has no path`, comp.id));
    }
  }

  // Check wireframe component refs exist
  for (const wf of ALL_WIREFRAMES) {
    for (const region of wf.regions) {
      if (region.children) {
        for (const child of region.children) {
          if (!getComponent(child.componentId)) {
            issues.push(issue("error", "XREF_MISSING_COMP", `Wireframe ${wf.id} refs non-existent component: ${child.componentId}`, `${wf.id}.${region.id}`));
          }
        }
      }
    }
  }

  return issues;
}

// ── Main Validation ─────────────────────────────────────────
export function validateDesignSystem(): DesignValidationResult {
  const issues: DesignValidationIssue[] = [];

  issues.push(...validateTokens(designTokens));
  issues.push(...validateComponents(ALL_COMPONENTS));
  issues.push(...validateScreens(getAllScreens()));
  issues.push(...validateCrossReferences());

  const errors = issues.filter((i) => i.severity === "error");

  return {
    valid: errors.length === 0,
    issues,
    timestamp: new Date().toISOString(),
  };
}

// ── Validate Single Wireframe ───────────────────────────────
export function validateWireframeDef(wf: WireframeDefinition): DesignValidationResult {
  const issues = validateWireframe(wf);
  return {
    valid: !issues.some((i) => i.severity === "error"),
    issues,
    timestamp: new Date().toISOString(),
  };
}
