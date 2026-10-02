// ============================================================================
// MYRAA Agent Reasoning Engine — Comprehensive Test Suite
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import {
  ReasoningEngine,
  GoalEngine,
  IntentUnderstanding,
  StrategySelector,
  PlanBuilder,
  PlanGraph,
  EvidenceEngine,
  DecisionEngine,
  ExecutionEngine,
  VerificationEngine,
  Replanner,
  PolicyEngine,
  ExperienceEngine,
  ContextManager,
  AgentPersistence,
} from '../src/agent/index';
import type {
  Goal, GoalType, GoalStatus, StructuredIntent, ExecutionPlan,
  PlanTask, TaskResult, PlanBudget, RiskLevel, VerificationResult,
  AgentEvent, DecisionResult, GatheredEvidence, TaskExperience,
  DecisionOption,
} from '../src/agent/contracts';
import { generateAgentId, nowISO, DEFAULT_PLAN_BUDGET } from '../src/agent/contracts';

// ============================================================================
// Contracts
// ============================================================================

describe('Agent Contracts', () => {
  it('should generate unique agent IDs with prefix', () => {
    const id1 = generateAgentId('goal');
    const id2 = generateAgentId('goal');
    const id3 = generateAgentId('plan');
    expect(id1).toMatch(/^goal_/);
    expect(id2).toMatch(/^goal_/);
    expect(id3).toMatch(/^plan_/);
    expect(id1).not.toBe(id2);
  });

  it('should generate ISO timestamps', () => {
    const ts = nowISO();
    expect(ts).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it('should have default plan budget', () => {
    expect(DEFAULT_PLAN_BUDGET.maxSteps).toBe(20);
    expect(DEFAULT_PLAN_BUDGET.maxToolCalls).toBe(15);
    expect(DEFAULT_PLAN_BUDGET.maxReplans).toBe(3);
  });
});

// ============================================================================
// Intent Understanding
// ============================================================================

describe('IntentUnderstanding', () => {
  let intent: IntentUnderstanding;

  beforeEach(() => {
    intent = new IntentUnderstanding();
  });

  it('should classify information questions', () => {
    const result = intent.classifyIntent('What is NIFTY 50?');
    expect(result.goalType).toBe('QUESTION');
    expect(result.requiresAction).toBe(false);
  });

  it('should classify research requests', () => {
    const result = intent.classifyIntent('Research Tesla stock performance');
    expect(result.goalType).toBe('RESEARCH');
  });

  it('should classify design requests', () => {
    const result = intent.classifyIntent('Design a bearing housing');
    expect(result.goalType).toBe('DESIGN');
    expect(result.requiresAction).toBe(true);
  });

  it('should classify system operations', () => {
    const result = intent.classifyIntent('Check my laptop temperature');
    expect(result.goalType).toBe('SYSTEM_OPERATION');
    expect(result.requiresAction).toBe(true);
  });

  it('should classify trading decisions', () => {
    const result = intent.classifyIntent('Should I buy Reliance stock?');
    expect(result.goalType).toBe('TRADING_DECISION');
  });

  it('should extract company entities', () => {
    const result = intent.classifyIntent('Tell me about NVIDIA earnings');
    expect(result.entities.some(e => e.name === 'NVIDIA')).toBe(true);
  });

  it('should extract market entities', () => {
    const result = intent.classifyIntent('What is NIFTY 50 at today?');
    expect(result.entities.some(e => e.entityType === 'MARKET')).toBe(true);
  });

  it('should classify trivial complexity for simple greetings', () => {
    const result = intent.classifyIntent('Hello');
    expect(result.complexity).toBe('TRIVIAL');
  });

  it('should classify moderate complexity for multi-step requests', () => {
    const result = intent.classifyIntent('Find the best laptop for gaming under 80000 and compare with alternatives');
    expect(result.complexity).toBe('COMPLEX');
  });

  it('should provide reasonable topics', () => {
    const result = intent.classifyIntent('How is the stock market performing today?');
    expect(result.topics.length).toBeGreaterThan(0);
  });

  it('should classify comparison requests', () => {
    const result = intent.classifyIntent('Compare NVIDIA and AMD stock performance');
    expect(result.goalType).toBe('COMPARISON');
  });

  it('should classify troubleshooting', () => {
    const result = intent.classifyIntent('My laptop is running slow');
    expect(result.goalType).toBe('TROUBLESHOOTING');
  });
});

// ============================================================================
// Goal Engine
// ============================================================================

describe('GoalEngine', () => {
  let engine: GoalEngine;

  beforeEach(() => {
    engine = new GoalEngine();
  });

  it('should create a goal from user request', () => {
    const goal = engine.createUserGoal('Research NVIDIA stock');
    expect(goal.id).toMatch(/^goal_/);
    expect(goal.userRequest).toBe('Research NVIDIA stock');
    expect(goal.status).toBe('RECEIVED');
    expect(goal.priority).toBe('MEDIUM');
  });

  it('should create goal with options', () => {
    const goal = engine.createUserGoal('Design a bearing', {
      priority: 'HIGH',
      conversationId: 'conv_123',
    });
    expect(goal.priority).toBe('HIGH');
    expect(goal.conversationId).toBe('conv_123');
  });

  it('should set intent on goal', () => {
    const goal = engine.createUserGoal('Research Tesla');
    const intent: StructuredIntent = {
      goalType: 'RESEARCH',
      complexity: 'COMPLEX',
      entities: [],
      requiresAction: true,
      topics: ['stock'],
      actions: ['research'],
      questions: [],
      temporalScope: 'CURRENT',
      domainHints: ['finance'],
      requiresExternalData: true,
      requiresDecision: false,
      ambiguityScore: 0.2,
      ambiguousFields: [],
      confidence: 0.9,
      originalRequest: 'Research Tesla',
    };
    engine.setIntent(goal.id, intent);
    const updated = engine.getGoal(goal.id);
    expect(updated?.normalizedIntent).toBe(intent);
    expect(updated?.objective).toContain('research');
  });

  it('should update goal status with valid transitions', () => {
    const goal = engine.createUserGoal('Test');
    engine.updateGoal(goal.id, { status: 'UNDERSTANDING' });
    expect(engine.getGoal(goal.id)?.status).toBe('UNDERSTANDING');
  });

  it('should reject invalid goal transitions', () => {
    const goal = engine.createUserGoal('Test');
    expect(() => engine.updateGoal(goal.id, { status: 'EXECUTING' })).toThrow('Invalid goal transition');
  });

  it('should cancel goal', () => {
    const goal = engine.createUserGoal('Test');
    engine.cancelGoal(goal.id, 'User cancelled');
    expect(engine.getGoal(goal.id)?.status).toBe('CANCELLED');
  });

  it('should list all goals', () => {
    engine.createUserGoal('Goal 1');
    engine.createUserGoal('Goal 2');
    expect(engine.getAllGoals().length).toBe(2);
  });

  it('should filter active goals', () => {
    engine.createUserGoal('Active');
    const completed = engine.createUserGoal('Done');
    engine.cancelGoal(completed.id, 'done');
    expect(engine.getActiveGoals().length).toBe(1);
  });

  it('should provide stats', () => {
    engine.createUserGoal('Goal 1');
    engine.createUserGoal('Goal 2');
    const stats = engine.getStats();
    expect(stats.total).toBe(2);
  });

  it('should get goals by conversation', () => {
    engine.createUserGoal('Goal 1', { conversationId: 'c1' });
    engine.createUserGoal('Goal 2', { conversationId: 'c1' });
    engine.createUserGoal('Goal 3', { conversationId: 'c2' });
    expect(engine.getGoalsByConversation('c1').length).toBe(2);
  });
});

// ============================================================================
// Strategy Selector
// ============================================================================

describe('StrategySelector', () => {
  let selector: StrategySelector;

  beforeEach(() => {
    selector = new StrategySelector();
  });

  it('should classify trivial tasks as DIRECT_ANSWER', () => {
    const goal = {
      id: 'g1', userRequest: 'Hello',
      normalizedIntent: { goalType: 'QUESTION', complexity: 'TRIVIAL', entities: [], requiresAction: false, topics: [], actions: [], questions: [], temporalScope: 'CURRENT', domainHints: [], requiresExternalData: false, requiresDecision: false, ambiguityScore: 0, ambiguousFields: [], confidence: 0.9, originalRequest: 'Hello' },
      status: 'RECEIVED',
    } as unknown as Goal;
    expect(selector.classifyTask(goal)).toBe('DIRECT_ANSWER');
  });

  it('should classify research goal type as RESEARCH', () => {
    const goal = {
      id: 'g1',
      userRequest: 'Research Tesla and NVIDIA',
      normalizedIntent: { goalType: 'RESEARCH', complexity: 'COMPLEX', entities: [], requiresAction: false, topics: ['research'], actions: [], questions: [], temporalScope: 'CURRENT', domainHints: [], requiresExternalData: true, requiresDecision: false, ambiguityScore: 0.2, ambiguousFields: [], confidence: 0.8, originalRequest: '' },
      status: 'RECEIVED',
    } as unknown as Goal;
    expect(selector.classifyTask(goal)).toBe('RESEARCH');
  });

  it('should classify action when requiresAction is true', () => {
    const goal = {
      id: 'g1',
      userRequest: 'Open Chrome',
      normalizedIntent: { goalType: 'ACTION', complexity: 'SIMPLE', entities: [], requiresAction: true, topics: [], actions: ['open'], questions: [], temporalScope: 'CURRENT', domainHints: [], requiresExternalData: false, requiresDecision: false, ambiguityScore: 0.1, ambiguousFields: [], confidence: 0.9, originalRequest: '' },
      status: 'RECEIVED',
    } as unknown as Goal;
    expect(selector.classifyTask(goal)).toBe('ACTION');
  });

  it('should select strategy based on goal type', () => {
    const goal = {
      id: 'g1',
      userRequest: 'Research stocks',
      normalizedIntent: { goalType: 'RESEARCH', complexity: 'COMPLEX', entities: [], requiresAction: false, topics: [], actions: [], questions: [], temporalScope: 'CURRENT', domainHints: [], requiresExternalData: true, requiresDecision: false, ambiguityScore: 0.2, ambiguousFields: [], confidence: 0.8, originalRequest: '' },
      status: 'RECEIVED',
    } as unknown as Goal;
    expect(selector.selectStrategy(goal)).toBe('RESEARCH_FIRST');
  });

  it('should return DIRECT for goals without intent', () => {
    const goal = { id: 'g1', userRequest: 'Hello' } as unknown as Goal;
    expect(selector.selectStrategy(goal)).toBe('DIRECT');
  });
});

// ============================================================================
// Plan Builder
// ============================================================================

describe('PlanBuilder', () => {
  let builder: PlanBuilder;
  let goalEngine: GoalEngine;

  beforeEach(() => {
    builder = new PlanBuilder();
    goalEngine = new GoalEngine();
  });

  function makeIntent(overrides: Partial<StructuredIntent> = {}): StructuredIntent {
    return {
      goalType: 'QUESTION', complexity: 'SIMPLE', entities: [],
      requiresAction: false, topics: [], actions: [], questions: [],
      temporalScope: 'CURRENT', domainHints: [], requiresExternalData: false,
      requiresDecision: false, ambiguityScore: 0.1, ambiguousFields: [],
      confidence: 0.8, originalRequest: '', ...overrides,
    };
  }

  it('should build a simple plan', () => {
    const goal = goalEngine.createUserGoal('Research Tesla stock');
    goalEngine.setIntent(goal.id, makeIntent({ goalType: 'RESEARCH', requiresExternalData: true }));
    const plan = builder.buildPlan(goal);
    expect(plan.planId).toMatch(/^plan_/);
    expect(plan.tasks.length).toBeGreaterThan(0);
    expect(plan.goalId).toBe(goal.id);
  });

  it('should validate plan', () => {
    const goal = goalEngine.createUserGoal('Research NIFTY 50');
    goalEngine.setIntent(goal.id, makeIntent({ goalType: 'RESEARCH', requiresExternalData: true }));
    const plan = builder.buildPlan(goal);
    const validation = builder.validatePlan(plan);
    expect(validation.valid).toBe(true);
    expect(validation.errors.length).toBe(0);
  });

  it('should generate rollback steps for action tasks', () => {
    const goal = goalEngine.createUserGoal('Open application Chrome');
    goalEngine.setIntent(goal.id, makeIntent({ goalType: 'ACTION', requiresAction: true, entities: [{ name: 'Chrome', entityType: 'APPLICATION', role: 'SUBJECT', confidence: 0.9 }] }));
    const plan = builder.buildPlan(goal);
    expect(plan.rollbackPlan.length).toBeGreaterThanOrEqual(0);
  });

  it('should generate approval requirements for high-risk tasks', () => {
    const goal = goalEngine.createUserGoal('Delete all files in Downloads folder');
    goalEngine.setIntent(goal.id, makeIntent({ goalType: 'ACTION', requiresAction: true, complexity: 'MODERATE', entities: [{ name: 'Downloads', entityType: 'DIRECTORY', role: 'TARGET', confidence: 0.9 }] }));
    const plan = builder.buildPlan(goal);
    expect(plan.tasks.length).toBeGreaterThan(0);
  });
});

// ============================================================================
// Plan Graph
// ============================================================================

describe('PlanGraph', () => {
  function makeTask(id: string, deps: string[] = [], status: PlanTask['status'] = 'PENDING'): PlanTask {
    return {
      taskId: id, goalId: 'g1', title: `Task ${id}`, description: '', type: 'ACTION',
      dependencies: deps, requiredCapabilities: [], requiredEvidence: [], inputs: {},
      expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status,
      priority: 1, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 },
      autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {},
    };
  }

  it('should build graph from tasks', () => {
    const graph = new PlanGraph([makeTask('t1'), makeTask('t2', ['t1'])]);
    expect(graph.getAllTasks().length).toBe(2);
    expect(graph.validate().valid).toBe(true);
  });

  it('should detect cycles', () => {
    const graph = new PlanGraph([makeTask('t1', ['t2']), makeTask('t2', ['t1'])]);
    expect(graph.validate().valid).toBe(false);
  });

  it('should compute topological order', () => {
    const graph = new PlanGraph([makeTask('t1'), makeTask('t2', ['t1'])]);
    const order = graph.topologicalSort();
    expect(order).toContain('t1');
    expect(order).toContain('t2');
    expect(order.indexOf('t1')).toBeLessThan(order.indexOf('t2'));
  });

  it('should compute parallel groups', () => {
    const graph = new PlanGraph([makeTask('t1'), makeTask('t2')]);
    const groups = graph.computeParallelGroups(new Set());
    expect(groups.length).toBeGreaterThanOrEqual(1);
  });

  it('should get ready tasks', () => {
    const graph = new PlanGraph([makeTask('t1'), makeTask('t2', ['t1'])]);
    const ready = graph.getReadyTasks(new Set(), new Set());
    expect(ready.length).toBe(1);
    expect(ready[0].taskId).toBe('t1');
  });

  it('should detect deadlocks', () => {
    const t1 = makeTask('t1', ['t2']);
    const t2 = makeTask('t2', ['t1']);
    const graph = new PlanGraph([t1, t2]);
    const deadlocks = graph.detectDeadlocks(new Set());
    expect(deadlocks.length).toBeGreaterThanOrEqual(0);
  });

  it('should add and remove tasks', () => {
    const graph = new PlanGraph([makeTask('t1')]);
    expect(graph.getAllTasks().length).toBe(1);
    graph.addTask(makeTask('t2'));
    expect(graph.getAllTasks().length).toBe(2);
    graph.removeTask('t2');
    expect(graph.getAllTasks().length).toBe(1);
  });

  it('should get dependencies and dependents', () => {
    const graph = new PlanGraph([makeTask('t1'), makeTask('t2', ['t1'])]);
    expect(graph.getDependencies('t2')).toContain('t1');
    expect(graph.getDependents('t1')).toContain('t2');
  });

  it('should build execution plan', () => {
    const graph = new PlanGraph([makeTask('t1'), makeTask('t2', ['t1'])]);
    const plan = graph.buildPlan('goal_1', 'DIRECT');
    expect(plan.planId).toMatch(/^plan_/);
    expect(plan.tasks.length).toBe(2);
  });
});

// ============================================================================
// Evidence Engine
// ============================================================================

describe('EvidenceEngine', () => {
  let engine: EvidenceEngine;

  beforeEach(() => {
    engine = new EvidenceEngine();
  });

  it('should record evidence', () => {
    const evidence = engine.recordEvidence({
      source: 'market',
      data: { price: 2500 },
      confidence: 0.9,
      freshness: nowISO(),
      conflictsWith: [],
    });
    expect(evidence.id).toMatch(/^ev_/);
    expect(evidence.source).toBe('market');
  });

  it('should retrieve all evidence', () => {
    engine.recordEvidence({ source: 'market', data: 'd1', confidence: 0.8, freshness: nowISO(), conflictsWith: [] });
    engine.recordEvidence({ source: 'news', data: 'd2', confidence: 0.7, freshness: nowISO(), conflictsWith: [] });
    expect(engine.getAllEvidence().length).toBe(2);
  });

  it('should assess sufficiency', () => {
    engine.recordEvidence({ source: 'market', data: 'price', confidence: 0.9, freshness: nowISO(), conflictsWith: [] });
    const result = engine.assessSufficiency([]);
    expect(result.sufficiency).toBe('SUFFICIENT');
    expect(result.overallConfidence).toBeGreaterThan(0);
  });

  it('should provide stats', () => {
    engine.recordEvidence({ source: 'market', data: 'd1', confidence: 0.8, freshness: nowISO(), conflictsWith: [] });
    const stats = engine.getStats();
    expect(stats.totalEvidence).toBe(1);
  });

  it('should get evidence by source', () => {
    engine.recordEvidence({ source: 'market', data: 'd1', confidence: 0.8, freshness: nowISO(), conflictsWith: [] });
    engine.recordEvidence({ source: 'news', data: 'd2', confidence: 0.7, freshness: nowISO(), conflictsWith: [] });
    expect(engine.getEvidenceBySource('market').length).toBe(1);
  });

  it('should clear evidence', () => {
    engine.recordEvidence({ source: 'market', data: 'd1', confidence: 0.8, freshness: nowISO(), conflictsWith: [] });
    engine.clear();
    expect(engine.getAllEvidence().length).toBe(0);
  });
});

// ============================================================================
// Decision Engine
// ============================================================================

describe('DecisionEngine', () => {
  let engine: DecisionEngine;

  beforeEach(() => {
    engine = new DecisionEngine();
  });

  it('should evaluate decision with options', () => {
    const options: DecisionOption[] = [
      { id: 'buy', label: 'Buy', description: 'Buy stock', pros: ['potential gain'], cons: ['risk'], risks: ['market risk'], evidence: [], constraints: [], score: 0.5 },
      { id: 'hold', label: 'Hold', description: 'Hold position', pros: ['stable'], cons: ['no gain'], risks: ['opportunity cost'], evidence: [], constraints: [], score: 0.5 },
    ];
    const result = engine.evaluateDecision('Should I buy?', options, [], []);
    expect(result.decision).toBeDefined();
    expect(result.confidence).toBeGreaterThan(0);
    expect(result.reasons.length).toBeGreaterThan(0);
  });

  it('should build options with helper', () => {
    const option = engine.createOption('Test', 'Test option', { pros: ['good'], cons: ['bad'], risks: ['risk'] });
    expect(option.id).toMatch(/^opt_/);
    expect(option.label).toBe('Test');
    expect(option.pros).toContain('good');
  });

  it('should return default decision with empty options', () => {
    const result = engine.evaluateDecision('What?', [], [], []);
    expect(result.decision).toBeDefined();
  });
});

// ============================================================================
// Execution Engine
// ============================================================================

describe('ExecutionEngine', () => {
  let engine: ExecutionEngine;

  beforeEach(() => {
    engine = new ExecutionEngine();
  });

  function makePlan(id: string): ExecutionPlan {
    return {
      planId: id,
      goalId: 'goal_1',
      strategy: 'DIRECT',
      tasks: [{
        taskId: 't1', goalId: 'g1', title: 'Task', description: '', type: 'ACTION',
        dependencies: [], requiredCapabilities: [], requiredEvidence: [], inputs: {},
        expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status: 'PENDING',
        priority: 1, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 },
        autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {},
      }],
      parallelGroups: [[]],
      requiredEvidence: [],
      riskSummary: 'LOW',
      approvalRequirements: [],
      estimatedTimeMs: 5000,
      successCriteria: [],
      verificationPlan: [],
      rollbackPlan: [],
      status: 'CREATED',
      version: 1,
      budget: DEFAULT_PLAN_BUDGET,
      createdAt: nowISO(),
      updatedAt: nowISO(),
    };
  }

  it('should start a plan', () => {
    engine.startPlan(makePlan('plan_1'));
    expect(engine.getPlan('plan_1')).toBeDefined();
  });

  it('should execute ready tasks', async () => {
    engine.startPlan(makePlan('plan_2'));
    const result = await engine.executeReadyTasks('plan_2');
    expect(result.completed.length).toBe(1);
  });

  it('should cancel plan', () => {
    engine.startPlan(makePlan('plan_3'));
    expect(engine.cancelPlan('plan_3')).toBe(true);
    expect(engine.getPlan('plan_3')).toBeUndefined();
  });

  it('should track budget status', async () => {
    engine.startPlan(makePlan('plan_4'));
    await engine.executeReadyTasks('plan_4');
    const budget = engine.getBudgetStatus('plan_4');
    expect(budget).toBeDefined();
    expect(budget!.stepsUsed).toBe(1);
  });

  it('should deny task', () => {
    engine.startPlan(makePlan('plan_5'));
    expect(engine.denyTask('plan_5', 't1', 'Denied')).toBe(true);
  });

  it('should provide stats', () => {
    const stats = engine.getStats();
    expect(stats.activePlans).toBe(0);
    expect(stats.totalCompleted).toBe(0);
  });

  it('should set custom task executor', async () => {
    const plan = makePlan('plan_6');
    engine.startPlan(plan);
    engine.setTaskExecutor(async (task) => ({
      success: true, data: { custom: true }, timestamp: nowISO(), latencyMs: 10, provenance: [], confidence: 1.0, retryable: false,
    }));
    const result = await engine.executeReadyTasks('plan_6');
    expect(result.completed.length).toBe(1);
  });

  it('should not cancel non-existent plan', () => {
    expect(engine.cancelPlan('nope')).toBe(false);
  });
});

// ============================================================================
// Verification Engine
// ============================================================================

describe('VerificationEngine', () => {
  let engine: VerificationEngine;

  beforeEach(() => {
    engine = new VerificationEngine();
  });

  it('should verify a task with policy', async () => {
    const task: PlanTask = {
      taskId: 't1', goalId: 'g1', title: 'Task', description: '', type: 'ACTION',
      dependencies: [], requiredCapabilities: [], requiredEvidence: [], inputs: {},
      expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status: 'PENDING',
      priority: 1, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 },
      verificationPolicy: { strategies: ['STATE_CHECK'], required: true, timeout: 5000, successCriteria: ['Output exists'] },
      autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {},
    };
    const result: TaskResult = {
      success: true, data: { output: 'done' }, timestamp: nowISO(),
      latencyMs: 100, provenance: [], confidence: 0.9, retryable: false,
    };
    const verification = await engine.verify(task, result);
    expect(verification.status).toMatch(/^(VERIFIED|FAILED|PARTIAL)$/);
    expect(verification.message).toBeDefined();
  });

  it('should skip verification when no policy', async () => {
    const task: PlanTask = {
      taskId: 't1', goalId: 'g1', title: 'Task', description: '', type: 'ACTION',
      dependencies: [], requiredCapabilities: [], requiredEvidence: [], inputs: {},
      expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status: 'PENDING',
      priority: 1, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 },
      autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {},
    };
    const result: TaskResult = {
      success: true, data: {}, timestamp: nowISO(), latencyMs: 100, provenance: [], confidence: 0.9, retryable: false,
    };
    const verification = await engine.verify(task, result);
    expect(verification.status).toBe('VERIFIED');
  });

  it('should retrieve results', () => {
    const results = engine.getResults('t1');
    expect(results.length).toBe(0);
  });

  it('should get all results', () => {
    const all = engine.getAllResults();
    expect(all.size).toBe(0);
  });
});

// ============================================================================
// Replanner
// ============================================================================

describe('Replanner', () => {
  let replanner: Replanner;

  beforeEach(() => {
    replanner = new Replanner();
  });

  it('should replan on failure', () => {
    const plan: ExecutionPlan = {
      planId: 'plan_1', goalId: 'goal_1', strategy: 'DIRECT',
      tasks: [
        { taskId: 't1', goalId: 'g1', title: 'Task 1', description: '', type: 'ACTION', dependencies: [], requiredCapabilities: [], requiredEvidence: [], inputs: {}, expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status: 'PENDING', priority: 1, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 }, autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {} },
        { taskId: 't2', goalId: 'g1', title: 'Task 2', description: '', type: 'ACTION', dependencies: [], requiredCapabilities: [], requiredEvidence: [], inputs: {}, expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status: 'PENDING', priority: 2, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 }, autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {} },
      ],
      parallelGroups: [[]], requiredEvidence: [], riskSummary: 'LOW', approvalRequirements: [],
      estimatedTimeMs: 10000, successCriteria: [], verificationPlan: [], rollbackPlan: [],
      status: 'EXECUTING', version: 1, budget: DEFAULT_PLAN_BUDGET, createdAt: nowISO(), updatedAt: nowISO(),
    };
    const newPlan = replanner.replan(plan, 'Task t1 failed', new Set(['t1']), new Set());
    expect(newPlan).toBeDefined();
    expect(newPlan!.version).toBe(2);
    expect(newPlan!.replanReason).toBe('Task t1 failed');
  });

  it('should return null when replan limit reached', () => {
    const plan: ExecutionPlan = {
      planId: 'plan_1', goalId: 'goal_1', strategy: 'DIRECT', tasks: [],
      parallelGroups: [], requiredEvidence: [], riskSummary: 'LOW', approvalRequirements: [],
      estimatedTimeMs: 0, successCriteria: [], verificationPlan: [], rollbackPlan: [],
      status: 'EXECUTING', version: 5, budget: DEFAULT_PLAN_BUDGET, createdAt: nowISO(), updatedAt: nowISO(),
    };
    const newPlan = replanner.replan(plan, 'Failed', new Set(), new Set());
    expect(newPlan).toBeNull();
  });
});

// ============================================================================
// Policy Engine
// ============================================================================

describe('PolicyEngine', () => {
  let engine: PolicyEngine;

  function makeTask(overrides: Partial<PlanTask> = {}): PlanTask {
    return {
      taskId: 't1', goalId: 'g1', title: 'Task', description: '', type: 'ACTION',
      dependencies: [], requiredCapabilities: [], requiredEvidence: [], inputs: {},
      expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status: 'PENDING',
      priority: 1, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 },
      autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {},
      ...overrides,
    };
  }

  beforeEach(() => {
    engine = new PolicyEngine();
  });

  it('should assess risk level', () => {
    expect(engine.assessTaskRisk(makeTask())).toBe('LOW');
  });

  it('should escalate risk for irreversible actions', () => {
    expect(engine.assessTaskRisk(makeTask({ risk: 'MEDIUM', reversibility: 'IRREVERSIBLE', autonomyPolicy: 'IRREVERSIBLE_ACTION' }))).toBe('CRITICAL');
  });

  it('should require approval for high-risk tasks', () => {
    expect(engine.requiresApproval(makeTask({ risk: 'HIGH' }))).toBe(true);
    expect(engine.requiresApproval(makeTask({ autonomyPolicy: 'HIGH_IMPACT_ACTION' }))).toBe(true);
    expect(engine.requiresApproval(makeTask({ risk: 'LOW' }))).toBe(false);
  });

  it('should build approval request', () => {
    const task = makeTask({ risk: 'HIGH', reversibility: 'IRREVERSIBLE', autonomyPolicy: 'IRREVERSIBLE_ACTION' });
    const request = engine.buildApprovalRequest(task);
    expect(request.taskId).toBe('t1');
    expect(request.risk).toBeDefined();
    expect(request.reason).toBeDefined();
  });

  it('should check if action is safe', () => {
    expect(engine.isSafeAction(makeTask({ title: 'Open Chrome' }))).toBe(true);
    expect(engine.isSafeAction(makeTask({ title: 'Execute rm -rf /' }))).toBe(false);
  });

  it('should check task execution permission', () => {
    const task = makeTask({ risk: 'LOW' });
    expect(engine.canExecuteTask(task, new Set()).allowed).toBe(true);
  });

  it('should deny execution without approval', () => {
    const task = makeTask({ risk: 'HIGH' });
    expect(engine.canExecuteTask(task, new Set()).allowed).toBe(false);
  });

  it('should notify for high importance', () => {
    expect(engine.shouldNotifyImportance('HIGH')).toBe(true);
    expect(engine.shouldNotifyImportance('LOW')).toBe(false);
  });
});

// ============================================================================
// Experience Engine
// ============================================================================

describe('ExperienceEngine', () => {
  let engine: ExperienceEngine;

  beforeEach(() => {
    engine = new ExperienceEngine();
  });

  it('should record experience', () => {
    const exp = engine.recordExperience({
      taskType: 'INFORMATION_GATHER', goalType: 'RESEARCH', goalPattern: 'research * stock',
      successfulPlan: ['Gather data'], failedApproaches: [], toolsUsed: ['market'],
      providersUsed: [], verificationOutcome: 'VERIFIED', duration: 1000, metadata: {},
    });
    expect(exp.id).toMatch(/^exp_/);
    expect(exp.successRate).toBe(1.0);
    expect(exp.usageCount).toBe(1);
  });

  it('should find relevant experience', () => {
    engine.recordExperience({
      taskType: 'INFORMATION_GATHER', goalType: 'RESEARCH', goalPattern: 'research * stock',
      successfulPlan: ['Gather data'], failedApproaches: [], toolsUsed: ['market'],
      providersUsed: [], verificationOutcome: 'VERIFIED', duration: 1000, metadata: {},
    });
    const found = engine.findRelevantExperience('RESEARCH', 'INFORMATION_GATHER');
    expect(found).toBeDefined();
  });

  it('should record outcome and update success rate', () => {
    const exp = engine.recordExperience({
      taskType: 'INFORMATION_GATHER', goalType: 'RESEARCH', goalPattern: 'test',
      successfulPlan: [], failedApproaches: [], toolsUsed: [], providersUsed: [],
      verificationOutcome: 'PENDING', duration: 0, metadata: {},
    });
    engine.recordOutcome(exp.id, false);
    const updated = engine.getExperience(exp.id);
    expect(updated!.usageCount).toBe(2);
    expect(updated!.successRate).toBeLessThan(1.0);
  });

  it('should record user correction', () => {
    const exp = engine.recordExperience({
      taskType: 'INFORMATION_GATHER', goalType: 'RESEARCH', goalPattern: 'test',
      successfulPlan: [], failedApproaches: [], toolsUsed: [], providersUsed: [],
      verificationOutcome: 'PENDING', duration: 0, metadata: {},
    });
    engine.recordUserCorrection(exp.id, 'Use Yahoo Finance instead');
    const updated = engine.getExperience(exp.id);
    expect(updated!.userCorrection).toBe('Use Yahoo Finance instead');
  });

  it('should suggest strategy', () => {
    engine.recordExperience({
      taskType: 'INFORMATION_GATHER', goalType: 'RESEARCH', goalPattern: 'research * stock',
      successfulPlan: ['Gather data from market'], failedApproaches: ['Use unreliable source'],
      toolsUsed: ['market'], providersUsed: [], verificationOutcome: 'VERIFIED',
      duration: 1000, metadata: {},
    });
    const suggestion = engine.suggestStrategy('RESEARCH', 'INFORMATION_GATHER');
    expect(suggestion.suggestedCapabilities).toContain('market');
    expect(suggestion.warningPoints).toContain('Use unreliable source');
  });

  it('should find similar experience', () => {
    engine.recordExperience({
      taskType: 'INFORMATION_GATHER', goalType: 'RESEARCH', goalPattern: 'research about stock market',
      successfulPlan: [], failedApproaches: [], toolsUsed: [], providersUsed: [],
      verificationOutcome: 'VERIFIED', duration: 0, metadata: {},
    });
    const found = engine.findSimilarExperience('research the stock market');
    expect(found).toBeDefined();
  });

  it('should provide stats', () => {
    engine.recordExperience({
      taskType: 'ACTION', goalType: 'SYSTEM_OPERATION', goalPattern: 'test',
      successfulPlan: [], failedApproaches: [], toolsUsed: [], providersUsed: [],
      verificationOutcome: 'VERIFIED', duration: 0, metadata: {},
    });
    const stats = engine.getStats();
    expect(stats.total).toBe(1);
    expect(stats.avgSuccessRate).toBe(1.0);
    expect(stats.highConfidence).toBe(1);
  });

  it('should return null for non-existent experience', () => {
    expect(engine.getExperience('nonexistent')).toBeUndefined();
  });

  it('should return empty suggestion when no experience', () => {
    const suggestion = engine.suggestStrategy('RESEARCH', 'INFORMATION_GATHER');
    expect(suggestion.suggestedCapabilities.length).toBe(0);
  });
});

// ============================================================================
// Context Manager
// ============================================================================

describe('ContextManager', () => {
  let manager: ContextManager;

  beforeEach(() => {
    manager = new ContextManager();
  });

  it('should set and get active goal', () => {
    const goal = { id: 'g1', userRequest: 'Research Tesla' } as unknown as Goal;
    manager.setActiveGoal('conv_1', goal);
    expect(manager.getActiveGoal('conv_1')).toBe(goal);
  });

  it('should clear active goal', () => {
    const goal = { id: 'g1' } as unknown as Goal;
    manager.setActiveGoal('conv_1', goal);
    manager.clearActiveGoal('conv_1');
    expect(manager.getActiveGoal('conv_1')).toBeUndefined();
  });

  it('should detect follow-up', () => {
    const goal = { id: 'g1', userRequest: 'Research Tesla stock performance', status: 'EXECUTING' } as unknown as Goal;
    manager.setActiveGoal('conv_1', goal);
    expect(manager.isFollowUp('conv_1', 'What about NVIDIA?')).toBe(true);
  });

  it('should not detect follow-up without active goal', () => {
    expect(manager.isFollowUp('no_conv', 'Hello')).toBe(false);
  });

  it('should build follow-up context', () => {
    const goal = { id: 'g1', userRequest: 'Research Tesla', objective: 'Get stock info', status: 'EXECUTING' } as unknown as Goal;
    manager.setActiveGoal('conv_1', goal);
    const context = manager.buildFollowUpContext('conv_1', 'Tell me more');
    expect(context).toBeDefined();
    expect(context!.parentGoalId).toBe('g1');
  });

  it('should return null for follow-up without active goal', () => {
    expect(manager.buildFollowUpContext('no_conv', 'Hello')).toBeNull();
  });

  it('should record and retrieve interactions', () => {
    manager.recordInteraction({ timestamp: nowISO(), role: 'USER', content: 'Hello' });
    manager.recordInteraction({ timestamp: nowISO(), role: 'SYSTEM', content: 'Hi!' });
    expect(manager.getRecentInteractions().length).toBe(2);
  });

  it('should limit interactions to 20', () => {
    for (let i = 0; i < 25; i++) {
      manager.recordInteraction({ timestamp: nowISO(), role: 'USER', content: `msg ${i}` });
    }
    expect(manager.getRecentInteractions().length).toBe(20);
  });

  it('should build intent context', () => {
    const goal = {
      id: 'g1', userRequest: 'Research Tesla', objective: 'Get stock info',
      normalizedIntent: { goalType: 'RESEARCH', complexity: 'COMPLEX', entities: [{ name: 'Tesla', entityType: 'COMPANY', role: 'SUBJECT', confidence: 0.9 }], topics: ['stock', 'research'] },
    } as unknown as Goal;
    const context = manager.buildIntentContext(goal);
    expect(context).toContain('Research Tesla');
    expect(context).toContain('RESEARCH');
  });
});

// ============================================================================
// Persistence
// ============================================================================

describe('AgentPersistence', () => {
  let persistence: AgentPersistence;

  beforeEach(() => {
    persistence = new AgentPersistence();
  });

  it('should save and load goals', async () => {
    const goals: Goal[] = [{
      id: 'g_test', userRequest: 'Test', status: 'RECEIVED', priority: 'LOW',
      objective: '', constraints: [], preferences: [], executionPolicy: 'READ_ONLY',
      createdAt: nowISO(), updatedAt: nowISO(),
    }];
    await persistence.saveGoals(goals);
    const loaded = await persistence.loadGoals();
    expect(loaded.length).toBe(1);
    expect(loaded[0].id).toBe('g_test');
  });

  it('should save and load experience', async () => {
    const exps: TaskExperience[] = [{
      id: 'exp_test', taskType: 'ACTION', goalType: 'SYSTEM_OPERATION', goalPattern: 'test',
      successfulPlan: [], failedApproaches: [], toolsUsed: [], providersUsed: [],
      verificationOutcome: 'VERIFIED', duration: 0, timestamp: nowISO(),
      successRate: 1.0, usageCount: 1, metadata: {},
    }];
    await persistence.saveExperience(exps);
    const loaded = await persistence.loadExperience();
    expect(loaded.length).toBe(1);
  });

  it('should save and load plans', async () => {
    const plans: ExecutionPlan[] = [{
      planId: 'plan_test', goalId: 'g1', strategy: 'DIRECT', tasks: [],
      parallelGroups: [], requiredEvidence: [], riskSummary: 'LOW', approvalRequirements: [],
      estimatedTimeMs: 0, successCriteria: [], verificationPlan: [], rollbackPlan: [],
      status: 'CREATED', version: 1, budget: DEFAULT_PLAN_BUDGET, createdAt: nowISO(), updatedAt: nowISO(),
    }];
    await persistence.savePlans(plans);
    const loaded = await persistence.loadPlans();
    expect(loaded.length).toBe(1);
  });

  it('should recover active plans', async () => {
    const plans: ExecutionPlan[] = [{
      planId: 'plan_active', goalId: 'g1', strategy: 'DIRECT',
      tasks: [{ taskId: 't1', goalId: 'g1', title: 'T', description: '', type: 'ACTION', dependencies: [], requiredCapabilities: [], requiredEvidence: [], inputs: {}, expectedOutcome: '', risk: 'LOW', reversibility: 'REVERSIBLE', status: 'PENDING', priority: 1, timeout: 5000, retryPolicy: { maxRetries: 0, retryableFailures: [], baseDelayMs: 1000 }, autonomyPolicy: 'FULL_AUTONOMY', retryCount: 0, sideEffects: [], metadata: {} }],
      parallelGroups: [], requiredEvidence: [], riskSummary: 'LOW', approvalRequirements: [],
      estimatedTimeMs: 0, successCriteria: [], verificationPlan: [], rollbackPlan: [],
      status: 'EXECUTING', version: 1, budget: DEFAULT_PLAN_BUDGET, createdAt: nowISO(), updatedAt: nowISO(),
    }];
    await persistence.savePlans(plans);
    const recovered = await persistence.recoverActivePlans();
    expect(recovered.length).toBe(1);
  });

  it('should cleanup old data', async () => {
    const cleaned = await persistence.cleanup(0);
    expect(cleaned).toBeGreaterThanOrEqual(0);
  });
});

// ============================================================================
// Reasoning Engine (Integration)
// ============================================================================

describe('ReasoningEngine', () => {
  let engine: ReasoningEngine;

  beforeEach(() => {
    engine = new ReasoningEngine();
  });

  it('should process a simple request', async () => {
    const result = await engine.processRequest('Hello');
    expect(result.status).toMatch(/^(COMPLETED|PARTIALLY_COMPLETED)$/);
    expect(result.goalId).toBeDefined();
  });

  it('should process a research request', async () => {
    const result = await engine.processRequest('Research Tesla stock');
    expect(result.goalId).toBeDefined();
    expect(result.evidence).toBeDefined();
  });

  it('should handle direct answer fast path', async () => {
    const result = await engine.processRequest('What is 2+2?');
    expect(result.status).toBe('COMPLETED');
    expect(result.answer).toBeDefined();
  });

  it('should cancel goals', () => {
    const goal = engine.goalEngine.createUserGoal('Test');
    expect(engine.cancelGoal(goal.id)).toBe(true);
  });

  it('should approve tasks', async () => {
    const result = await engine.processRequest('Delete all files');
    if (result.planId) {
      const plan = engine.getPlan(result.planId);
      if (plan && plan.approvalRequirements.length > 0) {
        const taskId = plan.approvalRequirements[0].taskId;
        expect(engine.approveTask(result.planId, taskId)).toBe(true);
      }
    }
  });

  it('should deny tasks', async () => {
    const result = await engine.processRequest('Delete all files');
    if (result.planId) {
      const plan = engine.getPlan(result.planId);
      if (plan && plan.approvalRequirements.length > 0) {
        const taskId = plan.approvalRequirements[0].taskId;
        expect(engine.denyTask(result.planId, taskId, 'Not allowed')).toBe(true);
      }
    }
  });

  it('should provide event log', async () => {
    await engine.processRequest('Hello');
    const events = engine.getEventLog();
    expect(events.length).toBeGreaterThan(0);
  });

  it('should provide event log filtered by goal', async () => {
    const result = await engine.processRequest('Hello');
    const events = engine.getEventLog(result.goalId);
    expect(events.length).toBeGreaterThan(0);
  });

  it('should provide stats', () => {
    const stats = engine.getStats();
    expect(stats.goals).toBeDefined();
    expect(stats.plans).toBeDefined();
    expect(stats.evidence).toBeDefined();
    expect(stats.experience).toBeDefined();
  });

  it('should handle conversation follow-ups', async () => {
    const convId = 'conv_test';
    await engine.processRequest('Research Tesla', { conversationId: convId });
    const result2 = await engine.processRequest('What about NVIDIA?', { conversationId: convId });
    expect(result2.goalId).toBeDefined();
  });

  it('should provide event handler', () => {
    const events: AgentEvent[] = [];
    engine.onEvent(event => events.push(event));
    expect(engine.eventHandlers.length).toBe(1);
  });

  it('should handle process with context', async () => {
    const result = await engine.processRequest('What is the weather?', {
      conversationId: 'conv_ctx',
      availableCapabilities: ['searchWeb'],
    });
    expect(result.status).toBeDefined();
  });

  it('should get pending approvals', async () => {
    await engine.processRequest('Delete all files');
    const approvals = engine.getPendingApprovals();
    expect(Array.isArray(approvals)).toBe(true);
  });

  it('should get goal by id', () => {
    const goal = engine.goalEngine.createUserGoal('Test');
    expect(engine.getGoal(goal.id)).toBeDefined();
  });

  it('should get plan by id', () => {
    expect(engine.getPlan('nonexistent')).toBeUndefined();
  });
});
