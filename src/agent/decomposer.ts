// ============================================================================
// MYRAA Goal Decomposer — Goal → Tasks/Subtasks with Dependencies
// ============================================================================

import type {
  Goal, StructuredIntent, PlanTask, TaskType, RiskLevel, Reversibility,
  EvidenceRequirement, EvidenceSource, AutonomyPolicy, RetryPolicy,
} from './contracts';
import { generateAgentId, DEFAULT_RETRY_POLICY } from './contracts';

// ============================================================================
// Decomposer
// ============================================================================

export class GoalDecomposer {
  decompose(goal: Goal): PlanTask[] {
    const intent = goal.normalizedIntent;
    if (!intent) {
      return [this.createSingleTask(goal, 'INFORMATION_GATHER', goal.userRequest, [])];
    }

    switch (intent.goalType) {
      case 'QUESTION':
        return this.decomposeQuestion(goal, intent);
      case 'RESEARCH':
        return this.decomposeResearch(goal, intent);
      case 'DECISION':
        return this.decomposeDecision(goal, intent);
      case 'COMPARISON':
        return this.decomposeComparison(goal, intent);
      case 'ACTION':
        return this.decomposeAction(goal, intent);
      case 'MULTI_STEP_TASK':
        return this.decomposeMultiStep(goal, intent);
      case 'TROUBLESHOOTING':
        return this.decomposeTroubleshooting(goal, intent);
      case 'ANALYSIS':
        return this.decomposeAnalysis(goal, intent);
      case 'MONITORING':
        return this.decomposeMonitoring(goal, intent);
      case 'INFORMATION_GATHERING':
        return this.decomposeInformationGathering(goal, intent);
      case 'DESIGN':
        return this.decomposeDesign(goal, intent);
      case 'SYSTEM_OPERATION':
        return this.decomposeSystemOperation(goal, intent);
      case 'TRADING_DECISION':
        return this.decomposeTradingDecision(goal, intent);
      default:
        return this.decomposeQuestion(goal, intent);
    }
  }

  private decomposeQuestion(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];

    // If simple + no external data needed → direct answer
    if (intent.complexity === 'TRIVIAL' || intent.complexity === 'SIMPLE') {
      if (!intent.requiresExternalData) {
        tasks.push(this.createTask(goal, 'SYNTHESIS', 'Formulate answer', [], {
          requiredEvidence: [],
          risk: 'LOW',
        }));
        return tasks;
      }
    }

    // Gather evidence if external data needed
    if (intent.requiresExternalData) {
      const evidenceTask = this.createTask(goal, 'INFORMATION_GATHER', 'Gather relevant information', [], {
        requiredEvidence: this.buildEvidenceRequirements(goal, intent),
        risk: 'LOW',
      });
      tasks.push(evidenceTask);
    }

    tasks.push(this.createTask(goal, 'SYNTHESIS', 'Synthesize answer from evidence',
      [tasks[tasks.length - 1]?.taskId].filter(Boolean) as string[], {
      requiredEvidence: [],
      risk: 'LOW',
    }));

    return tasks;
  }

  private decomposeResearch(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const gatherTask = this.createTask(goal, 'RESEARCH', 'Research topic from multiple sources', [], {
      requiredEvidence: this.buildEvidenceRequirements(goal, intent),
      risk: 'LOW',
    });
    const synthesizeTask = this.createTask(goal, 'SYNTHESIS', 'Synthesize research findings', [gatherTask.taskId], {
      requiredEvidence: [],
      risk: 'LOW',
    });
    return [gatherTask, synthesizeTask];
  }

  private decomposeDecision(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];
    const entityCount = intent.entities.filter(e => e.entityType === 'COMPANY' || e.entityType === 'MARKET').length;

    // Gather evidence for each entity/option
    for (const entity of intent.entities) {
      const gatherTask = this.createTask(goal, 'INFORMATION_GATHER',
        `Gather information about ${entity.name}`, [], {
        requiredEvidence: [{
          type: 'WORLD_INTELLIGENCE' as EvidenceSource,
          description: `Current state and recent events for ${entity.name}`,
          freshness: 'FRESH',
          minSources: 2,
          domains: intent.domainHints,
        }],
        risk: 'LOW',
        inputs: { entityName: entity.name, entityType: entity.entityType },
      });
      tasks.push(gatherTask);
    }

    // If no entities, gather general info
    if (tasks.length === 0) {
      tasks.push(this.createTask(goal, 'INFORMATION_GATHER', 'Gather relevant context', [], {
        requiredEvidence: this.buildEvidenceRequirements(goal, intent),
        risk: 'LOW',
      }));
    }

    const taskIds = tasks.map(t => t.taskId);

    const decideTask = this.createTask(goal, 'DECISION', 'Evaluate options and decide',
      taskIds, {
      requiredEvidence: [],
      risk: goal.riskLevel,
      autonomyPolicy: goal.executionPolicy,
    });

    return [...tasks, decideTask];
  }

  private decomposeComparison(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];
    const entities = intent.entities.length > 0 ? intent.entities : [
      { name: 'Option A', entityType: 'OTHER', role: 'SUBJECT', confidence: 0.5 },
      { name: 'Option B', entityType: 'OTHER', role: 'SUBJECT', confidence: 0.5 },
    ];

    for (const entity of entities) {
      const gatherTask = this.createTask(goal, 'INFORMATION_GATHER',
        `Research ${entity.name}`, [], {
        requiredEvidence: [{
          type: 'WORLD_INTELLIGENCE' as EvidenceSource,
          description: `Comprehensive data on ${entity.name}`,
          freshness: 'FRESH',
          minSources: 2,
          domains: intent.domainHints,
        }],
        risk: 'LOW',
        inputs: { entityName: entity.name },
      });
      tasks.push(gatherTask);
    }

    const taskIds = tasks.map(t => t.taskId);
    const compareTask = this.createTask(goal, 'REASONING', 'Compare options across criteria', taskIds, {
      requiredEvidence: [],
      risk: 'LOW',
    });
    return [...tasks, compareTask];
  }

  private decomposeAction(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];
    const actionType: TaskType = 'ACTION';

    // Safety check first if high risk
    if (goal.riskLevel !== 'LOW') {
      tasks.push(this.createTask(goal, 'VERIFICATION', 'Verify prerequisites and safety', [], {
        requiredEvidence: [],
        risk: 'LOW',
        inputs: { action: goal.userRequest },
      }));
    }

    // Gather context if needed
    if (intent.requiresExternalData) {
      const contextTask = this.createTask(goal, 'INFORMATION_GATHER', 'Gather context for action', [], {
        requiredEvidence: this.buildEvidenceRequirements(goal, intent),
        risk: 'LOW',
      });
      tasks.push(contextTask);
    }

    const deps = tasks.map(t => t.taskId);
    const actionTask = this.createTask(goal, actionType, `Execute: ${goal.objective}`, deps, {
      requiredEvidence: [],
      risk: goal.riskLevel,
      autonomyPolicy: goal.executionPolicy,
      verificationPolicy: {
        strategies: ['STATE_CHECK'],
        required: true,
        timeout: 10_000,
        successCriteria: goal.successCriteria,
      },
    });
    tasks.push(actionTask);

    return tasks;
  }

  private decomposeMultiStep(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];
    const steps = this.inferStepsFromRequest(goal.userRequest);

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const deps = i > 0 ? [tasks[i - 1].taskId] : [];
      const taskType: TaskType = this.inferTaskTypeForStep(step);
      tasks.push(this.createTask(goal, taskType, step, deps, {
        requiredEvidence: taskType === 'INFORMATION_GATHER' ? this.buildEvidenceRequirements(goal, intent) : [],
        risk: 'LOW',
      }));
    }
    return tasks;
  }

  private decomposeTroubleshooting(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const observeTask = this.createTask(goal, 'INFORMATION_GATHER', 'Observe symptoms and gather diagnostic data', [], {
      requiredEvidence: this.buildEvidenceRequirements(goal, intent),
      risk: 'LOW',
    });
    const diagnoseTask = this.createTask(goal, 'REASONING', 'Analyze symptoms and form hypotheses', [observeTask.taskId], {
      requiredEvidence: [],
      risk: 'LOW',
    });
    const recommendTask = this.createTask(goal, 'SYNTHESIS', 'Recommend solution', [diagnoseTask.taskId], {
      requiredEvidence: [],
      risk: 'LOW',
    });
    return [observeTask, diagnoseTask, recommendTask];
  }

  private decomposeAnalysis(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const gatherTask = this.createTask(goal, 'INFORMATION_GATHER', 'Collect relevant data', [], {
      requiredEvidence: this.buildEvidenceRequirements(goal, intent),
      risk: 'LOW',
    });
    const analyzeTask = this.createTask(goal, 'REASONING', 'Analyze data and form conclusions', [gatherTask.taskId], {
      requiredEvidence: [],
      risk: 'LOW',
    });
    return [gatherTask, analyzeTask];
  }

  private decomposeMonitoring(goal: Goal, intent: StructuredIntent): PlanTask[] {
    return [this.createTask(goal, 'VERIFICATION', `Set up monitoring: ${goal.objective}`, [], {
      requiredEvidence: [],
      risk: 'LOW',
      inputs: { monitoring: true, topics: intent.topics },
    })];
  }

  private decomposeInformationGathering(goal: Goal, intent: StructuredIntent): PlanTask[] {
    return [this.createTask(goal, 'INFORMATION_GATHER', goal.objective, [], {
      requiredEvidence: this.buildEvidenceRequirements(goal, intent),
      risk: 'LOW',
    })];
  }

  private decomposeDesign(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];
    const gatherTask = this.createTask(goal, 'INFORMATION_GATHER', 'Gather design requirements and constraints', [], {
      requiredEvidence: this.buildEvidenceRequirements(goal, intent),
      risk: 'LOW',
    });
    tasks.push(gatherTask);

    const designTask = this.createTask(goal, 'ACTION', `Design: ${goal.objective}`, [gatherTask.taskId], {
      requiredEvidence: [],
      risk: goal.riskLevel,
      autonomyPolicy: 'MODERATE_ACTION',
      verificationPolicy: { strategies: ['STATE_CHECK'], required: true, timeout: 30_000, successCriteria: ['Design created'] },
    });
    tasks.push(designTask);

    const verifyTask = this.createTask(goal, 'VERIFICATION', 'Verify design meets requirements', [designTask.taskId], {
      requiredEvidence: [],
      risk: 'LOW',
    });
    tasks.push(verifyTask);

    return tasks;
  }

  private decomposeSystemOperation(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];

    const gatherTask = this.createTask(goal, 'INFORMATION_GATHER', 'Gather system information', [], {
      requiredEvidence: this.buildEvidenceRequirements(goal, intent),
      risk: 'LOW',
    });
    tasks.push(gatherTask);

    const actionTask = this.createTask(goal, 'ACTION', `Execute: ${goal.objective}`, [gatherTask.taskId], {
      requiredEvidence: [],
      risk: goal.riskLevel,
      autonomyPolicy: 'SAFE_ACTION',
      verificationPolicy: { strategies: ['STATE_CHECK'], required: true, timeout: 10_000, successCriteria: ['Operation completed'] },
    });
    tasks.push(actionTask);

    return tasks;
  }

  private decomposeTradingDecision(goal: Goal, intent: StructuredIntent): PlanTask[] {
    const tasks: PlanTask[] = [];

    const gatherTask = this.createTask(goal, 'INFORMATION_GATHER', 'Gather market data and analysis', [], {
      requiredEvidence: this.buildEvidenceRequirements(goal, intent),
      risk: 'LOW',
    });
    tasks.push(gatherTask);

    const analyzeTask = this.createTask(goal, 'REASONING', 'Analyze technical and fundamental indicators', [gatherTask.taskId], {
      requiredEvidence: [],
      risk: 'LOW',
    });
    tasks.push(analyzeTask);

    const decisionTask = this.createTask(goal, 'SYNTHESIS', 'Provide trading recommendation', [analyzeTask.taskId], {
      requiredEvidence: [],
      risk: 'LOW',
    });
    tasks.push(decisionTask);

    return tasks;
  }

  // --- Helpers ---

  private createTask(
    goal: Goal,
    type: TaskType,
    description: string,
    dependencies: string[],
    options: {
      requiredEvidence?: EvidenceRequirement[];
      risk?: RiskLevel;
      autonomyPolicy?: AutonomyPolicy;
      verificationPolicy?: PlanTask['verificationPolicy'];
      inputs?: Record<string, unknown>;
    } = {},
  ): PlanTask {
    return {
      taskId: generateAgentId('task'),
      goalId: goal.id,
      title: description,
      description,
      type,
      dependencies,
      requiredCapabilities: [],
      requiredEvidence: options.requiredEvidence || [],
      inputs: options.inputs || {},
      expectedOutcome: `${description} completed successfully`,
      risk: options.risk || 'LOW',
      reversibility: 'REVERSIBLE',
      status: 'PENDING',
      priority: 5,
      timeout: 30_000,
      retryPolicy: DEFAULT_RETRY_POLICY,
      verificationPolicy: options.verificationPolicy,
      autonomyPolicy: options.autonomyPolicy || 'READ_ONLY',
      retryCount: 0,
      sideEffects: [],
      metadata: {},
    };
  }

  private createSingleTask(goal: Goal, type: TaskType, description: string, deps: string[]): PlanTask {
    return this.createTask(goal, type, description, deps);
  }

  private buildEvidenceRequirements(goal: Goal, intent: StructuredIntent): EvidenceRequirement[] {
    const reqs: EvidenceRequirement[] = [];
    if (intent.requiresExternalData) {
      reqs.push({
        type: 'WORLD_INTELLIGENCE',
        description: 'Current world state and recent events',
        freshness: 'FRESH',
        minSources: 1,
        domains: intent.domainHints,
      });
    }
    if (intent.requiresDecision) {
      reqs.push({
        type: 'CAPABILITY',
        description: 'Relevant capability data',
        freshness: 'FRESH',
        minSources: 1,
        domains: intent.domainHints,
      });
    }
    return reqs;
  }

  private inferStepsFromRequest(userRequest: string): string[] {
    const lower = userRequest.toLowerCase();
    const steps: string[] = [];
    const parts = userRequest.split(/\b(and|then|also|plus|additionally|after that|followed by)\b/i);
    for (const part of parts) {
      const trimmed = part.trim();
      if (trimmed.length > 3 && !/^(and|then|also|plus|additionally|after|followed by)$/i.test(trimmed)) {
        steps.push(trimmed);
      }
    }
    if (steps.length <= 1) {
      steps.length = 0;
      steps.push('Gather required information');
      steps.push('Process and analyze');
      steps.push('Deliver result');
    }
    return steps;
  }

  private inferTaskTypeForStep(step: string): TaskType {
    const lower = step.toLowerCase();
    if (/\b(find|search|look|get|fetch|gather|collect|research)\b/.test(lower)) return 'INFORMATION_GATHER';
    if (/\b(analyze|compare|evaluate|assess)\b/.test(lower)) return 'REASONING';
    if (/\b(create|build|write|generate|make)\b/.test(lower)) return 'ACTION';
    if (/\b(verify|check|validate|confirm)\b/.test(lower)) return 'VERIFICATION';
    return 'INFORMATION_GATHER';
  }
}
