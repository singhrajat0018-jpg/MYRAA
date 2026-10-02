// ============================================================================
// MYRAA Target Resolution — Multi-strategy target resolution with confidence
// ============================================================================

import type { UITarget, UITargetType, BoundingBox, TargetSource } from './contracts';
import { toBoundingRect } from './contracts';

// ============================================================================
// Resolution Strategy
// ============================================================================

export type ResolutionStrategy =
  | 'EXACT_TEXT'
  | 'FUZZY_TEXT'
  | 'TYPE_MATCH'
  | 'ORDINAL'
  | 'SPATIAL'
  | 'CONTEXTUAL'
  | 'HYBRID';

export interface ResolutionResult {
  readonly target: UITarget | null;
  readonly confidence: number;
  readonly strategy: ResolutionStrategy;
  readonly alternatives: readonly UITarget[];
  readonly reasoning: string;
}

// ============================================================================
// Target Resolver
// ============================================================================

export class TargetResolver {
  private ordinalPatterns: Map<string, number> = new Map([
    ['first', 0], ['second', 1], ['third', 2], ['fourth', 3], ['fifth', 4],
    ['1st', 0], ['2nd', 1], ['3rd', 2], ['4th', 3], ['5th', 4],
    ['pehla', 0], ['doosra', 1], ['teesra', 2],
    ['last', -1],
  ]);

  // --- Resolve ---

  resolve(query: string, targets: readonly UITarget[]): ResolutionResult {
    // Check for ordinal keywords first — ordinal is unambiguous when present
    const hasOrdinal = [...this.ordinalPatterns.keys()].some(k => query.toLowerCase().includes(k));
    
    const results: ResolutionResult[] = hasOrdinal
      ? [
          this.resolveOrdinal(query, targets),
          this.resolveExactText(query, targets),
          this.resolveFuzzyText(query, targets),
          this.resolveTypeMatch(query, targets),
        ]
      : [
          this.resolveExactText(query, targets),
          this.resolveFuzzyText(query, targets),
          this.resolveTypeMatch(query, targets),
          this.resolveOrdinal(query, targets),
        ];

    // Return best result
    const valid = results.filter(r => r.target !== null);
    if (valid.length === 0) {
      return {
        target: null,
        confidence: 0,
        strategy: 'HYBRID',
        alternatives: [],
        reasoning: `No target found matching "${query}"`,
      };
    }

    return valid.sort((a, b) => b.confidence - a.confidence)[0];
  }

  // --- Strategy: Exact Text ---

  private resolveExactText(query: string, targets: readonly UITarget[]): ResolutionResult {
    const q = query.toLowerCase().trim();
    const matches = targets.filter(t =>
      t.label.toLowerCase().trim() === q || t.text?.toLowerCase().trim() === q,
    );

    if (matches.length === 1) {
      return {
        target: matches[0],
        confidence: 0.95,
        strategy: 'EXACT_TEXT',
        alternatives: [],
        reasoning: `Exact match for "${query}"`,
      };
    }

    if (matches.length > 1) {
      return {
        target: matches[0],
        confidence: 0.8,
        strategy: 'EXACT_TEXT',
        alternatives: matches.slice(1),
        reasoning: `${matches.length} exact matches for "${query}", using first`,
      };
    }

    return { target: null, confidence: 0, strategy: 'EXACT_TEXT', alternatives: [], reasoning: 'No exact match' };
  }

  // --- Strategy: Fuzzy Text ---

  private resolveFuzzyText(query: string, targets: readonly UITarget[]): ResolutionResult {
    const q = query.toLowerCase().trim();
    const scored = targets
      .map(t => {
        const label = t.label.toLowerCase();
        const text = (t.text ?? '').toLowerCase();
        let score = 0;

        if (label.includes(q) || q.includes(label)) score += 0.6;
        if (text.includes(q) || q.includes(text)) score += 0.4;
        score *= t.confidence;

        return { target: t, score };
      })
      .filter(s => s.score > 0.3)
      .sort((a, b) => b.score - a.score);

    if (scored.length > 0) {
      return {
        target: scored[0].target,
        confidence: scored[0].score,
        strategy: 'FUZZY_TEXT',
        alternatives: scored.slice(1, 4).map(s => s.target),
        reasoning: `Fuzzy match for "${query}" (score: ${scored[0].score.toFixed(2)})`,
      };
    }

    return { target: null, confidence: 0, strategy: 'FUZZY_TEXT', alternatives: [], reasoning: 'No fuzzy match' };
  }

  // --- Strategy: Type Match ---

  private resolveTypeMatch(query: string, targets: readonly UITarget[]): ResolutionResult {
    const typeKeywords: Record<string, UITargetType[]> = {
      button: ['BUTTON'],
      input: ['INPUT', 'TEXTAREA'],
      text: ['INPUT', 'TEXTAREA'],
      tab: ['TAB'],
      menu: ['MENU', 'MENU_ITEM'],
      link: ['LINK'],
      checkbox: ['CHECKBOX'],
      slider: ['SLIDER'],
    };

    const q = query.toLowerCase();
    let targetType: UITargetType | undefined;
    for (const [kw, types] of Object.entries(typeKeywords)) {
      if (q.includes(kw)) { targetType = types[0]; break; }
    }

    if (!targetType) return { target: null, confidence: 0, strategy: 'TYPE_MATCH', alternatives: [], reasoning: 'No type keyword found' };

    const matches = targets.filter(t => t.type === targetType);
    if (matches.length > 0) {
      return {
        target: matches[0],
        confidence: 0.5,
        strategy: 'TYPE_MATCH',
        alternatives: matches.slice(1),
        reasoning: `Type match: ${matches.length} ${targetType} targets`,
      };
    }

    return { target: null, confidence: 0, strategy: 'TYPE_MATCH', alternatives: [], reasoning: `No ${targetType} targets` };
  }

  // --- Strategy: Ordinal ---

  private resolveOrdinal(query: string, targets: readonly UITarget[]): ResolutionResult {
    const q = query.toLowerCase();
    let ordinal: number | null = null;

    for (const [pattern, index] of this.ordinalPatterns) {
      if (q.includes(pattern)) { ordinal = index; break; }
    }

    if (ordinal === null) return { target: null, confidence: 0, strategy: 'ORDINAL', alternatives: [], reasoning: 'No ordinal found' };

    const interactables = targets.filter(t => t.clickable);
    if (interactables.length === 0) {
      return { target: null, confidence: 0, strategy: 'ORDINAL', alternatives: [], reasoning: 'No interactable targets' };
    }

    const idx = ordinal === -1 ? interactables.length - 1 : ordinal!;
    if (idx >= interactables.length) {
      return { target: null, confidence: 0, strategy: 'ORDINAL', alternatives: [], reasoning: `Ordinal ${idx} out of range (${interactables.length} targets)` };
    }

    return {
      target: interactables[idx],
      confidence: 0.7,
      strategy: 'ORDINAL',
      alternatives: [],
      reasoning: `Ordinal #${idx + 1} of ${interactables.length} interactables`,
    };
  }

  // --- Helpers ---

  getAvailableStrategies(): readonly ResolutionStrategy[] {
    return ['EXACT_TEXT', 'FUZZY_TEXT', 'TYPE_MATCH', 'ORDINAL', 'SPATIAL', 'CONTEXTUAL', 'HYBRID'];
  }
}
