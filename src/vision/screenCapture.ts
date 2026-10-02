export interface ScreenCaptureAdapterOptions {
  agentUrl: string;
}

export class BridgeScreenCaptureAdapter {
  constructor(private options: ScreenCaptureAdapterOptions) {}

  async captureScreen(mid?: string): Promise<{ buffer: Buffer; width: number; height: number }> {
    return { buffer: Buffer.alloc(0), width: 1920, height: 1080 };
  }
}
