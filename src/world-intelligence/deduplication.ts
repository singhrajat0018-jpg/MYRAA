// ============================================================================
// MYRAA Deduplication Engine
// ============================================================================

import {
  WorldEntity, WorldEvent, TemporalFact,
  nowISO,
} from './contracts';

export interface DeduplicationResult {
  readonly isDuplicate: boolean;
  readonly duplicateOf?: string;
  readonly confidence: number;
  readonly reason: string;
}

export class DeduplicationEngine {
  private eventFingerprintIndex: Map<string, string> = new Map(); // fingerprint -> event ID
  private factFingerprintIndex: Map<string, string> = new Map(); // fingerprint -> fact ID
  private entityFingerprintIndex: Map<string, string> = new Map(); // fingerprint -> entity ID

  // --- Event Deduplication ---

  checkEventDuplicate(event: WorldEvent): DeduplicationResult {
    const fp = this.computeEventFingerprint(event);
    const existingId = this.eventFingerprintIndex.get(fp);
    if (existingId && existingId !== event.id) {
      return {
        isDuplicate: true,
        duplicateOf: existingId,
        confidence: 0.95,
        reason: `Exact fingerprint match with event ${existingId}`,
      };
    }
    // Check title similarity for near-duplicates
    const titleFp = this.normalizeTitle(event.title);
    for (const [existingFp, existingId] of this.eventFingerprintIndex) {
      if (existingId === event.id) continue;
      const existingEvent = this.getEventById(existingId);
      if (!existingEvent) continue;
      const existingTitleFp = this.normalizeTitle(existingEvent.title);
      const similarity = this.computeTitleSimilarity(titleFp, existingTitleFp);
      if (similarity > 0.85 && event.type === existingEvent.type) {
        return {
          isDuplicate: true,
          duplicateOf: existingId,
          confidence: similarity * 0.9,
          reason: `Title similarity (${(similarity * 100).toFixed(0)}%) + same event type`,
        };
      }
    }
    return { isDuplicate: false, confidence: 0, reason: 'No duplicate found' };
  }

  registerEvent(event: WorldEvent): void {
    const fp = this.computeEventFingerprint(event);
    if (!this.eventFingerprintIndex.has(fp)) {
      this.eventFingerprintIndex.set(fp, event.id);
    }
  }

  // --- Fact Deduplication ---

  checkFactDuplicate(fact: TemporalFact): DeduplicationResult {
    const fp = this.computeFactFingerprint(fact);
    const existingId = this.factFingerprintIndex.get(fp);
    if (existingId && existingId !== fact.id) {
      return {
        isDuplicate: true,
        duplicateOf: existingId,
        confidence: 0.9,
        reason: `Same subject+predicate+object as fact ${existingId}`,
      };
    }
    return { isDuplicate: false, confidence: 0, reason: 'No duplicate found' };
  }

  registerFact(fact: TemporalFact): void {
    const fp = this.computeFactFingerprint(fact);
    if (!this.factFingerprintIndex.has(fp)) {
      this.factFingerprintIndex.set(fp, fact.id);
    }
  }

  // --- Entity Deduplication ---

  checkEntityDuplicate(entity: WorldEntity): DeduplicationResult {
    const fp = this.computeEntityFingerprint(entity);
    const existingId = this.entityFingerprintIndex.get(fp);
    if (existingId && existingId !== entity.id) {
      return {
        isDuplicate: true,
        duplicateOf: existingId,
        confidence: 0.9,
        reason: `Same name+type as entity ${existingId}`,
      };
    }
    // Check alias overlap
    for (const alias of entity.identity.aliases) {
      const aliasLower = alias.name.toLowerCase().trim();
      for (const [existingFp, existingId] of this.entityFingerprintIndex) {
        if (existingId === entity.id) continue;
        if (existingFp.includes(aliasLower)) {
          return {
            isDuplicate: true,
            duplicateOf: existingId,
            confidence: 0.75,
            reason: `Alias "${alias.name}" matches existing entity fingerprint`,
          };
        }
      }
    }
    return { isDuplicate: false, confidence: 0, reason: 'No duplicate found' };
  }

  registerEntity(entity: WorldEntity): void {
    const fp = this.computeEntityFingerprint(entity);
    if (!this.entityFingerprintIndex.has(fp)) {
      this.entityFingerprintIndex.set(fp, entity.id);
    }
  }

  // --- Fingerprint Computation ---

  computeEventFingerprint(event: WorldEvent): string {
    const parts = [
      event.type,
      this.normalizeTitle(event.title),
      [...event.entityIds].sort().join(','),
      this.dateKey(event.timestamp),
    ];
    return parts.join('|');
  }

  computeFactFingerprint(fact: TemporalFact): string {
    return [fact.subjectId, fact.predicate, fact.objectId || '', String(fact.objectValue || '')].join('|');
  }

  computeEntityFingerprint(entity: WorldEntity): string {
    return [entity.identity.canonicalName.toLowerCase().trim(), entity.identity.entityType].join('|');
  }

  computeTitleSimilarity(a: string, b: string): number {
    const na = this.normalizeTitle(a);
    const nb = this.normalizeTitle(b);
    if (na === nb) return 1.0;
    if (na.includes(nb) || nb.includes(na)) {
      return Math.min(na.length, nb.length) / Math.max(na.length, nb.length);
    }
    // Jaccard similarity on words
    const wordsA = new Set(na.split(/\s+/));
    const wordsB = new Set(nb.split(/\s+/));
    const intersection = new Set([...wordsA].filter(w => wordsB.has(w)));
    const union = new Set([...wordsA, ...wordsB]);
    return union.size > 0 ? intersection.size / union.size : 0;
  }

  private normalizeTitle(title: string): string {
    return title.toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  private dateKey(dateStr: string): string {
    try {
      const d = new Date(dateStr);
      return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
    } catch {
      return dateStr.slice(0, 10);
    }
  }

  private getEventById(_id: string): WorldEvent | undefined {
    // This is a stub - in production, the engine would inject the state engine reference
    return undefined;
  }

  getStats() {
    return {
      eventFingerprints: this.eventFingerprintIndex.size,
      factFingerprints: this.factFingerprintIndex.size,
      entityFingerprints: this.entityFingerprintIndex.size,
    };
  }
}
