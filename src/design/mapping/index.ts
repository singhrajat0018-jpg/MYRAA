// MYRAA Design System — Implementation Mapping
// Maps design components to actual React implementations

import type { ImplementationMapping, ComponentDefinition, ScreenId } from "../contracts/index";
import { ALL_COMPONENTS, getComponent } from "../components/index";
import { getScreen, getAllScreens } from "../screens/index";

// ── Implementation Map Entry ────────────────────────────────
export interface ImplementationMapEntry {
  readonly designComponentId: string;
  readonly reactComponentPath: string;
  readonly reactComponentName: string;
  readonly status: "mapped" | "partial" | "unmapped";
  readonly notes?: string;
}

// ── Build Implementation Map ────────────────────────────────
export function buildImplementationMap(): readonly ImplementationMapEntry[] {
  return ALL_COMPONENTS.map((comp) => ({
    designComponentId: comp.id,
    reactComponentPath: comp.implementation.componentPath,
    reactComponentName: comp.implementation.componentName,
    status: comp.implementation.status,
    notes: comp.implementation.notes,
  }));
}

// ── Find Unmapped Components ────────────────────────────────
export function findUnmappedComponents(): readonly ComponentDefinition[] {
  return ALL_COMPONENTS.filter((c) => c.implementation.status === "unmapped");
}

// ── Find Partially Mapped Components ────────────────────────
export function findPartiallyMappedComponents(): readonly ComponentDefinition[] {
  return ALL_COMPONENTS.filter((c) => c.implementation.status === "partial");
}

// ── Validate Implementation Mapping ─────────────────────────
export function validateImplementationMapping(): readonly { designId: string; issue: string }[] {
  const issues: { designId: string; issue: string }[] = [];

  for (const comp of ALL_COMPONENTS) {
    if (comp.implementation.status === "mapped" && !comp.implementation.componentPath) {
      issues.push({ designId: comp.id, issue: "Marked as mapped but has no component path" });
    }
    if (comp.implementation.status === "partial" && !comp.implementation.componentPath) {
      issues.push({ designId: comp.id, issue: "Marked as partial but has no component path" });
    }
  }

  return issues;
}

// ── Get Screen Implementation Coverage ──────────────────────
export function getScreenImplementationCoverage(screenId: ScreenId): {
  total: number;
  mapped: number;
  partial: number;
  unmapped: number;
  coverage: number;
} {
  const screen = getScreen(screenId);
  if (!screen) return { total: 0, mapped: 0, partial: 0, unmapped: 0, coverage: 0 };

  const total = screen.implementationMapping.length;
  const mapped = screen.implementationMapping.filter((m) => m.status === "mapped").length;
  const partial = screen.implementationMapping.filter((m) => m.status === "partial").length;
  const unmapped = total - mapped - partial;

  return {
    total,
    mapped,
    partial,
    unmapped,
    coverage: total > 0 ? mapped / total : 0,
  };
}

// ── Get Overall Coverage ────────────────────────────────────
export function getOverallImplementationCoverage(): {
  totalComponents: number;
  mapped: number;
  partial: number;
  unmapped: number;
  coverage: number;
} {
  const total = ALL_COMPONENTS.length;
  const mapped = ALL_COMPONENTS.filter((c) => c.implementation.status === "mapped").length;
  const partial = ALL_COMPONENTS.filter((c) => c.implementation.status === "partial").length;
  const unmapped = total - mapped - partial;

  return {
    totalComponents: total,
    mapped,
    partial,
    unmapped,
    coverage: total > 0 ? mapped / total : 0,
  };
}
