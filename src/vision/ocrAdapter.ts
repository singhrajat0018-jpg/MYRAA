export interface OcrAdapterOptions {
  agentUrl: string;
}

export class BridgeOcrAdapter {
  constructor(private options: OcrAdapterOptions) {}

  async recognize(buffer: Buffer): Promise<Array<{ text: string; confidence: number; bbox: any }>> {
    return [];
  }
}
