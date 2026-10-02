// ============================================================================
// MYRAA Evidence Engine — Evidence planning, gathering, sufficiency checking
// ============================================================================

import type {
  EvidenceRequirement, GatheredEvidence, EvidenceAssessment, EvidenceConflict,
  EvidenceSufficiency, EvidenceSource, ProvenanceEntry, PlanTask, AgentEvent,
} from './contracts';
import { generateAgentId, nowISO } from './contracts';

// ============================================================================
// Evidence Planner
// ============================================================================

export class EvidenceEngine {
  private gathered: Map<string, GatheredEvidence> = new Map();
  private eventHandler?: (event: AgentEvent) => void;

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  // --- Record gathered evidence ---

  recordEvidence(evidence: Omit<GatheredEvidence, 'id' | 'retrievedAt'>): GatheredEvidence {
    const full: GatheredEvidence = {
      ...evidence,
      id: generateAgentId('ev'),
      retrievedAt: nowISO(),
    };
    this.gathered.set(full.id, full);
    this.emit({
      type: 'EVIDENCE_GATHERED',
      agentId: 'system',
      timestamp: nowISO(),
      data: { source: full.source, confidence: full.confidence },
    });
    return full;
  }

  // --- Assess sufficiency ---

  assessSufficiency(
    requirements: readonly EvidenceRequirement[],
    gathered: readonly GatheredEvidence[] = Array.from(this.gathered.values()),
  ): EvidenceAssessment {
    const conflicts = this.detectConflicts(gathered);
    const missingRequirements = this.findMissingRequirements(requirements, gathered);
    const sufficiency = this.determineSufficiency(requirements, gathered, missingRequirements, conflicts);
    const overallConfidence = this.computeOverallConfidence(gathered);

    if (sufficiency === 'SUFFICIENT') {
      this.emit({ type: 'EVIDENCE_SUFFICIENT', agentId: 'system', timestamp: nowISO(), data: { overallConfidence } });
    } else if (sufficiency === 'INSUFFICIENT' || sufficiency === 'CONFLICTED') {
      this.emit({ type: 'EVIDENCE_INSUFFICIENT', agentId: 'system', timestamp: nowISO(), data: { sufficiency, missingCount: missingRequirements.length } });
    }

    return {
      requirements,
      gathered,
      sufficiency,
      conflicts,
      missingRequirements,
      overallConfidence,
    };
  }

  // --- Conflict detection ---

  private detectConflicts(evidence: readonly GatheredEvidence[]): EvidenceConflict[] {
    const conflicts: EvidenceConflict[] = [];
    for (let i = 0; i < evidence.length; i++) {
      for (let j = i + 1; j < evidence.length; j++) {
        const a = evidence[i];
        const b = evidence[j];
        if (a.source !== b.source && this.dataMayConflict(a.data, b.data)) {
          conflicts.push({
            evidenceAId: a.id,
            evidenceBId: b.id,
            field: 'data',
            valueA: a.data,
            valueB: b.data,
            description: `Conflicting data from ${a.source} vs ${b.source}`,
          });
        }
        if (a.conflictsWith?.includes(b.id) || b.conflictsWith?.includes(a.id)) {
          conflicts.push({
            evidenceAId: a.id,
            evidenceBId: b.id,
            field: 'declared_conflict',
            valueA: a.data,
            valueB: b.data,
            description: `Declared conflict between ${a.id} and ${b.id}`,
          });
        }
      }
    }
    return conflicts;
  }

  private dataMayConflict(a: unknown, b: unknown): boolean {
    if (typeof a === 'object' && typeof b === 'object' && a !== null && b !== null) {
      const objA = a as Record<string, unknown>;
      const objB = b as Record<string, unknown>;
      for (const key of Object.keys(objA)) {
        if (key in objB && objA[key] !== objB[key] && typeof objA[key] === typeof objB[key]) {
          return true;
        }
      }
    }
    return false;
  }

  // --- Missing requirements ---

  private findMissingRequirements(
    requirements: readonly EvidenceRequirement[],
    gathered: readonly GatheredEvidence[],
  ): EvidenceRequirement[] {
    const missing: EvidenceRequirement[] = [];
    for (const req of requirements) {
      const matching = gathered.filter(e => this.evidenceMatchesRequirement(e, req));
      if (matching.length < req.minSources) {
        missing.push(req);
      }
    }
    return missing;
  }

  private evidenceMatchesRequirement(evidence: GatheredEvidence, req: EvidenceRequirement): boolean {
    if (evidence.source !== req.type) return false;
    if (req.freshness) {
      const age = Date.now() - new Date(evidence.freshness).getTime();
      if (req.freshness === 'VERY_FRESH' && age > 3600_000) return false;
      if (req.freshness === 'FRESH' && age > 86400_000) return false;
      if (req.freshness === 'RECENT' && age > 604800_000) return false;
    }
    return true;
  }

  // --- Sufficiency determination ---

  private determineSufficiency(
    requirements: readonly EvidenceRequirement[],
    gathered: readonly GatheredEvidence[],
    missing: readonly EvidenceRequirement[],
    conflicts: readonly EvidenceConflict[],
  ): EvidenceSufficiency {
    if (gathered.length === 0 && requirements.length > 0) return 'INSUFFICIENT';
    if (conflicts.length > 0) return 'CONFLICTED';
    if (missing.length === 0 && gathered.length > 0) return 'SUFFICIENT';
    if (missing.length > 0 && gathered.length > 0) return 'PARTIAL';

    // Check freshness
    const now = Date.now();
    const staleThreshold = 86400_000; // 24 hours
    const anyStale = gathered.some(e => now - new Date(e.freshness).getTime() > staleThreshold);
    if (anyStale && gathered.length > 0) return 'STALE';

    return 'INSUFFICIENT';
  }

  private computeOverallConfidence(evidence: readonly GatheredEvidence[]): number {
    if (evidence.length === 0) return 0;
    const total = evidence.reduce((sum, e) => sum + e.confidence, 0);
    return total / evidence.length;
  }

  // --- Get gathered evidence ---

  getEvidence(id: string): GatheredEvidence | undefined {
    return this.gathered.get(id);
  }

  getAllEvidence(): GatheredEvidence[] {
    return Array.from(this.gathered.values());
  }

  getEvidenceBySource(source: EvidenceSource): GatheredEvidence[] {
    return Array.from(this.gathered.values()).filter(e => e.source === source);
  }

  clear(): void {
    this.gathered.clear();
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }

  getStats() {
    return {
      totalEvidence: this.gathered.size,
      bySource: Array.from(this.gathered.values()).reduce((acc, e) => {
        acc[e.source] = (acc[e.source] || 0) + 1;
        return acc;
      }, {} as Record<string, number>),
      avgConfidence: this.gathered.size > 0
        ? Array.from(this.gathered.values()).reduce((s, e) => s + e.confidence, 0) / this.gathered.size
        : 0,
    };
  }
}
