// ============================================================================
// MYRAA Strategy Selector — Choose reasoning strategy based on goal/context
// ============================================================================

import type { Goal, StructuredIntent, ReasoningStrategy, TaskClassifier, GoalType, TaskComplexity } from './contracts';

// ============================================================================
// Strategy Selector
// ============================================================================

export class StrategySelector {
  selectStrategy(goal: Goal): ReasoningStrategy {
    const intent = goal.normalizedIntent;
    if (!intent) return 'DIRECT';

    // Fast path: trivial/simple non-external → DIRECT
    if ((intent.complexity === 'TRIVIAL' || intent.complexity === 'SIMPLE') && !intent.requiresExternalData) {
      return 'DIRECT';
    }

    // Goal-type based strategy
    const strategyByGoalType: Record<GoalType, ReasoningStrategy> = {
      QUESTION: intent.requiresExternalData ? 'EVIDENCE_DRIVEN' : 'DIRECT',
      RESEARCH: 'RESEARCH_FIRST',
      DECISION: 'COMPARATIVE',
      COMPARISON: 'COMPARATIVE',
      ACTION: 'ACTION_FIRST',
      MULTI_STEP_TASK: 'STEPWISE',
      TROUBLESHOOTING: 'DIAGNOSTIC',
      ANALYSIS: 'EVIDENCE_DRIVEN',
      MONITORING: 'EVIDENCE_DRIVEN',
      OPTIMIZATION: 'EVIDENCE_DRIVEN',
      CREATIVE: 'DIRECT',
      INFORMATION_GATHERING: 'EVIDENCE_DRIVEN',
      PLANNED_TASK: 'STEPWISE',
      DESIGN: 'STEPWISE',
      SYSTEM_OPERATION: 'ACTION_FIRST',
      TRADING_DECISION: 'COMPARATIVE',
    };

    const baseStrategy = strategyByGoalType[goal.normalizedIntent?.goalType || 'QUESTION'] || 'EVIDENCE_DRIVEN';

    // Override for decision-heavy tasks
    if (intent.requiresDecision && intent.entities.length >= 2) return 'COMPARATIVE';

    // Override for high complexity
    if (intent.complexity === 'HIGHLY_COMPLEX') return 'STEPWISE';

    return baseStrategy;
  }

  classifyTask(goal: Goal): TaskClassifier {
    const intent = goal.normalizedIntent;
    if (!intent) return 'DIRECT_ANSWER';

    if (intent.complexity === 'TRIVIAL' && !intent.requiresExternalData && !intent.requiresAction) return 'DIRECT_ANSWER';
    if (intent.requiresAction && !intent.requiresExternalData) return 'ACTION';
    if (goal.normalizedIntent?.goalType === 'MONITORING') return 'MONITOR';
    if (goal.normalizedIntent?.goalType === 'DECISION' || goal.normalizedIntent?.goalType === 'COMPARISON') return 'DECISION';
    if (goal.normalizedIntent?.goalType === 'RESEARCH') return 'RESEARCH';
    if (intent.complexity === 'MEDIUM' || intent.complexity === 'COMPLEX') return 'MULTI_STEP';
    if (intent.requiresExternalData && intent.requiresAction) return 'HYBRID';
    if (intent.requiresExternalData) return 'RETRIEVE';
    return 'DIRECT_ANSWER';
  }

  estimateReasoningDepth(goal: Goal): 'SHALLOW' | 'MODERATE' | 'DEEP' {
    const intent = goal.normalizedIntent;
    if (!intent) return 'SHALLOW';

    if (intent.complexity === 'TRIVIAL') return 'SHALLOW';
    if (intent.complexity === 'SIMPLE' && !intent.requiresDecision) return 'SHALLOW';
    if (intent.complexity === 'MEDIUM' || intent.requiresDecision) return 'MODERATE';
    return 'DEEP';
  }
}
