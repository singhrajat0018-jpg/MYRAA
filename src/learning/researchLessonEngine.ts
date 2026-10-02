// ============================================================================
// MYRAA Phase 28 — Research Lesson Engine
// Manages structured research lessons with confidence, decay, and conflicts.
// ============================================================================

import type { ResearchLesson, RegimeType, TimeHorizon, StrategyType } from './contracts';

export class ResearchLessonEngine {
  private lessons = new Map<string, ResearchLesson>();

  createLesson(params: {
    source: string;
    strategyId: string;
    context: string;
    failureOrSuccess: 'FAILURE' | 'SUCCESS';
    recommendation: string;
    confidence: number;
    regime?: RegimeType;
    strategyType?: StrategyType;
    horizon?: TimeHorizon;
    volatilityRegime?: 'HIGH' | 'NORMAL' | 'LOW';
    expiresAt?: string;
    regrets?: string[];
  }): ResearchLesson {
    const id = `lesson_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const lesson: ResearchLesson = {
      lessonId: id,
      source: params.source,
      strategyId: params.strategyId,
      context: params.context,
      failureOrSuccess: params.failureOrSuccess,
      recommendation: params.recommendation,
      confidence: params.confidence,
      createdAt: new Date().toISOString(),
      expiresAt: params.expiresAt || new Date(Date.now() + 90 * 24 * 3600 * 1000).toISOString(),
      regrets: params.regrets,
      applicability: {
        regime: params.regime,
        strategyType: params.strategyType,
        horizon: params.horizon,
        volatilityRegime: params.volatilityRegime,
      },
    };
    this.lessons.set(id, lesson);
    return lesson;
  }

  getLesson(lessonId: string): ResearchLesson | undefined {
    return this.lessons.get(lessonId);
  }

  getAllLessons(): ResearchLesson[] {
    return Array.from(this.lessons.values());
  }

  getLessonsByStrategy(strategyId: string): ResearchLesson[] {
    return this.getAllLessons().filter(l => l.strategyId === strategyId);
  }

  getLessonsByRegime(regime: RegimeType): ResearchLesson[] {
    return this.getAllLessons().filter(l => l.applicability.regime === regime);
  }

  getLessonsByType(failureOrSuccess: 'FAILURE' | 'SUCCESS'): ResearchLesson[] {
    return this.getAllLessons().filter(l => l.failureOrSuccess === failureOrSuccess);
  }

  getActiveLessons(): ResearchLesson[] {
    const now = Date.now();
    return this.getAllLessons().filter(l => !l.expiresAt || new Date(l.expiresAt).getTime() > now);
  }

  getExpiredLessons(): ResearchLesson[] {
    const now = Date.now();
    return this.getAllLessons().filter(l => l.expiresAt && new Date(l.expiresAt).getTime() <= now);
  }

  getConflictingLessons(strategyId: string): ResearchLesson[] {
    const lessons = this.getLessonsByStrategy(strategyId);
    const failures = lessons.filter(l => l.failureOrSuccess === 'FAILURE');
    const successes = lessons.filter(l => l.failureOrSuccess === 'SUCCESS');
    if (failures.length > 0 && successes.length > 0) return lessons;
    return [];
  }

  applyDecay(lessonId: string, decayFactor: number): ResearchLesson | undefined {
    const lesson = this.lessons.get(lessonId);
    if (!lesson) return undefined;
    const updated: ResearchLesson = {
      ...lesson,
      confidence: lesson.confidence * decayFactor,
    };
    this.lessons.set(lessonId, updated);
    return updated;
  }

  getRelevantLessons(params: {
    strategyId?: string;
    regime?: RegimeType;
    horizon?: TimeHorizon;
    strategyType?: StrategyType;
    limit?: number;
  }): ResearchLesson[] {
    let lessons = this.getActiveLessons();

    if (params.strategyId) {
      lessons = lessons.filter(l => l.strategyId === params.strategyId);
    }
    if (params.regime) {
      lessons = lessons.filter(l => !l.applicability.regime || l.applicability.regime === params.regime);
    }
    if (params.horizon) {
      lessons = lessons.filter(l => !l.applicability.horizon || l.applicability.horizon === params.horizon);
    }
    if (params.strategyType) {
      lessons = lessons.filter(l => !l.applicability.strategyType || l.applicability.strategyType === params.strategyType);
    }

    lessons.sort((a, b) => b.confidence - a.confidence);
    return lessons.slice(0, params.limit || 20);
  }

  deleteLesson(lessonId: string): boolean {
    return this.lessons.delete(lessonId);
  }

  clearExpired(): number {
    const expired = this.getExpiredLessons();
    for (const l of expired) {
      this.lessons.delete(l.lessonId);
    }
    return expired.length;
  }
}

export const researchLessonEngine = new ResearchLessonEngine();
