// ============================================================================
// MYRAA Evidence Pack — Structured Evidence for Brain Consumption
// ============================================================================

import type { WorldEntity, TemporalFact, WorldEvent, FactProvenance, EventSource, FreshnessClass } from './contracts';
import { nowISO } from './contracts';

export interface EvidenceClaim {
  readonly text: string;
  readonly subject: string;
  readonly predicate: string;
  readonly value: string | number | boolean;
  readonly confidence: number;
  readonly observationStatus: 'OBSERVED' | 'DERIVED' | 'INFERRED' | 'UNKNOWN';
  readonly validFrom?: string;
  readonly validTo?: string;
}

export interface EvidenceSource {
  readonly sourceId: string;
  readonly providerId: string;
  readonly sourceClass: string;
  readonly url?: string;
  readonly title?: string;
  readonly retrievedAt: string;
  readonly publishedAt?: string;
  readonly confidence: number;
  readonly verificationStatus: string;
}

export interface EvidenceContradiction {
  readonly claimA: EvidenceClaim;
  readonly claimB: EvidenceClaim;
  readonly description: string;
}

export interface EvidencePack {
  readonly query: string;
  readonly answer: string;
  readonly claims: readonly EvidenceClaim[];
  readonly supportingSources: readonly EvidenceSource[];
  readonly contradictingSources: readonly EvidenceSource[];
  readonly entities: readonly WorldEntity[];
  readonly events: readonly WorldEvent[];
  readonly facts: readonly TemporalFact[];
  readonly contradictions: readonly EvidenceContradiction[];
  readonly timestamps: {
    readonly queriedAt: string;
    readonly latestDataAt: string;
    readonly oldestDataAt: string;
  };
  readonly freshness: FreshnessClass;
  readonly overallConfidence: number;
  readonly provenanceChain: readonly string[];
  readonly metadata: Record<string, unknown>;
}

// ============================================================================
// Evidence Pack Builder
// ============================================================================

export class EvidencePackBuilder {
  private claims: EvidenceClaim[] = [];
  private supportingSources: EvidenceSource[] = [];
  private contradictingSources: EvidenceSource[] = [];
  private entities: WorldEntity[] = [];
  private events: WorldEvent[] = [];
  private facts: TemporalFact[] = [];
  private contradictions: EvidenceContradiction[] = [];
  private latestDataAt = '';
  private oldestDataAt = '';
  private query = '';

  setQuery(query: string): this {
    this.query = query;
    return this;
  }

  addEntity(entity: WorldEntity): this {
    this.entities.push(entity);
    return this;
  }

  addEvent(event: WorldEvent): this {
    this.events.push(event);
    // Track timestamps
    if (event.timestamp > this.latestDataAt || !this.latestDataAt) {
      this.latestDataAt = event.timestamp;
    }
    if (!this.oldestDataAt || event.timestamp < this.oldestDataAt) {
      this.oldestDataAt = event.timestamp;
    }
    // Add event sources
    for (const source of event.sources) {
      this.addSource(source, event.confidence);
    }
    return this;
  }

  addFact(fact: TemporalFact): this {
    this.facts.push(fact);
    // Track timestamps
    if (fact.validFrom > this.latestDataAt || !this.latestDataAt) {
      this.latestDataAt = fact.validFrom;
    }
    if (fact.validFrom < this.oldestDataAt || !this.oldestDataAt) {
      this.oldestDataAt = fact.validFrom;
    }
    // Add fact provenance
    for (const prov of fact.provenance) {
      this.addProvenance(prov);
    }
    // Build claim
    this.claims.push({
      text: `${fact.predicate}: ${String(fact.objectValue || fact.objectId || 'unknown')}`,
      subject: fact.subjectId,
      predicate: fact.predicate,
      value: fact.objectValue || fact.objectId || '',
      confidence: fact.confidence,
      observationStatus: fact.observationStatus,
      validFrom: fact.validFrom,
      validTo: fact.validTo,
    });
    return this;
  }

  addSource(source: EventSource, confidence: number): this {
    this.supportingSources.push({
      sourceId: source.sourceId,
      providerId: source.providerId,
      sourceClass: source.sourceClass,
      url: source.url,
      title: source.title,
      retrievedAt: source.retrievedAt,
      publishedAt: source.publishedAt,
      confidence,
      verificationStatus: 'UNVERIFIED',
    });
    return this;
  }

  addProvenance(provenance: FactProvenance): this {
    this.supportingSources.push({
      sourceId: provenance.sourceId,
      providerId: provenance.providerId,
      sourceClass: provenance.sourceClass,
      retrievedAt: provenance.retrievedAt,
      publishedAt: provenance.publishedAt,
      confidence: provenance.confidence,
      verificationStatus: provenance.verificationStatus,
    });
    return this;
  }

  addContradiction(claimA: EvidenceClaim, claimB: EvidenceClaim, description: string): this {
    this.contradictions.push({ claimA, claimB, description });
    return this;
  }

  addContradictingSource(source: EvidenceSource): this {
    this.contradictingSources.push(source);
    return this;
  }

  build(answer: string): EvidencePack {
    // Deduplicate sources
    const seenSources = new Set<string>();
    const dedupedSupporting = this.supportingSources.filter(s => {
      const key = `${s.providerId}:${s.sourceId}:${s.retrievedAt}`;
      if (seenSources.has(key)) return false;
      seenSources.add(key);
      return true;
    });
    const seenContradicting = new Set<string>();
    const dedupedContradicting = this.contradictingSources.filter(s => {
      const key = `${s.providerId}:${s.sourceId}`;
      if (seenContradicting.has(key)) return false;
      seenContradicting.add(key);
      return true;
    });
    // Compute overall confidence
    const allConfidences = [
      ...this.claims.map(c => c.confidence),
      ...dedupedSupporting.map(s => s.confidence),
    ];
    const overallConfidence = allConfidences.length > 0
      ? allConfidences.reduce((a, b) => a + b, 0) / allConfidences.length
      : 0.5;
    // Determine freshness
    const freshness = this.determineFreshness();
    return {
      query: this.query,
      answer,
      claims: this.claims,
      supportingSources: dedupedSupporting,
      contradictingSources: dedupedContradicting,
      entities: this.entities,
      events: this.events,
      facts: this.facts,
      contradictions: this.contradictions,
      timestamps: {
        queriedAt: nowISO(),
        latestDataAt: this.latestDataAt || nowISO(),
        oldestDataAt: this.oldestDataAt || nowISO(),
      },
      freshness,
      overallConfidence,
      provenanceChain: dedupedSupporting.map(s => `${s.providerId}:${s.sourceClass}`),
      metadata: {
        claimCount: this.claims.length,
        sourceCount: dedupedSupporting.length,
        contradictionCount: this.contradictions.length,
        entityCount: this.entities.length,
        eventCount: this.events.length,
        factCount: this.facts.length,
      },
    };
  }

  private determineFreshness(): FreshnessClass {
    if (!this.latestDataAt) return 'UNKNOWN';
    const age = Date.now() - new Date(this.latestDataAt).getTime();
    if (age < 5 * 60 * 1000) return 'REALTIME';
    if (age < 60 * 60 * 1000) return 'MINUTES';
    if (age < 24 * 60 * 60 * 1000) return 'HOURLY';
    if (age < 7 * 24 * 60 * 60 * 1000) return 'DAILY';
    return 'HISTORICAL';
  }
}

// ============================================================================
// Brain Context Builder — Convert EvidencePack to Brain-consumable format
// ============================================================================

export interface BrainWorldContext {
  readonly summary: string;
  readonly keyFacts: readonly string[];
  readonly entities: readonly { name: string; type: string; keyInfo: string }[];
  readonly recentEvents: readonly { title: string; time: string; importance: string }[];
  readonly sources: readonly string[];
  readonly confidence: number;
  readonly freshness: string;
  readonly disclaimer?: string;
}

export function buildBrainContext(pack: EvidencePack): BrainWorldContext {
  const keyFacts = pack.claims.map(c => c.text).slice(0, 10);
  const entityNames = new Set<string>();
  const entities = pack.entities
    .filter(e => {
      if (entityNames.has(e.identity.canonicalName)) return false;
      entityNames.add(e.identity.canonicalName);
      return true;
    })
    .slice(0, 5)
    .map(e => ({
      name: e.identity.canonicalName,
      type: e.identity.entityType,
      keyInfo: e.tags.join(', ') || e.identity.entityType,
    }));
  const recentEvents = [...pack.events]
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
    .slice(0, 5)
    .map(e => ({
      title: e.title,
      time: e.timestamp,
      importance: e.importance,
    }));
  const sources = [...new Set(pack.supportingSources.map(s => s.providerId))];
  const summary = pack.answer || `Found ${pack.claims.length} claims from ${sources.length} sources.`;
  const disclaimer = pack.overallConfidence < 0.5
    ? 'Warning: Low confidence information. Cross-reference recommended.'
    : undefined;
  return {
    summary,
    keyFacts,
    entities,
    recentEvents,
    sources,
    confidence: pack.overallConfidence,
    freshness: pack.freshness,
    disclaimer,
  };
}
