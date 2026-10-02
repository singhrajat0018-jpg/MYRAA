export type MonitorId = string;

export function monitorId(id: string): MonitorId {
  return id;
}

export interface ScreenRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ObservedScene {
  timestamp: number;
  monitorId: string;
  elements: Array<{
    id: string;
    text?: string;
    box?: ScreenRegion;
    confidence?: number;
  }>;
  ocrBlocks?: Array<{ text: string; confidence: number; bbox: any }>;
  textContent?: string;
}
