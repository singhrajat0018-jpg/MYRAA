// ============================================================================
// MYRAA Vision Core — OCR Adapter
// ============================================================================

import type {
  ScreenCapture, OcrBlock, OcrLine, OcrWord, Bounds,
} from './contracts';

// ============================================================================
// OCR Adapter Interface
// ============================================================================

export interface IOcrAdapter {
  recognizeText(capture: ScreenCapture): Promise<readonly OcrBlock[]>;
  recognizeRegion(capture: ScreenCapture, region: Bounds): Promise<readonly OcrBlock[]>;
  isAvailable(): boolean;
}

// ============================================================================
// Mock OCR Adapter — Generates synthetic OCR results for development
// ============================================================================

export class MockOcrAdapter implements IOcrAdapter {
  async recognizeText(capture: ScreenCapture): Promise<readonly OcrBlock[]> {
    return this.generateSyntheticBlocks(capture.bounds);
  }

  async recognizeRegion(capture: ScreenCapture, region: Bounds): Promise<readonly OcrBlock[]> {
    return this.generateSyntheticBlocks(region);
  }

  isAvailable(): boolean {
    return true;
  }

  private generateSyntheticBlocks(bounds: Bounds): readonly OcrBlock[] {
    const blocks: OcrBlock[] = [];
    const blockCount = Math.max(1, Math.floor(bounds.height / 120));

    for (let i = 0; i < blockCount; i++) {
      const blockBounds: Bounds = {
        x: bounds.x + 20,
        y: bounds.y + (i * 120) + 10,
        width: Math.min(bounds.width - 40, 800),
        height: 100,
      };

      const lines: OcrLine[] = [];
      const lineCount = Math.max(1, Math.floor(blockBounds.height / 24));

      for (let j = 0; j < lineCount; j++) {
        const lineBounds: Bounds = {
          x: blockBounds.x,
          y: blockBounds.y + (j * 24),
          width: blockBounds.width * (0.5 + Math.random() * 0.5),
          height: 20,
        };

        const words = this.generateSyntheticWords(lineBounds);

        lines.push({
          text: words.map(w => w.text).join(' '),
          bounds: lineBounds,
          confidence: 0.7 + Math.random() * 0.3,
          words,
        });
      }

      blocks.push({
        blockId: `ocr-block-${i}`,
        text: lines.map(l => l.text).join('\n'),
        bounds: blockBounds,
        confidence: 0.6 + Math.random() * 0.4,
        lines,
        readingOrder: i,
      });
    }

    return blocks;
  }

  private generateSyntheticWords(lineBounds: Bounds): readonly OcrWord[] {
    const wordCount = Math.max(1, Math.floor(lineBounds.width / 60));
    const words: OcrWord[] = [];
    const sampleTexts = ['Button', 'Menu', 'File', 'Edit', 'View', 'Help', 'Save', 'Open', 'Close', 'Run'];
    let xOffset = lineBounds.x;

    for (let i = 0; i < wordCount; i++) {
      const text = sampleTexts[i % sampleTexts.length];
      const wordWidth = text.length * 8;

      words.push({
        text,
        bounds: { x: xOffset, y: lineBounds.y, width: wordWidth, height: lineBounds.height },
        confidence: 0.6 + Math.random() * 0.4,
      });

      xOffset += wordWidth + 6;
    }

    return words;
  }
}

// ============================================================================
// Bridge OCR Adapter — Real production OCR via Python desktop agent
// ============================================================================
// Phase 29.7: canonical production OCR path. Calls the Python agent's
// readScreen tool (Tesseract-backed) and converts the result into OcrBlocks
// with spatial data preserved. MockOcrAdapter remains for tests only.

export interface BridgeOcrConfig {
  readonly agentUrl: string;
  readonly timeoutMs: number;
}

const DEFAULT_BRIDGE_OCR_CONFIG: BridgeOcrConfig = {
  agentUrl: 'http://127.0.0.1:8765',
  timeoutMs: 15000,
};

interface PythonReadScreenResult {
  ok?: boolean;
  result?: {
    text?: string;
    lines?: Array<{
      text?: string;
      x?: number;
      y?: number;
      width?: number;
      height?: number;
      confidence?: number;
    }>;
  };
  error?: string;
}

export class BridgeOcrAdapter implements IOcrAdapter {
  private config: BridgeOcrConfig;

  constructor(config?: Partial<BridgeOcrConfig>) {
    this.config = { ...DEFAULT_BRIDGE_OCR_CONFIG, ...config };
  }

  async recognizeText(capture: ScreenCapture): Promise<readonly OcrBlock[]> {
    const result = await this.executeReadScreen();
    return this.toOcrBlocks(result, capture.bounds);
  }

  async recognizeRegion(capture: ScreenCapture, region: Bounds): Promise<readonly OcrBlock[]> {
    const result = await this.executeReadScreen();
    // Filter blocks to the requested region
    return this.toOcrBlocks(result, capture.bounds).filter(b =>
      b.bounds.x >= region.x &&
      b.bounds.y >= region.y &&
      b.bounds.x + b.bounds.width <= region.x + region.width &&
      b.bounds.y + b.bounds.height <= region.y + region.height
    );
  }

  isAvailable(): boolean {
    return true; // availability verified at call time via error handling
  }

  private async executeReadScreen(): Promise<PythonReadScreenResult> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.config.timeoutMs);
    try {
      const response = await fetch(`${this.config.agentUrl}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: 'readScreen', args: {} }),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`OCR bridge returned ${response.status}`);
      }
      return await response.json() as PythonReadScreenResult;
    } finally {
      clearTimeout(timeout);
    }
  }

  private toOcrBlocks(result: PythonReadScreenResult, fallbackBounds: Bounds): readonly OcrBlock[] {
    if (result.error || !result.result) return [];

    const lines = result.result.lines;
    if (Array.isArray(lines) && lines.length > 0) {
      // Structured lines with spatial data
      const blocks: OcrBlock[] = [];
      let blockIndex = 0;
      let currentLines: OcrLine[] = [];

      const flushBlock = () => {
        if (currentLines.length === 0) return;
        const minX = Math.min(...currentLines.map(l => l.bounds.x));
        const minY = Math.min(...currentLines.map(l => l.bounds.y));
        const maxX = Math.max(...currentLines.map(l => l.bounds.x + l.bounds.width));
        const maxY = Math.max(...currentLines.map(l => l.bounds.y + l.bounds.height));
        blocks.push({
          blockId: `ocr-bridge-${blockIndex++}`,
          text: currentLines.map(l => l.text).join('\n'),
          bounds: { x: minX, y: minY, width: maxX - minX, height: maxY - minY },
          confidence: currentLines.reduce((s, l) => s + l.confidence, 0) / currentLines.length,
          lines: currentLines,
          readingOrder: blocks.length,
        });
        currentLines = [];
      };

      for (const line of lines) {
        const text = (line.text || '').trim();
        if (!text) { flushBlock(); continue; }
        currentLines.push({
          text,
          bounds: {
            x: line.x ?? fallbackBounds.x,
            y: line.y ?? fallbackBounds.y,
            width: line.width ?? 200,
            height: line.height ?? 20,
          },
          confidence: line.confidence ?? 0.8,
          words: text.split(/\s+/).map((w, i) => ({
            text: w,
            bounds: {
              x: (line.x ?? fallbackBounds.x) + i * 10,
              y: line.y ?? fallbackBounds.y,
              width: w.length * 8,
              height: line.height ?? 20,
            },
            confidence: line.confidence ?? 0.8,
          })),
        });
        // Group ~8 lines per block
        if (currentLines.length >= 8) flushBlock();
      }
      flushBlock();
      return blocks;
    }

    // Fallback: plain text only — single block, no spatial data
    const text = (result.result.text || '').trim();
    if (!text) return [];
    return [{
      blockId: 'ocr-bridge-0',
      text,
      bounds: fallbackBounds,
      confidence: 0.7,
      lines: text.split('\n').map((lineText, i) => ({
        text: lineText,
        bounds: { ...fallbackBounds, y: fallbackBounds.y + i * 24, height: 20 },
        confidence: 0.7,
        words: lineText.split(/\s+/).filter(Boolean).map(w => ({
          text: w,
          bounds: { ...fallbackBounds, height: 20 },
          confidence: 0.7,
        })),
      })),
      readingOrder: 0,
    }];
  }
}

// ============================================================================
// OCR Result Merger — Combines results from multiple passes
// ============================================================================

export class OcrResultMerger {
  merge(blocks: ReadonlyArray<readonly OcrBlock[]>): readonly OcrBlock[] {
    const allBlocks = blocks.flat();
    if (allBlocks.length === 0) return [];

    const deduped = this.deduplicateBlocks(allBlocks);
    return this.assignReadingOrder(deduped);
  }

  private deduplicateBlocks(blocks: readonly OcrBlock[]): OcrBlock[] {
    const result: OcrBlock[] = [];
    const used = new Set<number>();

    for (let i = 0; i < blocks.length; i++) {
      if (used.has(i)) continue;

      const block = blocks[i];
      let bestBlock = block;
      let bestConfidence = block.confidence;

      for (let j = i + 1; j < blocks.length; j++) {
        if (used.has(j)) continue;

        const other = blocks[j];
        if (this.blocksOverlap(block, other)) {
          if (other.confidence > bestConfidence) {
            bestBlock = other;
            bestConfidence = other.confidence;
          }
          used.add(j);
        }
      }

      result.push(bestBlock);
      used.add(i);
    }

    return result;
  }

  private blocksOverlap(a: OcrBlock, b: OcrBlock): boolean {
    return (
      a.bounds.x < b.bounds.x + b.bounds.width &&
      a.bounds.x + a.bounds.width > b.bounds.x &&
      a.bounds.y < b.bounds.y + b.bounds.height &&
      a.bounds.y + a.bounds.height > b.bounds.y
    );
  }

  private assignReadingOrder(blocks: OcrBlock[]): OcrBlock[] {
    return blocks
      .slice()
      .sort((a, b) => {
        const yDiff = a.bounds.y - b.bounds.y;
        if (Math.abs(yDiff) > 10) return yDiff;
        return a.bounds.x - b.bounds.x;
      })
      .map((block, index) => ({
        ...block,
        readingOrder: index,
      }));
  }
}

// ============================================================================
// OCR Text Extractor — Flattens OCR blocks to plain text
// ============================================================================

export class OcrTextExtractor {
  extractText(blocks: readonly OcrBlock[]): string {
    const sorted = blocks
      .slice()
      .sort((a, b) => a.readingOrder - b.readingOrder);

    return sorted.map(b => b.text).join('\n');
  }

  extractTextFromRegion(blocks: readonly OcrBlock[], region: Bounds): string {
    const inRegion = blocks.filter(b => this.blockInRegion(b, region));
    return this.extractText(inRegion);
  }

  searchBlocks(
    blocks: readonly OcrBlock[],
    query: string,
    options?: { fuzzy?: boolean; minConfidence?: number },
  ): readonly OcrBlock[] {
    const minConf = options?.minConfidence ?? 0;
    const fuzzy = options?.fuzzy ?? true;
    const q = query.toLowerCase();

    return blocks.filter(b => {
      if (b.confidence < minConf) return false;
      const text = b.text.toLowerCase();
      if (fuzzy) {
        return text.includes(q) || q.includes(text);
      }
      return text === q;
    });
  }

  private blockInRegion(block: OcrBlock, region: Bounds): boolean {
    return (
      block.bounds.x >= region.x &&
      block.bounds.y >= region.y &&
      block.bounds.x + block.bounds.width <= region.x + region.width &&
      block.bounds.y + block.bounds.height <= region.y + region.height
    );
  }
}
