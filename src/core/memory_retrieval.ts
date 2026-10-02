// ============================================================================
// MYRAA Hybrid Memory Retrieval — Keyword + Recency + Importance
// ============================================================================

import type { Memory } from '../lib/memoryTypes';

export interface MemoryScored extends Memory {
  readonly relevanceScore: number;
  readonly recencyScore: number;
  readonly importanceScore: number;
  readonly totalScore: number;
}

export interface RetrievalOptions {
  readonly maxResults?: number;
  readonly minScore?: number;
  readonly categories?: readonly string[];
  readonly boostRecent?: number;
  readonly boostImportant?: number;
}

const DEFAULT_OPTIONS: Required<RetrievalOptions> = {
  maxResults: 10,
  minScore: 0.05,
  categories: [],
  boostRecent: 0.3,
  boostImportant: 0.2,
};

function computeRecencyScore(createdAt: string, updatedAt: string): number {
  const now = Date.now();
  const mostRecent = Math.max(new Date(createdAt).getTime(), new Date(updatedAt).getTime());
  const ageMs = now - mostRecent;
  const ONE_DAY = 86400000;
  const ONE_WEEK = ONE_DAY * 7;
  const ONE_MONTH = ONE_DAY * 30;

  if (ageMs < ONE_DAY) return 1.0;
  if (ageMs < ONE_WEEK) return 0.8;
  if (ageMs < ONE_MONTH) return 0.5;
  return 0.2;
}

function computeKeywordScore(query: string, text: string): number {
  const queryWords = query.toLowerCase().split(/\s+/).filter(w => w.length > 2);
  const textWords = new Set(text.toLowerCase().split(/\s+/));

  if (queryWords.length === 0) return 0;

  let matches = 0;
  for (const w of queryWords) {
    if (textWords.has(w)) matches++;
    // Partial match
    for (const tw of textWords) {
      if (tw.includes(w) || w.includes(tw)) {
        matches += 0.5;
        break;
      }
    }
  }

  return matches / queryWords.length;
}

function computeImportanceScore(memory: Memory): number {
  // Identity and goal memories are more important
  const importanceMap: Record<string, number> = {
    identity: 0.9,
    goal: 0.8,
    preference: 0.7,
    project: 0.7,
    relationship: 0.6,
    emotional: 0.5,
    behavior: 0.4,
  };
  return importanceMap[memory.category] || 0.5;
}

export function hybridRetrieve(
  memories: readonly Memory[],
  query: string,
  options?: RetrievalOptions,
): readonly MemoryScored[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  let candidates = [...memories];

  // Filter by categories if specified
  if (opts.categories.length > 0) {
    candidates = candidates.filter(m => opts.categories.includes(m.category));
  }

  // Score each memory
  const scored: MemoryScored[] = candidates.map(memory => {
    const keywordScore = computeKeywordScore(query, memory.text);
    const recencyScore = computeRecencyScore(memory.createdAt, memory.updatedAt);
    const importanceScore = computeImportanceScore(memory);

    const totalScore =
      keywordScore * (1 - opts.boostRecent - opts.boostImportant) +
      recencyScore * opts.boostRecent +
      importanceScore * opts.boostImportant;

    return {
      ...memory,
      relevanceScore: keywordScore,
      recencyScore,
      importanceScore,
      totalScore,
    };
  });

  // Filter and sort
  return scored
    .filter(m => m.totalScore >= opts.minScore)
    .sort((a, b) => b.totalScore - a.totalScore)
    .slice(0, opts.maxResults);
}
