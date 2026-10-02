// ============================================================================
// MYRAA LLM-Assisted Extraction — Validated Extraction Behind Schema
// ============================================================================

import type { EntityType, WorldEventType, ImportanceLevel, ObservationStatus, KnowledgeLevel } from './contracts';
import { nowISO } from './contracts';
import { MODEL_ROUTES } from '../core/request_router';

// ============================================================================
// Extraction Candidates (LLM proposals before validation)
// ============================================================================

export interface ExtractedEntity {
  readonly name: string;
  readonly entityType: EntityType;
  readonly aliases?: readonly string[];
  readonly confidence: number;
}

export interface ExtractedFact {
  readonly subjectName: string;
  readonly predicate: string;
  readonly objectValue?: string | number | boolean;
  readonly objectEntityName?: string;
  readonly confidence: number;
  readonly observationStatus: ObservationStatus;
  readonly knowledgeLevel: KnowledgeLevel;
}

export interface ExtractedEvent {
  readonly type: WorldEventType;
  readonly title: string;
  readonly summary: string;
  readonly entityNames: readonly string[];
  readonly importance: ImportanceLevel;
  readonly confidence: number;
  readonly topics: readonly string[];
  readonly timestamp?: string;
}

export interface ExtractionResult {
  readonly entities: readonly ExtractedEntity[];
  readonly facts: readonly ExtractedFact[];
  readonly events: readonly ExtractedEvent[];
  readonly topics: readonly string[];
  readonly rawLlmOutput: string;
  readonly validated: boolean;
  readonly validationErrors: readonly string[];
  readonly extractionTimeMs: number;
}

// ============================================================================
// Schema Validators
// ============================================================================

const VALID_ENTITY_TYPES = new Set([
  'PERSON', 'COMPANY', 'COUNTRY', 'CITY', 'PLACE', 'PRODUCT',
  'ORGANIZATION', 'EVENT', 'MARKET', 'ASSET', 'CURRENCY',
  'SPORTS_TEAM', 'SPORTS_EVENT', 'SCIENTIFIC_OBJECT', 'SPACE_OBJECT',
  'TECHNOLOGY', 'PUBLICATION', 'REGULATION', 'WEATHER_SYSTEM', 'OTHER',
]);

const VALID_EVENT_TYPES = new Set([
  'NEWS', 'MARKET_MOVE', 'EARNINGS', 'POLICY_CHANGE', 'PRODUCT_RELEASE',
  'SCIENTIFIC_DISCOVERY', 'WEATHER_EVENT', 'NATURAL_EVENT', 'SPORTS_RESULT',
  'POLITICAL_EVENT', 'COMPANY_EVENT', 'TECH_EVENT', 'FINANCIAL_DATA',
  'ECONOMIC_RELEASE', 'CENTRAL_BANK', 'GEOPOLITICAL', 'ENVIRONMENT',
  'TRANSPORTATION', 'OTHER',
]);

const VALID_IMPORTANCE = new Set(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']);

function validateEntity(e: ExtractedEntity): string[] {
  const errors: string[] = [];
  if (!e.name || e.name.trim().length === 0) errors.push('Entity name is empty');
  if (!VALID_ENTITY_TYPES.has(e.entityType)) errors.push(`Invalid entity type: ${e.entityType}`);
  if (e.confidence < 0 || e.confidence > 1) errors.push(`Invalid confidence: ${e.confidence}`);
  if (e.name && e.name.length > 200) errors.push('Entity name too long');
  return errors;
}

function validateFact(f: ExtractedFact): string[] {
  const errors: string[] = [];
  if (!f.subjectName || f.subjectName.trim().length === 0) errors.push('Fact subject is empty');
  if (!f.predicate || f.predicate.trim().length === 0) errors.push('Fact predicate is empty');
  if (f.confidence < 0 || f.confidence > 1) errors.push(`Invalid confidence: ${f.confidence}`);
  if (!['OBSERVED', 'DERIVED', 'INFERRED', 'UNKNOWN'].includes(f.observationStatus)) {
    errors.push(`Invalid observation status: ${f.observationStatus}`);
  }
  return errors;
}

function validateEvent(e: ExtractedEvent): string[] {
  const errors: string[] = [];
  if (!e.title || e.title.trim().length === 0) errors.push('Event title is empty');
  if (!VALID_EVENT_TYPES.has(e.type)) errors.push(`Invalid event type: ${e.type}`);
  if (!VALID_IMPORTANCE.has(e.importance)) errors.push(`Invalid importance: ${e.importance}`);
  if (e.confidence < 0 || e.confidence > 1) errors.push(`Invalid confidence: ${e.confidence}`);
  if (e.title && e.title.length > 500) errors.push('Event title too long');
  if (e.summary && e.summary.length > 2000) errors.push('Event summary too long');
  return errors;
}

// ============================================================================
// LLM Extraction Engine (Rule-based with optional LLM enhancement)
// ============================================================================

export class LlmExtractionEngine {
  private knownEntities: Map<string, EntityType> = new Map();
  private ollamaUrl: string;

  constructor(ollamaUrl = 'http://127.0.0.1:11434') {
    this.ollamaUrl = ollamaUrl;
    this.initKnownEntities();
  }

  private initKnownEntities(): void {
    const known: [string, EntityType][] = [
      ['Apple', 'COMPANY'], ['Google', 'COMPANY'], ['Microsoft', 'COMPANY'],
      ['Amazon', 'COMPANY'], ['NVIDIA', 'COMPANY'], ['Tesla', 'COMPANY'],
      ['OpenAI', 'COMPANY'], ['Meta', 'COMPANY'], ['Samsung', 'COMPANY'],
      ['IBM', 'COMPANY'], ['Intel', 'COMPANY'], ['AMD', 'COMPANY'],
      ['India', 'COUNTRY'], ['China', 'COUNTRY'], ['USA', 'COUNTRY'],
      ['United States', 'COUNTRY'], ['United Kingdom', 'COUNTRY'],
      ['Japan', 'COUNTRY'], ['Germany', 'COUNTRY'], ['France', 'COUNTRY'],
      ['NASA', 'ORGANIZATION'], ['WHO', 'ORGANIZATION'], ['UN', 'ORGANIZATION'],
      ['EU', 'ORGANIZATION'], ['IMF', 'ORGANIZATION'],
      ['Elon Musk', 'PERSON'], ['Sam Altman', 'PERSON'],
      ['Sundar Pichai', 'PERSON'], ['Tim Cook', 'PERSON'],
      ['Satya Nadella', 'PERSON'], ['Jensen Huang', 'PERSON'],
      ['Bitcoin', 'CURRENCY'], ['Ethereum', 'CURRENCY'],
      ['NIFTY', 'MARKET'], ['Sensex', 'MARKET'],
      ['S&P 500', 'MARKET'], ['Dow Jones', 'MARKET'],
      ['NASDAQ', 'MARKET'], ['Nasdaq', 'MARKET'],
    ];
    for (const [name, type] of known) {
      this.knownEntities.set(name.toLowerCase(), type);
    }
  }

  // --- Rule-based extraction (fast, always available) ---

  extractFromText(text: string, sourceId: string): ExtractionResult {
    const start = Date.now();
    const entities: ExtractedEntity[] = [];
    const facts: ExtractedFact[] = [];
    const events: ExtractedEvent[] = [];
    const topics: string[] = [];
    const validationErrors: string[] = [];

    // Entity extraction (known entity matching)
    for (const [nameLower, entityType] of this.knownEntities) {
      if (text.toLowerCase().includes(nameLower)) {
        const originalName = text.match(new RegExp(`\\b${nameLower}\\b`, 'i'))?.[0] || nameLower;
        entities.push({
          name: originalName,
          entityType,
          confidence: 0.8,
        });
      }
    }

    // Topic extraction
    const topicPatterns: [RegExp, string][] = [
      [/artificial intelligence|ai\b|machine learning/i, 'artificial-intelligence'],
      [/climate|global warming|carbon/i, 'climate'],
      [/crypto|bitcoin|ethereum|blockchain/i, 'cryptocurrency'],
      [/trade war|tariff|sanction/i, 'trade'],
      [/pandemic|covid|virus|health/i, 'health'],
      [/space|nasa|spacex|rocket/i, 'space'],
      [/energy|oil|solar|renewable/i, 'energy'],
      [/election|vote|democracy/i, 'politics'],
      [/stock|market|trading|invest/i, 'finance'],
      [/startup|venture|funding/i, 'startups'],
    ];
    for (const [pattern, topic] of topicPatterns) {
      if (pattern.test(text)) topics.push(topic);
    }

    // Event extraction (from headline patterns)
    const lines = text.split('\n').filter(l => l.trim().length > 10);
    for (const line of lines.slice(0, 5)) {
      const eventType = this.inferEventType(line);
      const importance = this.inferImportance(line);
      if (line.length > 20) {
        events.push({
          type: eventType,
          title: line.slice(0, 200),
          summary: line,
          entityNames: entities.map(e => e.name),
          importance,
          confidence: 0.6,
          topics,
        });
      }
    }

    // Simple fact extraction
    const factPatterns = [
      { regex: /(\w+)\s+(?:is|are)\s+(?:the\s+)?(?:CEO|chief executive)\s+(?:of\s+)?(\w[\w\s]*?)(?:\.|,|$)/i, predicate: 'CEO' },
      { regex: /(\w+)\s+(?:reported|announced)\s+(?:revenue|earnings)\s+(?:of\s+)?(\$?[\d,.]+\s*(?:billion|million|B|M)?)/i, predicate: 'revenue' },
      { regex: /(\w+)\s+(?:stock|shares)\s+(?:fell|dropped|declined|rose|jumped|surged)\s+(\d+%?)/i, predicate: 'stock_movement' },
    ];
    for (const { regex, predicate } of factPatterns) {
      const match = text.match(regex);
      if (match) {
        facts.push({
          subjectName: match[1],
          predicate,
          objectValue: match[2],
          confidence: 0.7,
          observationStatus: 'OBSERVED',
          knowledgeLevel: 'CURRENT',
        });
      }
    }

    // Validate all extracted items
    for (const e of entities) validationErrors.push(...validateEntity(e));
    for (const f of facts) validationErrors.push(...validateFact(f));
    for (const e of events) validationErrors.push(...validateEvent(e));

    return {
      entities: entities.filter(e => validateEntity(e).length === 0),
      facts: facts.filter(f => validateFact(f).length === 0),
      events: events.filter(e => validateEvent(e).length === 0),
      topics,
      rawLlmOutput: '',
      validated: validationErrors.length === 0,
      validationErrors,
      extractionTimeMs: Date.now() - start,
    };
  }

  // --- LLM-enhanced extraction (optional, uses Ollama) ---

  async extractWithLlm(text: string, sourceId: string): Promise<ExtractionResult> {
    const start = Date.now();
    // First do rule-based extraction
    const ruleBased = this.extractFromText(text, sourceId);
    // Try LLM enhancement
    try {
      const prompt = `Extract entities, facts, and events from this text. Return JSON only.
Text: ${text.slice(0, 2000)}

Return format:
{
  "entities": [{"name": "...", "type": "PERSON|COMPANY|COUNTRY|...", "confidence": 0.0-1.0}],
  "facts": [{"subject": "...", "predicate": "...", "value": "...", "confidence": 0.0-1.0}],
  "events": [{"type": "NEWS|TECH_EVENT|...", "title": "...", "summary": "...", "importance": "HIGH|MEDIUM|LOW", "confidence": 0.0-1.0}],
  "topics": ["topic1", "topic2"]
}`;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 15_000);
      const res = await fetch(`${this.ollamaUrl}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          // FIX: was 'qwen3:8b' — never installed on target hardware, so this
          // LLM enhancement silently degraded to rule-based every time.
          // Now sourced from the single routing table (fast local model).
          model: MODEL_ROUTES.FAST,
          prompt,
          stream: false,
          options: { temperature: 0.1, num_predict: 1000 },
        }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      const data = await res.json() as Record<string, unknown>;
      const response = String(data.response || '');
      // Parse JSON from response
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]) as Record<string, unknown>;
        // Validate and merge LLM results
        const llmEntities = (parsed.entities || []) as ExtractedEntity[];
        const llmFacts = (parsed.facts || []) as ExtractedFact[];
        const llmEvents = (parsed.events || []) as ExtractedEvent[];
        const llmTopics = (parsed.topics || []) as string[];
        // Merge: prefer LLM if valid, fallback to rule-based
        const mergedEntities = llmEntities.filter(e => validateEntity(e).length === 0).length > 0
          ? llmEntities.filter(e => validateEntity(e).length === 0)
          : ruleBased.entities;
        const mergedFacts = llmFacts.filter(f => validateFact(f).length === 0).length > 0
          ? llmFacts.filter(f => validateFact(f).length === 0)
          : ruleBased.facts;
        const mergedEvents = llmEvents.filter(e => validateEvent(e).length === 0).length > 0
          ? llmEvents.filter(e => validateEvent(e).length === 0)
          : ruleBased.events;
        return {
          entities: mergedEntities,
          facts: mergedFacts,
          events: mergedEvents,
          topics: [...new Set([...ruleBased.topics, ...llmTopics])],
          rawLlmOutput: response.slice(0, 2000),
          validated: true,
          validationErrors: [],
          extractionTimeMs: Date.now() - start,
        };
      }
    } catch {
      // LLM unavailable, return rule-based results
    }
    return { ...ruleBased, extractionTimeMs: Date.now() - start };
  }

  private inferEventType(text: string): WorldEventType {
    const lower = text.toLowerCase();
    if (lower.includes('market') || lower.includes('stock') || lower.includes('trading')) return 'MARKET_MOVE';
    if (lower.includes('earning') || lower.includes('revenue') || lower.includes('profit')) return 'EARNINGS';
    if (lower.includes('ai ') || lower.includes('openai') || lower.includes('nvidia') || lower.includes('tech')) return 'TECH_EVENT';
    if (lower.includes('weather') || lower.includes('storm') || lower.includes('cyclone')) return 'WEATHER_EVENT';
    if (lower.includes('politic') || lower.includes('election') || lower.includes('parliament')) return 'POLITICAL_EVENT';
    if (lower.includes('science') || lower.includes('research') || lower.includes('discovery')) return 'SCIENTIFIC_DISCOVERY';
    if (lower.includes('policy') || lower.includes('regulation') || lower.includes('ban')) return 'POLICY_CHANGE';
    if (lower.includes('economic') || lower.includes('gdp') || lower.includes('inflation')) return 'ECONOMIC_RELEASE';
    return 'NEWS';
  }

  private inferImportance(text: string): ImportanceLevel {
    const lower = text.toLowerCase();
    if (lower.includes('breaking') || lower.includes('urgent') || lower.includes('critical')) return 'CRITICAL';
    if (lower.includes('major') || lower.includes('significant') || lower.includes('important')) return 'HIGH';
    if (lower.includes('minor') || lower.includes('trivial')) return 'LOW';
    return 'MEDIUM';
  }
}
