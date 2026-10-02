import type { WireframeDefinition } from "../contracts/index";

function makeWireframe(screenId: string, title: string): WireframeDefinition {
  return {
    id: `wf-${screenId.toLowerCase()}`,
    version: "1.0.0",
    screenId,
    viewport: "desktop",
    regions: [],
    constraints: [],
    responsiveRules: [],
    metadata: {
      title,
      description: `${title} wireframe`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    },
  };
}

export const HOME_WIREFRAME = makeWireframe("HOME", "Home");
export const CHAT_WIREFRAME = makeWireframe("CHAT", "Chat");
export const VISION_WIREFRAME = makeWireframe("VISION", "Vision");
export const DESKTOP_WIREFRAME = makeWireframe("DESKTOP", "Desktop");
export const BROWSER_WIREFRAME = makeWireframe("BROWSER", "Browser");
export const MEMORY_WIREFRAME = makeWireframe("MEMORY", "Memory");
export const TRADING_WIREFRAME = makeWireframe("TRADING", "Trading");
export const RESEARCH_WIREFRAME = makeWireframe("RESEARCH", "Research");
export const SETTINGS_WIREFRAME = makeWireframe("SETTINGS", "Settings");
export const DESIGN_LAB_WIREFRAME = makeWireframe("DESIGN_LAB", "Design Lab");

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

export function getWireframe(id: string): WireframeDefinition | undefined {
  return ALL_WIREFRAMES.find((w) => w.id === id);
}

export function getWireframeByScreen(screenId: string): WireframeDefinition | undefined {
  return ALL_WIREFRAMES.find((w) => w.screenId === screenId);
}
