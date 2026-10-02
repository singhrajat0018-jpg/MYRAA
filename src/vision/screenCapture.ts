// ============================================================================
// MYRAA Screen Capture Adapter — Connected to Real Desktop Agent Capture
// ============================================================================

import type { ScreenRegion, ActiveWindowInfo } from './contracts';

export interface ScreenCaptureAdapterOptions {
  agentUrl: string;
}

export interface CapturedFrame {
  buffer: Buffer;
  width: number;
  height: number;
  mimeType: string;
  timestamp: number;
  activeWindow: ActiveWindowInfo;
}

export class BridgeScreenCaptureAdapter {
  private agentUrl: string;

  constructor(options: ScreenCaptureAdapterOptions) {
    this.agentUrl = options.agentUrl || 'http://127.0.0.1:8765';
  }

  /**
   * Capture full desktop screen via Desktop Agent.
   * Calls real Windows capture tool `takeScreenshot`.
   */
  async captureScreen(mid?: string): Promise<CapturedFrame> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);

    try {
      const response = await fetch(`${this.agentUrl}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: 'takeScreenshot',
          args: { include_image: true, max_dim: 1920, monitor_id: mid || 'primary' },
        }),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(`Desktop Agent capture HTTP ${response.status}`);
      }

      const data = await response.json();
      if (!data.ok && data.error) {
        throw new Error(data.error);
      }

      const res = data.result || {};
      const width = typeof res.width === 'number' ? res.width : 1920;
      const height = typeof res.height === 'number' ? res.height : 1080;
      const mimeType = res.image_mime || 'image/jpeg';
      const b64 = res.image_base64 || '';

      const buffer = b64 ? Buffer.from(b64, 'base64') : Buffer.alloc(0);

      // Fetch active window metadata concurrently or best-effort
      const activeWindow = await this.getActiveWindowInfo();

      return {
        buffer,
        width,
        height,
        mimeType,
        timestamp: Date.now(),
        activeWindow,
      };
    } catch (err: any) {
      clearTimeout(timeout);
      // Fallback: check /vision/state directly
      try {
        const stateRes = await fetch(`${this.agentUrl}/vision/state`);
        if (stateRes.ok) {
          const vs = await stateRes.json();
          return {
            buffer: Buffer.alloc(0),
            width: 1920,
            height: 1080,
            mimeType: 'image/jpeg',
            timestamp: Date.now(),
            activeWindow: {
              application: vs.application || 'Windows Desktop',
              title: vs.window_title || 'Active Window',
              active: true,
            },
          };
        }
      } catch {
        // Agent offline
      }
      throw new Error(`Screen capture unavailable: ${err.message}`);
    }
  }

  /**
   * Capture a specific bounding region via Desktop Agent.
   */
  async captureRegion(region: ScreenRegion, mid?: string): Promise<CapturedFrame> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);

    try {
      const response = await fetch(`${this.agentUrl}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: 'takeRegionScreenshot',
          args: {
            x: Math.round(region.x),
            y: Math.round(region.y),
            width: Math.round(region.width),
            height: Math.round(region.height),
          },
        }),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(`Desktop Agent region capture HTTP ${response.status}`);
      }

      const data = await response.json();
      if (!data.ok && data.error) {
        throw new Error(data.error);
      }

      const res = data.result || {};
      const width = typeof res.width === 'number' ? res.width : region.width;
      const height = typeof res.height === 'number' ? res.height : region.height;
      const mimeType = res.image_mime || 'image/jpeg';
      const b64 = res.image_base64 || '';
      const buffer = b64 ? Buffer.from(b64, 'base64') : Buffer.alloc(0);

      const activeWindow = await this.getActiveWindowInfo();

      return {
        buffer,
        width,
        height,
        mimeType,
        timestamp: Date.now(),
        activeWindow,
      };
    } catch (err: any) {
      clearTimeout(timeout);
      throw new Error(`Region capture failed: ${err.message}`);
    }
  }

  /**
   * Retrieve active window identity directly from Desktop Agent.
   */
  async getActiveWindowInfo(): Promise<ActiveWindowInfo> {
    try {
      const response = await fetch(`${this.agentUrl}/vision/state`);
      if (response.ok) {
        const state = await response.json();
        return {
          application: state.application || 'Desktop',
          title: state.window_title || '',
          active: true,
        };
      }
    } catch {
      // Best-effort
    }
    return {
      application: 'Desktop',
      title: 'Active Desktop Window',
      active: true,
    };
  }
}
