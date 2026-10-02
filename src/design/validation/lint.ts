// MYRAA Design System — Design Lint Rules
// Lint rules for detecting design system violations

import type { DesignLintRule, DesignLintResult } from "../contracts/index";
import { ALL_COMPONENTS } from "../components/index";

// ── Lint Rule Definitions ───────────────────────────────────
export const LINT_RULES: readonly DesignLintRule[] = [
  {
    id: "L001",
    name: "hardcoded-color",
    description: "Detect hardcoded color values outside the token system",
    severity: "warning",
    category: "token",
  },
  {
    id: "L002",
    name: "hardcoded-spacing",
    description: "Detect arbitrary spacing values where tokens exist",
    severity: "warning",
    category: "token",
  },
  {
    id: "L003",
    name: "missing-focus-state",
    description: "Interactive component missing focus state",
    severity: "warning",
    category: "component",
  },
  {
    id: "L004",
    name: "missing-disabled-state",
    description: "Interactive component missing disabled state",
    severity: "info",
    category: "component",
  },
  {
    id: "L005",
    name: "missing-loading-state",
    description: "Component that may load data missing loading state",
    severity: "info",
    category: "component",
  },
  {
    id: "L006",
    name: "missing-accessible-label",
    description: "Component missing accessible label or aria-label",
    severity: "warning",
    category: "accessibility",
  },
  {
    id: "L007",
    name: "missing-responsive-behavior",
    description: "Component has no responsive rules defined",
    severity: "info",
    category: "responsive",
  },
  {
    id: "L008",
    name: "duplicate-component-id",
    description: "Two components share the same ID",
    severity: "error",
    category: "component",
  },
  {
    id: "L009",
    name: "invalid-component-ref",
    description: "Wireframe references non-existent component ID",
    severity: "error",
    category: "wireframe",
  },
  {
    id: "L010",
    name: "excessive-nesting",
    description: "Component hierarchy has excessive nesting depth",
    severity: "info",
    category: "wireframe",
  },
  {
    id: "L011",
    name: "inconsistent-typography",
    description: "Mixed typography tokens in same component",
    severity: "warning",
    category: "token",
  },
  {
    id: "L012",
    name: "missing-aria-role",
    description: "Component missing ARIA role definition",
    severity: "warning",
    category: "accessibility",
  },
];

// ── Hardcoded Color Detection ───────────────────────────────
const HARDCODED_COLOR_PATTERNS = [
  /#[0-9a-fA-F]{3,8}(?![0-9a-fA-F])/g,
  /rgba?\(\s*\d+/g,
  /hsla?\(\s*\d+/g,
];

const KNOWN_TOKEN_COLORS = new Set([
  "#070b14", "#020206", "#0c1020",
  "#00d4ff", "#0088aa", "#3388ff", "#2266cc",
  "#00e88a", "#00aa55",
  "#ffaa00", "#cc8800",
  "#ff4466", "#cc3355",
  "#e0e8ff", "#7a8599", "#4a5568",
  "#38bdf8", "#facc15", "#ef4444", "#c0c8e0",
]);

export function lintHardcodedColors(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];
  const lines = fileContent.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes("--color-") || line.includes("export const") || line.includes("import ")) continue;

    for (const pattern of HARDCODED_COLOR_PATTERNS) {
      const matches = line.matchAll(pattern);
      for (const match of matches) {
        const color = match[0];
        if (!KNOWN_TOKEN_COLORS.has(color) && !color.includes("var(--")) {
          results.push({
            ruleId: "L001",
            severity: "warning",
            message: `Hardcoded color ${color} — use design token instead`,
            file: fileName,
            line: i + 1,
            column: match.index,
          });
        }
      }
    }
  }

  return results;
}

// ── Hardcoded Spacing Detection ─────────────────────────────
const TOKEN_SPACING_VALUES = new Set([0, 4, 8, 12, 16, 20, 24, 32]);

export function lintHardcodedSpacing(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];
  const lines = fileContent.split("\n");

  const spacingPattern = /(?:margin|padding|gap|top|right|bottom|left|width|height)[\s]*:[\s]*(\d+)px/g;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes("import ") || line.includes("export const")) continue;

    const matches = line.matchAll(spacingPattern);
    for (const match of matches) {
      const value = parseInt(match[1], 10);
      if (value > 0 && !TOKEN_SPACING_VALUES.has(value) && value < 100) {
        results.push({
          ruleId: "L002",
          severity: "warning",
          message: `Arbitrary spacing ${value}px — consider using design token`,
          file: fileName,
          line: i + 1,
          column: match.index,
        });
      }
    }
  }

  return results;
}

// ── L003: Missing Focus State ────────────────────────────────
const INTERACTIVE_CATEGORIES = new Set(["input"]);

export function lintMissingFocusState(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  for (const comp of ALL_COMPONENTS) {
    if (INTERACTIVE_CATEGORIES.has(comp.category)) {
      const hasFocus = comp.states.includes("focus");
      if (!hasFocus) {
        results.push({
          ruleId: "L003",
          severity: "warning",
          message: `Interactive component ${comp.id} missing focus state`,
          file: fileName,
          line: 0,
        });
      }
    }
  }

  return results;
}

// ── L004: Missing Disabled State ─────────────────────────────
export function lintMissingDisabledState(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  for (const comp of ALL_COMPONENTS) {
    if (INTERACTIVE_CATEGORIES.has(comp.category)) {
      const hasDisabled = comp.states.includes("disabled");
      if (!hasDisabled) {
        results.push({
          ruleId: "L004",
          severity: "info",
          message: `Interactive component ${comp.id} missing disabled state`,
          file: fileName,
          line: 0,
        });
      }
    }
  }

  return results;
}

// ── L005: Missing Loading State ──────────────────────────────
const LOADING_CATEGORIES = new Set(["feedback", "content"]);

export function lintMissingLoadingState(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  for (const comp of ALL_COMPONENTS) {
    if (LOADING_CATEGORIES.has(comp.category)) {
      const hasLoading = comp.states.includes("loading");
      if (!hasLoading) {
        results.push({
          ruleId: "L005",
          severity: "info",
          message: `Component ${comp.id} that may load data missing loading state`,
          file: fileName,
          line: 0,
        });
      }
    }
  }

  return results;
}

// ── L006: Missing Accessible Label ───────────────────────────
export function lintMissingAccessibleLabel(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  for (const comp of ALL_COMPONENTS) {
    if (INTERACTIVE_CATEGORIES.has(comp.category)) {
      const hasLabel = comp.accessibility?.ariaLabel || comp.accessibility?.role;
      if (!hasLabel) {
        results.push({
          ruleId: "L006",
          severity: "warning",
          message: `Interactive component ${comp.id} missing accessible label`,
          file: fileName,
          line: 0,
        });
      }
    }
  }

  return results;
}

// ── L007: Missing Responsive Behavior ────────────────────────
export function lintMissingResponsiveBehavior(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  for (const comp of ALL_COMPONENTS) {
    if (comp.responsiveRules.length === 0 && comp.category !== "foundation") {
      results.push({
        ruleId: "L007",
        severity: "info",
        message: `Component ${comp.id} has no responsive rules defined`,
        file: fileName,
        line: 0,
      });
    }
  }

  return results;
}

// ── L008: Duplicate Component ID ─────────────────────────────
export function lintDuplicateComponentId(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];
  const seen = new Map<string, number>();

  for (const comp of ALL_COMPONENTS) {
    const prev = seen.get(comp.id);
    if (prev !== undefined) {
      results.push({
        ruleId: "L008",
        severity: "error",
        message: `Duplicate component ID: ${comp.id}`,
        file: fileName,
        line: 0,
      });
    }
    seen.set(comp.id, (prev ?? 0) + 1);
  }

  return results;
}

// ── L009: Invalid Component Reference ────────────────────────
export function lintInvalidComponentRef(fileContent: string, fileName: string): DesignLintResult[] {
  // This requires wireframe context — only runs in full validation
  return [];
}

// ── L010: Excessive Nesting ──────────────────────────────────
export function lintExcessiveNesting(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];
  const lines = fileContent.split("\n");
  let maxDepth = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const openBraces = (line.match(/\{/g) || []).length;
    const closeBraces = (line.match(/\}/g) || []).length;
    maxDepth += openBraces - closeBraces;
    if (maxDepth > 8) {
      results.push({
        ruleId: "L010",
        severity: "info",
        message: `Excessive nesting depth (${maxDepth}) at line ${i + 1}`,
        file: fileName,
        line: i + 1,
      });
      break; // Report only once per file
    }
  }

  return results;
}

// ── L011: Inconsistent Typography ────────────────────────────
export function lintInconsistentTypography(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];
  const lines = fileContent.split("\n");

  const fontFamilies = new Set<string>();
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const match = line.match(/fontFamily:\s*["']([^"']+)["']/);
    if (match) {
      fontFamilies.add(match[1]);
    }
  }

  if (fontFamilies.size > 2) {
    results.push({
      ruleId: "L011",
      severity: "warning",
      message: `Mixed font families detected: ${Array.from(fontFamilies).join(", ")}`,
      file: fileName,
      line: 0,
    });
  }

  return results;
}

// ── L012: Missing ARIA Role ──────────────────────────────────
export function lintMissingAriaRole(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  for (const comp of ALL_COMPONENTS) {
    const interactiveCategories = new Set(["input", "navigation", "overlay"]);
    if (interactiveCategories.has(comp.category)) {
      const hasRole = comp.accessibility?.role;
      if (!hasRole) {
        results.push({
          ruleId: "L012",
          severity: "warning",
          message: `Component ${comp.id} missing ARIA role definition`,
          file: fileName,
          line: 0,
        });
      }
    }
  }

  return results;
}

// ── Main Lint Function ──────────────────────────────────────
export function lintFile(fileContent: string, fileName: string): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  if (!fileName.endsWith(".tsx") && !fileName.endsWith(".ts")) return results;
  if (fileName.includes("src/design/")) return results;
  if (fileName.includes("src/tokens/")) return results;

  results.push(...lintHardcodedColors(fileContent, fileName));
  results.push(...lintHardcodedSpacing(fileContent, fileName));

  return results;
}

/** Run all lint rules against the design system itself (not file content) */
export function lintDesignSystem(): DesignLintResult[] {
  const results: DesignLintResult[] = [];

  results.push(...lintMissingFocusState("", "design-system"));
  results.push(...lintMissingDisabledState("", "design-system"));
  results.push(...lintMissingLoadingState("", "design-system"));
  results.push(...lintMissingAccessibleLabel("", "design-system"));
  results.push(...lintMissingResponsiveBehavior("", "design-system"));
  results.push(...lintDuplicateComponentId("", "design-system"));
  results.push(...lintExcessiveNesting("", "design-system"));
  results.push(...lintMissingAriaRole("", "design-system"));

  return results;
}

export function getLintRule(id: string): DesignLintRule | undefined {
  return LINT_RULES.find((r) => r.id === id);
}
