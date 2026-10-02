// MYRAA Design Lab — Developer Inspection Tool
// Gated to development mode, provides visual design inspection

import React, { useState, useCallback, useMemo } from "react";
import type { ScreenId, ComponentState, DesignLabState } from "../contracts/index";
import { getAllScreenIds, getScreen } from "../screens/index";
import { ALL_COMPONENTS, getComponent, getComponentIds } from "../components/index";
import { designTokens } from "../tokens/index";
import { validateDesignSystem } from "../validation/index";

// ── Design Lab State ────────────────────────────────────────
const INITIAL_STATE: DesignLabState = {
  selectedScreen: "HOME",
  selectedState: "idle",
  viewport: "desktop",
  showGrid: false,
  showGuides: false,
  showRegionOutlines: false,
  showComponentIds: false,
  showDimensions: false,
  showSpacing: false,
  showTokenInspection: false,
  designMode: true,
};

// ── Viewport Sizes ──────────────────────────────────────────
const VIEWPORTS = {
  narrow: { width: 480, label: "Narrow (480px)" },
  desktop: { width: 1024, label: "Desktop (1024px)" },
  wide: { width: 1440, label: "Wide (1440px)" },
  ultraWide: { width: 1920, label: "Ultra-wide (1920px)" },
} as const;

// ── MYRAA Core States ───────────────────────────────────────
const MYRAA_STATES: readonly ComponentState[] = [
  "idle", "listening", "thinking", "processing", "speaking",
  "interrupted", "offline", "degraded",
];

// ── DesignLab Component ─────────────────────────────────────
export function DesignLab() {
  const [state, setState] = useState<DesignLabState>(INITIAL_STATE);
  const [validationResult, setValidationResult] = useState(() => validateDesignSystem());

  const screenIds = useMemo(() => getAllScreenIds(), []);
  const screen = useMemo(() => getScreen(state.selectedScreen), [state.selectedScreen]);
  const componentIds = useMemo(() => getComponentIds(), []);

  const toggleOption = useCallback((key: keyof DesignLabState) => {
    setState((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const setScreen = useCallback((id: ScreenId) => {
    setState((prev) => ({ ...prev, selectedScreen: id }));
  }, []);

  const setState_ = useCallback((s: ComponentState) => {
    setState((prev) => ({ ...prev, selectedState: s }));
  }, []);

  const setViewport = useCallback((vp: DesignLabState["viewport"]) => {
    setState((prev) => ({ ...prev, viewport: vp }));
  }, []);

  const vp = VIEWPORTS[state.viewport];

  return (
    <div className="flex h-full" style={{ fontFamily: designTokens.typography.fontFamily.sans }}>
      {/* Sidebar — Controls */}
      <div
        className="flex-shrink-0 overflow-y-auto border-r"
        style={{
          width: 280,
          background: designTokens.colors.background.panel,
          borderColor: designTokens.colors.border.primary,
        }}
      >
        <div className="p-3">
          <h2 className="text-sm font-semibold mb-3" style={{ color: designTokens.colors.text.primary }}>
            Design Lab
          </h2>

          {/* Screen Selector */}
          <Section title="Screen">
            <select
              value={state.selectedScreen}
              onChange={(e) => setScreen(e.target.value as ScreenId)}
              className="w-full text-xs p-1.5 rounded"
              style={{
                background: designTokens.colors.background.base,
                color: designTokens.colors.text.primary,
                border: `1px solid ${designTokens.colors.border.primary}`,
              }}
            >
              {screenIds.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </Section>

          {/* Viewport Selector */}
          <Section title="Viewport">
            <div className="flex flex-wrap gap-1">
              {(Object.keys(VIEWPORTS) as Array<keyof typeof VIEWPORTS>).map((key) => (
                <button
                  key={key}
                  onClick={() => setViewport(key)}
                  className="text-xs px-2 py-1 rounded"
                  style={{
                    background: state.viewport === key ? designTokens.colors.accent.primary : designTokens.colors.background.base,
                    color: state.viewport === key ? designTokens.colors.text.inverse : designTokens.colors.text.secondary,
                    border: `1px solid ${designTokens.colors.border.primary}`,
                  }}
                >
                  {key}
                </button>
              ))}
            </div>
          </Section>

          {/* State Preview */}
          <Section title="Core State">
            <div className="flex flex-wrap gap-1">
              {MYRAA_STATES.map((s) => (
                <button
                  key={s}
                  onClick={() => setState_(s)}
                  className="text-xs px-2 py-1 rounded"
                  style={{
                    background: state.selectedState === s ? designTokens.colors.accent.primary : designTokens.colors.background.base,
                    color: state.selectedState === s ? designTokens.colors.text.inverse : designTokens.colors.text.secondary,
                    border: `1px solid ${designTokens.colors.border.primary}`,
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </Section>

          {/* Toggle Options */}
          <Section title="Display">
            <Toggle label="Grid" checked={state.showGrid} onChange={() => toggleOption("showGrid")} />
            <Toggle label="Guides" checked={state.showGuides} onChange={() => toggleOption("showGuides")} />
            <Toggle label="Region Outlines" checked={state.showRegionOutlines} onChange={() => toggleOption("showRegionOutlines")} />
            <Toggle label="Component IDs" checked={state.showComponentIds} onChange={() => toggleOption("showComponentIds")} />
            <Toggle label="Dimensions" checked={state.showDimensions} onChange={() => toggleOption("showDimensions")} />
            <Toggle label="Token Inspection" checked={state.showTokenInspection} onChange={() => toggleOption("showTokenInspection")} />
          </Section>

          {/* Mode Toggle */}
          <Section title="Mode">
            <div className="flex gap-1">
              <button
                onClick={() => setState((p) => ({ ...p, designMode: true }))}
                className="text-xs px-2 py-1 rounded flex-1"
                style={{
                  background: state.designMode ? designTokens.colors.status.success : designTokens.colors.background.base,
                  color: state.designMode ? designTokens.colors.text.inverse : designTokens.colors.text.secondary,
                  border: `1px solid ${designTokens.colors.border.primary}`,
                }}
              >
                Design
              </button>
              <button
                onClick={() => setState((p) => ({ ...p, designMode: false }))}
                className="text-xs px-2 py-1 rounded flex-1"
                style={{
                  background: !state.designMode ? designTokens.colors.status.success : designTokens.colors.background.base,
                  color: !state.designMode ? designTokens.colors.text.inverse : designTokens.colors.text.secondary,
                  border: `1px solid ${designTokens.colors.border.primary}`,
                }}
              >
                Production
              </button>
            </div>
          </Section>

          {/* Validation Summary */}
          <Section title="Validation">
            <div className="text-xs" style={{ color: designTokens.colors.text.secondary }}>
              <div className="flex justify-between mb-1">
                <span>Errors</span>
                <span style={{ color: designTokens.colors.status.error }}>
                  {validationResult.issues.filter((i) => i.severity === "error").length}
                </span>
              </div>
              <div className="flex justify-between mb-1">
                <span>Warnings</span>
                <span style={{ color: designTokens.colors.status.warning }}>
                  {validationResult.issues.filter((i) => i.severity === "warning").length}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Info</span>
                <span style={{ color: designTokens.colors.status.info }}>
                  {validationResult.issues.filter((i) => i.severity === "info").length}
                </span>
              </div>
            </div>
          </Section>
        </div>
      </div>

      {/* Main Canvas */}
      <div className="flex-1 overflow-auto" style={{ background: designTokens.colors.background.base }}>
        {/* Canvas Header */}
        <div
          className="flex items-center justify-between px-4 py-2 border-b"
          style={{
            background: designTokens.colors.background.panel,
            borderColor: designTokens.colors.border.primary,
          }}
        >
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium" style={{ color: designTokens.colors.text.primary }}>
              {screen?.title || state.selectedScreen}
            </span>
            <span className="text-xs" style={{ color: designTokens.colors.text.muted }}>
              {vp.label}
            </span>
            <span className="text-xs" style={{ color: designTokens.colors.text.muted }}>
              State: {state.selectedState}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: state.designMode ? designTokens.colors.status.success : designTokens.colors.text.muted }}>
              {state.designMode ? "DESIGN" : "PROD"}
            </span>
          </div>
        </div>

        {/* Canvas Content */}
        <div className="flex justify-center p-8">
          <div
            className="relative overflow-hidden"
            style={{
              width: vp.width,
              maxWidth: "100%",
              height: 600,
              background: designTokens.colors.background.base,
              border: state.designMode ? `1px solid ${designTokens.colors.border.active}` : `1px solid ${designTokens.colors.border.secondary}`,
              borderRadius: designTokens.radius.md,
            }}
          >
            {/* Grid Overlay */}
            {state.showGrid && state.designMode && (
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  backgroundImage: `
                    linear-gradient(${designTokens.colors.border.subtle} 1px, transparent 1px),
                    linear-gradient(90deg, ${designTokens.colors.border.subtle} 1px, transparent 1px)
                  `,
                  backgroundSize: "60px 60px",
                }}
              />
            )}

            {/* Region Outlines */}
            {state.showRegionOutlines && state.designMode && screen && (
              <div className="absolute inset-0 pointer-events-none">
                {screen.wireframe.regions.map((region) => (
                  <div
                    key={region.id}
                    className="absolute border border-dashed"
                    style={{
                      borderColor: designTokens.colors.accent.primary,
                      opacity: 0.4,
                      left: 0,
                      top: 0,
                      right: 0,
                      bottom: 0,
                    }}
                  >
                    {state.showComponentIds && (
                      <span
                        className="absolute text-xs px-1"
                        style={{
                          background: designTokens.colors.accent.primary,
                          color: designTokens.colors.text.inverse,
                          top: 2,
                          left: 2,
                          fontSize: 9,
                        }}
                      >
                        {region.id}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Screen Content Placeholder */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div
                  className="text-lg font-semibold mb-2"
                  style={{ color: designTokens.colors.text.primary }}
                >
                  {screen?.title || state.selectedScreen}
                </div>
                <div className="text-xs" style={{ color: designTokens.colors.text.secondary }}>
                  {screen?.purpose || "Screen wireframe preview"}
                </div>
                {state.designMode && (
                  <div className="mt-4 text-xs" style={{ color: designTokens.colors.text.muted }}>
                    {screen?.wireframe.regions.length || 0} regions •{" "}
                    {screen?.wireframe.regions.reduce((acc, r) => acc + (r.children?.length || 0), 0) || 0} components
                  </div>
                )}
              </div>
            </div>

            {/* Token Inspection Panel */}
            {state.showTokenInspection && state.designMode && (
              <div
                className="absolute bottom-0 left-0 right-0 p-2 text-xs overflow-auto"
                style={{
                  maxHeight: 200,
                  background: designTokens.colors.background.elevated,
                  borderTop: `1px solid ${designTokens.colors.border.primary}`,
                  color: designTokens.colors.text.secondary,
                }}
              >
                <div className="font-mono">
                  <div><span style={{ color: designTokens.colors.text.accent }}>version:</span> {designTokens.version}</div>
                  <div><span style={{ color: designTokens.colors.text.accent }}>breakpoints:</span> sm={designTokens.breakpoints.sm} md={designTokens.breakpoints.md} lg={designTokens.breakpoints.lg}</div>
                  <div><span style={{ color: designTokens.colors.text.accent }}>spacing:</span> xs={designTokens.spacing.xs} sm={designTokens.spacing.sm} md={designTokens.spacing.md} lg={designTokens.spacing.lg}</div>
                  <div><span style={{ color: designTokens.colors.text.accent }}>radius:</span> sm={designTokens.radius.sm} md={designTokens.radius.md} lg={designTokens.radius.lg}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Helper Components ───────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="text-xs font-medium mb-1.5" style={{ color: designTokens.colors.text.muted, letterSpacing: "0.05em", textTransform: "uppercase" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label className="flex items-center gap-2 text-xs mb-1 cursor-pointer" style={{ color: designTokens.colors.text.secondary }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="rounded"
        style={{ accentColor: designTokens.colors.accent.primary }}
      />
      {label}
    </label>
  );
}

export default DesignLab;
