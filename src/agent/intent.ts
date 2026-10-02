// ============================================================================
// MYRAA Intent Understanding — NL → StructuredIntent
// ============================================================================

import type { StructuredIntent, IntentEntity, GoalType, TaskComplexity } from './contracts';

// ============================================================================
// Intent Classifier (deterministic + pattern-based)
// ============================================================================

export class IntentUnderstanding {
  private entityPatterns: [RegExp, string, string][] = [
    [/\b(NVIDIA|AMD|Intel|Apple|Google|Microsoft|Tesla|Amazon|Meta|Samsung)\b/gi, 'COMPANY', 'SUBJECT'],
    [/\b(India|China|USA|UK|Japan|Germany|France|Russia)\b/gi, 'COUNTRY', 'LOCATION'],
    [/\b(NIFTY|Sensex|S&P\s*500|Dow\s*Jones|NASDAQ)\b/gi, 'MARKET', 'CONTEXT'],
    [/\b(Bitcoin|Ethereum|BTC|ETH|USDT)\b/gi, 'CRYPTO', 'ASSET'],
    [/\bweather\b/gi, 'TOPIC', 'DOMAIN'],
    [/\b(temperature|rain|wind|storm)\b/gi, 'WEATHER', 'DOMAIN'],
  ];

  classifyIntent(userRequest: string): StructuredIntent {
    const lower = userRequest.toLowerCase();
    const goalType = this.classifyGoalType(lower, userRequest);
    const complexity = this.classifyComplexity(lower, userRequest);
    const entities = this.extractEntities(userRequest);
    const topics = this.extractTopics(lower);
    const actions = this.extractActions(lower);
    const questions = this.extractQuestions(userRequest);
    const temporalScope = this.classifyTemporalScope(lower);
    const domainHints = this.inferDomains(lower, topics);
    const requiresExternalData = this.needsExternalData(lower, goalType);
    const requiresAction = this.needsAction(lower, goalType, actions);
    const requiresDecision = this.needsDecision(lower, goalType);
    const ambiguityScore = this.measureAmbiguity(lower, entities, questions);
    const ambiguousFields = this.identifyAmbiguity(lower, entities);

    return {
      goalType,
      complexity,
      entities,
      topics,
      actions,
      questions,
      temporalScope,
      domainHints,
      requiresExternalData,
      requiresAction,
      requiresDecision,
      ambiguityScore,
      ambiguousFields,
    };
  }

  private classifyGoalType(lower: string, _raw: string): GoalType {
    if (/^(compare|vs|versus|better|worse|which|difference)/.test(lower)) return 'COMPARISON';
    if (/\b(why|reason|cause|because)\b/.test(lower)) return 'ANALYSIS';
    if (/\b(how to|how do|steps to|guide|tutorial)\b/.test(lower)) return 'MULTI_STEP_TASK';
    if (/\b(create|make|build|generate|write|save|delete|move|rename|open|close|run|execute|install|send)\b/.test(lower)) return 'ACTION';
    if (/\b(research|investigate|find out|look into|explore)\b/.test(lower)) return 'RESEARCH';
    if (/\b(should I|recommend|advice|suggestion|opinion)\b/.test(lower)) return 'DECISION';
    if (/\b(monitor|watch|track|notify|alert|tell me if)\b/.test(lower)) return 'MONITORING';
    if (/\b(optimize|improve|enhance|speed up|reduce)\b/.test(lower)) return 'OPTIMIZATION';
    if (/\b(fix|troubleshoot|debug|error|issue|problem|slow|broken)\b/.test(lower)) return 'TROUBLESHOOTING';
    if (/\b(write|story|poem|creative|imagine|design concept)\b/.test(lower)) return 'CREATIVE';
    if (/\b(summarize|overview|summary|brief)\b/.test(lower)) return 'ANALYSIS';
    if (/\b(compare|price|cost|cheap|expensive|best|top)\b/.test(lower)) return 'COMPARISON';
    if (/\b(design|draw|sketch|model|cad|3d|part|assembly|bearing|housing|bracket)\b/.test(lower)) return 'DESIGN';
    if (/\b(temperature|check|laptop|pc|system info|gpu|cpu|volume|brightness|battery)\b/.test(lower)) return 'SYSTEM_OPERATION';
    if (/\b(buy|sell|trade|stock|nifty|sensex|reliance|tcs|infy)\b/.test(lower) && /\b(should|recommend|advice|opinion|buy|sell)\b/.test(lower)) return 'TRADING_DECISION';
    if (/\b(what is|who is|when did|where is|define)\b/.test(lower)) return 'QUESTION';
    return 'QUESTION';
  }

  private classifyComplexity(lower: string, raw: string): TaskComplexity {
    const wordCount = raw.split(/\s+/).length;
    const hasMultipleClauses = /\b(and|then|also|plus|additionally|after that|followed by)\b/.test(lower);
    const hasComparison = /\b(compare|vs|versus|better|worse|difference)\b/.test(lower);
    const hasResearch = /\b(research|investigate|find out|deep dive)\b/.test(lower);
    const hasAction = /\b(create|build|deploy|execute|run|send)\b/.test(lower);

    if (wordCount <= 5 && !hasMultipleClauses) return 'TRIVIAL';
    if (wordCount <= 12 && !hasComparison && !hasResearch) return 'SIMPLE';
    if (hasMultipleClauses || hasComparison || (hasResearch && hasAction)) return 'COMPLEX';
    if (hasResearch || hasAction || hasMultipleClauses) return 'MEDIUM';
    return 'SIMPLE';
  }

  private extractEntities(text: string): IntentEntity[] {
    const entities: IntentEntity[] = [];
    for (const [pattern, entityType, role] of this.entityPatterns) {
      const matches = text.matchAll(pattern);
      for (const match of matches) {
        entities.push({
          name: match[1],
          entityType,
          role,
          confidence: 0.85,
        });
      }
    }
    return entities;
  }

  private extractTopics(lower: string): string[] {
    const topics: string[] = [];
    const topicMap: [RegExp, string][] = [
      [/\b(weather|temperature|forecast)\b/, 'weather'],
      [/\b(stock|market|trading|invest|portfolio)\b/, 'finance'],
      [/\b(ai|artificial intelligence|machine learning|llm|gpt|openai)\b/, 'artificial-intelligence'],
      [/\b(crypto|bitcoin|ethereum|blockchain)\b/, 'cryptocurrency'],
      [/\b(news|headline|breaking|latest)\b/, 'news'],
      [/\b(code|coding|programming|developer|github)\b/, 'programming'],
      [/\b(travel|flight|hotel|trip|vacation)\b/, 'travel'],
      [/\b(health|medical|doctor|symptom)\b/, 'health'],
      [/\b(energy|oil|solar|renewable)\b/, 'energy'],
      [/\b(climate|environment|pollution|carbon)\b/, 'climate'],
      [/\b(politics|election|government|policy)\b/, 'politics'],
      [/\b(space|nasa|spacex|rocket|mars)\b/, 'space'],
      [/\b(education|study|learn|course|university)\b/, 'education'],
    ];
    for (const [pattern, topic] of topicMap) {
      if (pattern.test(lower)) topics.push(topic);
    }
    return [...new Set(topics)];
  }

  private extractActions(lower: string): string[] {
    const actions: string[] = [];
    const actionPatterns: [RegExp, string][] = [
      [/\b(create|make|build)\b/, 'create'],
      [/\b(delete|remove|destroy)\b/, 'delete'],
      [/\b(move|relocate|transfer)\b/, 'move'],
      [/\b(rename)\b/, 'rename'],
      [/\b(open|launch|start)\b/, 'open'],
      [/\b(close|stop|kill|shutdown)\b/, 'close'],
      [/\b(send|email|message)\b/, 'send'],
      [/\b(search|find|look up|google)\b/, 'search'],
      [/\b(download|install|update)\b/, 'install'],
      [/\b(run|execute|launch)\b/, 'execute'],
      [/\b(save|store|persist)\b/, 'save'],
      [/\b(read|view|show|display|open)\b/, 'view'],
      [/\b(compare|analyze|evaluate)\b/, 'analyze'],
      [/\b(research|investigate)\b/, 'research'],
    ];
    for (const [pattern, action] of actionPatterns) {
      if (pattern.test(lower)) actions.push(action);
    }
    return [...new Set(actions)];
  }

  private extractQuestions(text: string): string[] {
    const questions: string[] = [];
    if (text.includes('?')) {
      questions.push(text.trim());
    }
    const questionStarters = /^(what|who|where|when|why|how|which|can|could|should|would|is|are|do|does|will)\b/i;
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 5);
    for (const s of sentences) {
      if (questionStarters.test(s.trim())) {
        questions.push(s.trim());
      }
    }
    return [...new Set(questions)];
  }

  private classifyTemporalScope(lower: string): StructuredIntent['temporalScope'] {
    const hasCurrent = /\b(now|current|today|right now|latest|recent|just)\b/.test(lower);
    const hasHistorical = /\b(history|past|was|were|last year|ago|historical|previous)\b/.test(lower);
    const hasFuture = /\b(will|tomorrow|next|upcoming|forecast|predict|future)\b/.test(lower);

    if (hasCurrent && hasHistorical) return 'MIXED';
    if (hasFuture) return 'FUTURE';
    if (hasHistorical) return 'HISTORICAL';
    if (hasCurrent) return 'CURRENT';
    return 'CURRENT';
  }

  private inferDomains(lower: string, topics: string[]): string[] {
    const domains = new Set(topics);
    if (/\b(bug|error|crash|slow|fix|debug|troubleshoot)\b/.test(lower)) domains.add('troubleshooting');
    if (/\b(buy|price|cheap|cost|deal|offer)\b/.test(lower)) domains.add('shopping');
    if (/\b(python|javascript|typescript|code|program|function|api)\b/.test(lower)) domains.add('programming');
    return [...domains];
  }

  private needsExternalData(lower: string, goalType: GoalType): boolean {
    if (goalType === 'RESEARCH') return true;
    if (goalType === 'MONITORING') return true;
    if (/\b(news|current|latest|today|weather|stock|price)\b/.test(lower)) return true;
    if (/\b(compare|research|investigate)\b/.test(lower)) return true;
    return false;
  }

  private needsAction(lower: string, goalType: GoalType, actions: string[]): boolean {
    if (goalType === 'ACTION') return true;
    if (goalType === 'DESIGN') return true;
    if (goalType === 'SYSTEM_OPERATION') return true;
    if (goalType === 'MULTI_STEP_TASK') return true;
    if (actions.length > 0) return true;
    if (/\b(create|delete|move|rename|open|close|send|run|execute|install)\b/.test(lower)) return true;
    return false;
  }

  private needsDecision(lower: string, goalType: GoalType): boolean {
    if (goalType === 'DECISION') return true;
    if (goalType === 'COMPARISON') return true;
    if (/\b(should I|recommend|advice|better|worse|which|compare)\b/.test(lower)) return true;
    return false;
  }

  private measureAmbiguity(lower: string, entities: IntentEntity[], questions: string[]): number {
    let score = 0;
    if (entities.length === 0 && lower.split(/\s+/).length > 5) score += 0.2;
    if (questions.length === 0 && /\b(it|that|this|they|them)\b/.test(lower)) score += 0.3;
    if (/\b(something|stuff|things|whatever)\b/.test(lower)) score += 0.3;
    if (lower.split(/\s+/).length < 3) score += 0.1;
    return Math.min(score, 1.0);
  }

  private identifyAmbiguity(lower: string, entities: IntentEntity[]): string[] {
    const fields: string[] = [];
    if (entities.length === 0) fields.push('subject');
    if (!/\?/.test(lower) && !/\b(create|delete|move|find|search|compare)\b/.test(lower)) fields.push('action');
    if (/\b(it|that|this|they|them)\b/.test(lower) && entities.length === 0) fields.push('reference');
    return fields;
  }
}
