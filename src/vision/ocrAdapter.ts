// ============================================================================
// MYRAA OCR Adapter — Connected to Real Desktop Agent Tesseract/OCR Tools
// ============================================================================

import type { OcrBlock, ScreenRegion } from './contracts';

export interface OcrAdapterOptions {
  agentUrl: string;
}

export interface OcrResult {
  text: string;
  blocks: OcrBlock[];
  confidence: number;
  hasErrors: boolean;
  sensitiveRedacted: boolean;
}

export class BridgeOcrAdapter {
  private agentUrl: string;

  constructor(options: OcrAdapterOptions) {
    this.agentUrl = options.agentUrl || 'http://127.0.0.1:8765';
  }

  /**
   * Run OCR on screen or image buffer using Desktop Agent's OCR engine.
   * Calls real tool `readScreen` or `analyzeScreenshot`.
   */
  async recognize(buffer?: Buffer, region?: ScreenRegion): Promise<OcrBlock[]> {
    const res = await this.recognizeWithMetadata(buffer, region);
    return res.blocks;
  }

  async recognizeWithMetadata(buffer?: Buffer, region?: ScreenRegion): Promise<OcrResult> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    try {
      const tool = region ? 'readScreen' : 'analyzeScreenshot';
      const args: Record<string, unknown> = { max_chars: 3000 };
      if (region) {
        args.region = region;
      }

      const response = await fetch(`${this.agentUrl}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool, args }),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(`Desktop Agent OCR HTTP ${response.status}`);
      }

      const data = await response.json();
      if (!data.ok && data.error) {
        throw new Error(data.error);
      }

      const rawText: string = data.result?.text || '';
      return this.parseOcrText(rawText);
    } catch (err: any) {
      clearTimeout(timeout);
      // If Desktop Agent is unreachable or OCR is uninstalled on host, return empty with error notice
      return {
        text: '',
        blocks: [],
        confidence: 0,
        hasErrors: true,
        sensitiveRedacted: false,
      };
    }
  }

  /**
   * Parse raw OCR text into structured line-by-line OcrBlock instances,
   * detect errors (e.g. "Build failed", "SyntaxError", "Traceback"),
   * and sanitize sensitive patterns (passwords, JWT tokens, Bearer keys).
   */
  public parseOcrText(rawText: string): OcrResult {
    if (!rawText || !rawText.trim()) {
      return {
        text: '',
        blocks: [],
        confidence: 0,
        hasErrors: false,
        sensitiveRedacted: false,
      };
    }

    let sensitiveRedacted = false;
    let sanitizedText = rawText;

    // Privacy & Security: redact potential API keys or tokens in OCR
    const tokenRegex = /(Bearer\s+[A-Za-z0-9\-_]{20,})|(ghp_[A-Za-z0-9]{30,})|(AIza[0-9A-Za-z-_]{35})/g;
    if (tokenRegex.test(sanitizedText)) {
      sanitizedText = sanitizedText.replace(tokenRegex, '[REDACTED_SECRET]');
      sensitiveRedacted = true;
    }

    const lines = sanitizedText.split('\n').map(l => l.trim()).filter(Boolean);
    const blocks: OcrBlock[] = [];

    const errorRegex = /(error|failed|exception|traceback|syntaxerror|typeerror|panic|fatal)/i;
    let hasErrors = false;

    lines.forEach((line, index) => {
      if (errorRegex.test(line)) {
        hasErrors = true;
      }
      blocks.push({
        text: line,
        confidence: 0.92,
        bbox: {
          x: 0,
          y: index * 24,
          width: Math.min(line.length * 8, 1920),
          height: 20,
        },
        line: index + 1,
        block: 1,
        language: 'en',
      });
    });

    return {
      text: sanitizedText,
      blocks,
      confidence: blocks.length > 0 ? 0.92 : 0,
      hasErrors,
      sensitiveRedacted,
    };
  }
}
