// ============================================================================
// MYRAA Visual Targeting — OCR + Template + Vision-based target acquisition
// ============================================================================

import type {
  UITarget, UITargetType, TargetSource, BoundingBox, Vec2,
} from './contracts';
import { toBoundingRect, iou } from './contracts';

// ============================================================================
// Visual Target Result
// ============================================================================

export interface VisualTargetResult {
  readonly targets: readonly UITarget[];
  readonly method: TargetSource;
  readonly confidence: number;
  readonly processingTimeMs: number;
}

// ============================================================================
// Visual Targeter
// ============================================================================

export class VisualTargeter {
  private targetCache: Map<string, UITarget> = new Map();
  private lastScanHash = '';
  private scanIntervalMs = 2000;
  private lastScanAt = 0;

  // --- Target Search ---

  async findTarget(
    description: string,
    allTargets: readonly UITarget[],
    options?: {
      preferredType?: UITargetType;
      minConfidence?: number;
      maxResults?: number;
    },
  ): Promise<VisualTargetResult> {
    const start = Date.now();
    const minConf = options?.minConfidence ?? 0.4;
    const maxResults = options?.maxResults ?? 5;

    // Score each target by label similarity
    const scored = allTargets
      .filter(t => t.confidence >= minConf)
      .map(t => ({
        target: t,
        score: this.scoreTargetMatch(t, description),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, maxResults);

    const method: TargetSource = scored.length > 0 ? scored[0].target.source : 'VISION';
    const topConf = scored.length > 0 ? scored[0].score : 0;

    return {
      targets: scored.map(s => s.target),
      method,
      confidence: topConf,
      processingTimeMs: Date.now() - start,
    };
  }

  // --- OCR-based Targeting ---

  async findTargetByOCR(
    text: string,
    ocrTargets: readonly UITarget[],
    options?: { fuzzy?: boolean; minConfidence?: number },
  ): Promise<VisualTargetResult> {
    const start = Date.now();
    const minConf = options?.minConfidence ?? 0.3;
    const fuzzy = options?.fuzzy ?? true;

    const matches = ocrTargets
      .filter(t => t.confidence >= minConf)
      .filter(t => {
        if (!t.text) return false;
        if (fuzzy) {
          return t.text.toLowerCase().includes(text.toLowerCase()) ||
                 text.toLowerCase().includes(t.text.toLowerCase());
        }
        return t.text.toLowerCase() === text.toLowerCase();
      })
      .sort((a, b) => b.confidence - a.confidence);

    return {
      targets: matches,
      method: 'OCR',
      confidence: matches.length > 0 ? matches[0].confidence : 0,
      processingTimeMs: Date.now() - start,
    };
  }

  // --- Template Matching ---

  async findTargetByTemplate(
    templateBounds: BoundingBox,
    screenTargets: readonly UITarget[],
    options?: { iouThreshold?: number },
  ): Promise<VisualTargetResult> {
    const start = Date.now();
    const thresh = options?.iouThreshold ?? 0.3;

    const matches = screenTargets
      .filter(t => iou(t.bounds, templateBounds) >= thresh)
      .sort((a, b) => b.confidence - a.confidence);

    return {
      targets: matches,
      method: 'VISION',
      confidence: matches.length > 0 ? matches[0].confidence : 0,
      processingTimeMs: Date.now() - start,
    };
  }

  // --- Spatial Search ---

  findTargetsInRegion(
    region: BoundingBox,
    targets: readonly UITarget[],
    options?: { includePartial?: boolean },
  ): readonly UITarget[] {
    const includePartial = options?.includePartial ?? false;

    return targets.filter(t => {
      const overlap = iou(t.bounds, region);
      if (includePartial) return overlap > 0;
      return overlap > 0.5 || this.isInsideRegion(t.bounds, region);
    });
  }

  findTargetsNear(
    point: Vec2,
    targets: readonly UITarget[],
    maxDistance = 100,
  ): readonly UITarget[] {
    return targets
      .map(t => ({ target: t, dist: this.pointToTargetDistance(point, t.bounds) }))
      .filter(({ dist }) => dist <= maxDistance)
      .sort((a, b) => a.dist - b.dist)
      .map(({ target }) => target);
  }

  // --- Scoring ---

  private scoreTargetMatch(target: UITarget, description: string): number {
    const desc = description.toLowerCase();
    let score = 0;

    // Exact label match
    if (target.label.toLowerCase() === desc) score += 1.0;
    // Partial label match
    else if (target.label.toLowerCase().includes(desc)) score += 0.7;
    else if (desc.includes(target.label.toLowerCase())) score += 0.5;

    // Type match
    if (this.typeMatchesDescription(target.type, desc)) score += 0.2;

    // Confidence contribution
    score *= target.confidence;

    return Math.min(1.0, score);
  }

  private typeMatchesDescription(type: UITargetType, desc: string): boolean {
    const typeKeywords: Record<string, string[]> = {
      BUTTON: ['button', 'btn', 'click'],
      INPUT: ['input', 'text field', 'textbox', 'search'],
      TAB: ['tab', 'tab bar'],
      MENU: ['menu', 'dropdown'],
      LINK: ['link', 'href'],
      CHECKBOX: ['checkbox', 'check'],
      RADIO: ['radio', 'option'],
      SLIDER: ['slider', 'range'],
    };
    const keywords = typeKeywords[type] ?? [];
    return keywords.some(k => desc.includes(k));
  }

  private isInsideRegion(bounds: BoundingBox, region: BoundingBox): boolean {
    const r = toBoundingRect(bounds);
    return bounds.x >= region.x && r.right <= region.x + region.width &&
           bounds.y >= region.y && r.bottom <= region.y + region.height;
  }

  private pointToTargetDistance(point: Vec2, bounds: BoundingBox): number {
    const r = toBoundingRect(bounds);
    const cx = r.centerX, cy = r.centerY;
    return Math.hypot(point.x - cx, point.y - cy);
  }

  // --- Cache ---

  updateTargets(targets: readonly UITarget[], stateHash: string): void {
    this.targetCache.clear();
    for (const t of targets) this.targetCache.set(t.id, t);
    this.lastScanHash = stateHash;
    this.lastScanAt = Date.now();
  }

  getCachedTargets(): readonly UITarget[] {
    return [...this.targetCache.values()];
  }

  isCacheStale(): boolean {
    return Date.now() - this.lastScanAt > this.scanIntervalMs;
  }

  clearCache(): void {
    this.targetCache.clear();
    this.lastScanHash = '';
  }
}
