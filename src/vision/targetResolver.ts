// ============================================================================
// MYRAA Vision Core — Visual Target Resolver
// ============================================================================

import type {
  VisualTarget, TargetResolutionRequest, TargetResolutionResult,
  VisualScene, VisualElement, VisionContext, MonitorId, ElementId,
  Bounds, Point, ResolutionMethod, AmbiguityLevel,
} from './contracts';
import { observationId, CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW } from './contracts';

// ============================================================================
// Target Resolver
// ============================================================================

export class TargetResolver {
  private ordinalPatterns: Map<string, number> = new Map([
    ['first', 0], ['second', 1], ['third', 2], ['fourth', 3], ['fifth', 4],
    ['sixth', 5], ['seventh', 6], ['eighth', 7], ['ninth', 8], ['tenth', 9],
    ['1st', 0], ['2nd', 1], ['3rd', 2], ['4th', 3], ['5th', 4],
    ['6th', 5], ['7th', 6], ['8th', 7], ['9th', 8], ['10th', 9],
    ['last', -1],
  ]);

  private spatialPatterns: Map<string, (bounds: Bounds, screenBounds: Bounds) => number> = new Map([
    ['top left', (b, s) => -(b.x + b.y)],
    ['top right', (b, s) => -(s.width - b.x - b.width + b.y)],
    ['bottom left', (b, s) => -(b.x + s.height - b.y - b.height)],
    ['bottom right', (b, s) => -(s.width - b.x - b.width + s.height - b.y - b.height)],
    ['left side', (b, s) => b.x],
    ['right side', (b, s) => s.width - b.x - b.width],
    ['top', (b, s) => b.y],
    ['bottom', (b, s) => s.height - b.y - b.height],
    ['center', (b, s) => {
      const cx = s.width / 2, cy = s.height / 2;
      return -Math.hypot(b.x + b.width / 2 - cx, b.y + b.height / 2 - cy);
    }],
  ]);

  // --- Resolve ---

  resolve(request: TargetResolutionRequest): TargetResolutionResult {
    const { query, context } = request;
    const candidates: VisualTarget[] = [];

    const textTargets = this.resolveByText(query, context);
    candidates.push(...textTargets);

    const ordinalTargets = this.resolveByOrdinal(query, context);
    candidates.push(...ordinalTargets);

    const spatialTargets = this.resolveBySpatial(query, context);
    candidates.push(...spatialTargets);

    const typeTargets = this.resolveByType(query, context);
    candidates.push(...typeTargets);

    const deduped = this.deduplicateTargets(candidates);
    const filtered = deduped.filter(t => t.confidence >= request.minConfidence);
    const sorted = filtered.sort((a, b) => b.confidence - a.confidence);
    const topCandidates = sorted.slice(0, request.maxCandidates);

    const primary = topCandidates.length > 0 ? topCandidates[0] : null;
    const confidence = primary?.confidence ?? 0;
    const ambiguity = this.computeAmbiguity(topCandidates);
    const suggestion = this.generateSuggestion(query, topCandidates, ambiguity);

    return {
      primary,
      candidates: topCandidates,
      confidence,
      ambiguity,
      suggestion,
    };
  }

  // --- Text Resolution ---

  private resolveByText(query: string, context: VisionContext): readonly VisualTarget[] {
    const results: VisualTarget[] = [];
    const q = query.toLowerCase();

    for (const el of context.keyElements) {
      const score = this.scoreTextMatch(el, q);
      if (score > 0) {
        results.push(this.elementToTarget(el, score, 'ocr', context.sceneId, context.monitorId, context.dpiScale));
      }
    }

    for (const el of context.importantControls) {
      const score = this.scoreTextMatch(el, q);
      if (score > 0 && !results.some(r => r.element?.elementId === el.elementId)) {
        results.push(this.elementToTarget(el, score, 'accessibility', context.sceneId, context.monitorId, context.dpiScale));
      }
    }

    return results;
  }

  private scoreTextMatch(element: VisualElement, query: string): number {
    const label = (element.accessibilityLabel ?? element.text).toLowerCase();
    const text = element.text.toLowerCase();

    if (label === query || text === query) return 0.95;
    if (label.includes(query) || text.includes(query)) return 0.8;
    if (query.includes(label) || query.includes(text)) return 0.6;

    const words = query.split(/\s+/);
    const matchCount = words.filter(w =>
      label.includes(w) || text.includes(w)
    ).length;
    if (matchCount > 0) {
      return 0.4 * (matchCount / words.length);
    }

    return 0;
  }

  // --- Ordinal Resolution ---

  private resolveByOrdinal(query: string, context: VisionContext): readonly VisualTarget[] {
    const q = query.toLowerCase();
    let ordinal: number | null = null;

    for (const [pattern, index] of this.ordinalPatterns) {
      if (q.includes(pattern)) {
        ordinal = index;
        break;
      }
    }

    if (ordinal === null) return [];

    const interactables = context.importantControls.filter(e => e.isClickable);
    if (interactables.length === 0) return [];

    const idx = ordinal === -1 ? interactables.length - 1 : ordinal;
    if (idx < 0 || idx >= interactables.length) return [];

    return [this.elementToTarget(interactables[idx], 0.7, 'ordinal', context.sceneId, context.monitorId, context.dpiScale)];
  }

  // --- Spatial Resolution ---

  private resolveBySpatial(query: string, context: VisionContext): readonly VisualTarget[] {
    const q = query.toLowerCase();
    const screenBounds = context.keyElements[0]
      ? { x: 0, y: 0, width: 1920, height: 1080 }
      : { x: 0, y: 0, width: 1920, height: 1080 };

    const results: VisualTarget[] = [];

    for (const [pattern, scoreFn] of this.spatialPatterns) {
      if (!q.includes(pattern)) continue;

      const allElements = [...context.keyElements, ...context.importantControls];
      const scored = allElements
        .map(el => ({
          element: el,
          score: scoreFn(el.bounds, screenBounds),
        }))
        .sort((a, b) => b.score - a.score);

      if (scored.length > 0) {
        const best = scored[0];
        results.push(this.elementToTarget(best.element, 0.55, 'spatial', context.sceneId, context.monitorId, context.dpiScale));
      }
    }

    return results;
  }

  // --- Type Resolution ---

  private resolveByType(query: string, context: VisionContext): readonly VisualTarget[] {
    const typeKeywords: Record<string, VisualElement['type'][]> = {
      button: ['BUTTON'],
      text: ['TEXT_FIELD', 'TEXT_BLOCK'],
      input: ['TEXT_FIELD', 'COMBOBOX'],
      tab: ['TAB'],
      menu: ['MENU'],
      link: ['LINK'],
      checkbox: ['CHECKBOX'],
      slider: ['SLIDER'],
      toggle: ['TOGGLE'],
      dropdown: ['DROPDOWN', 'COMBOBOX'],
      dialog: ['DIALOG'],
      table: ['TABLE'],
      image: ['IMAGE'],
      icon: ['ICON'],
    };

    const q = query.toLowerCase();
    let targetType: VisualElement['type'] | undefined;

    for (const [keyword, types] of Object.entries(typeKeywords)) {
      if (q.includes(keyword)) {
        targetType = types[0];
        break;
      }
    }

    if (!targetType) return [];

    const allElements = [...context.keyElements, ...context.importantControls];
    const matches = allElements.filter(e => e.type === targetType);

    if (matches.length === 0) return [];

    return matches.map(el =>
      this.elementToTarget(el, 0.5, 'visual', context.sceneId, context.monitorId, context.dpiScale)
    );
  }

  // --- Helpers ---

  private elementToTarget(
    element: VisualElement,
    confidence: number,
    method: ResolutionMethod,
    sceneId: import('./contracts').ObservationId,
    monitorId: MonitorId,
    dpiScale: number,
  ): VisualTarget {
    return {
      targetId: `target-${element.elementId}`,
      description: element.text || element.accessibilityLabel || element.type,
      element,
      bounds: element.bounds,
      center: {
        x: element.bounds.x + element.bounds.width / 2,
        y: element.bounds.y + element.bounds.height / 2,
      },
      monitorId,
      coordinateSpace: 'screen',
      confidence,
      resolutionMethod: method,
      observationId: sceneId,
    };
  }

  private deduplicateTargets(targets: readonly VisualTarget[]): readonly VisualTarget[] {
    const seen = new Map<ElementId, VisualTarget>();

    for (const target of targets) {
      if (!target.element) {
        if (!seen.has(target.targetId as ElementId)) {
          seen.set(target.targetId as ElementId, target);
        }
        continue;
      }

      const existing = seen.get(target.element.elementId);
      if (!existing || target.confidence > existing.confidence) {
        seen.set(target.element.elementId, target);
      }
    }

    return [...seen.values()];
  }

  private computeAmbiguity(candidates: readonly VisualTarget[]): AmbiguityLevel {
    if (candidates.length <= 1) return 'none';
    if (candidates.length === 2) {
      const gap = candidates[0].confidence - candidates[1].confidence;
      if (gap > 0.3) return 'low';
      return 'medium';
    }
    if (candidates.length > 3) {
      const topConf = candidates[0].confidence;
      const secondConf = candidates[1].confidence;
      if (topConf - secondConf > 0.4) return 'low';
      if (topConf - secondConf > 0.2) return 'medium';
      return 'high';
    }
    return 'low';
  }

  private generateSuggestion(
    query: string,
    candidates: readonly VisualTarget[],
    ambiguity: AmbiguityLevel,
  ): string | null {
    if (candidates.length === 0) {
      return `No element matching "${query}" found on screen. Try a different description.`;
    }

    if (ambiguity === 'high') {
      const types = [...new Set(candidates.map(c => c.element?.type ?? 'unknown'))];
      return `Multiple elements match "${query}". Found ${types.join(', ')}. Try being more specific.`;
    }

    if (ambiguity === 'medium') {
      return `Several matches found. Using the most likely: "${candidates[0].description}".`;
    }

    return null;
  }
}
