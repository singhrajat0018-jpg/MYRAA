// ============================================================================
// MYRAA Entity Resolution Engine
// ============================================================================

import {
  WorldEntity, EntityAlias, EntityType,
  generateWorldId, nowISO,
} from './contracts';

export interface ResolutionMatch {
  readonly entityId: string;
  readonly score: number;
  readonly matchType: 'exact_name' | 'alias_match' | 'fuzzy_name' | 'provider_id' | 'context_match';
  readonly evidence: string[];
}

export interface ResolutionConfig {
  readonly exactMatchThreshold: number;
  readonly aliasMatchThreshold: number;
  readonly fuzzyMatchThreshold: number;
  readonly providerIdMatchThreshold: number;
  readonly contextMatchThreshold: number;
  readonly maxCandidates: number;
}

const DEFAULT_RESOLUTION_CONFIG: ResolutionConfig = {
  exactMatchThreshold: 0.95,
  aliasMatchThreshold: 0.85,
  fuzzyMatchThreshold: 0.6,
  providerIdMatchThreshold: 0.9,
  contextMatchThreshold: 0.6,
  maxCandidates: 10,
};

export class EntityResolver {
  private config: ResolutionConfig;
  private entityIndex: Map<string, WorldEntity> = new Map();
  private aliasIndex: Map<string, Set<string>> = new Map();
  private providerIdIndex: Map<string, string> = new Map(); // providerId -> entityId
  private entityTypeIndex: Map<EntityType, Set<string>> = new Map();

  constructor(config?: Partial<ResolutionConfig>) {
    this.config = { ...DEFAULT_RESOLUTION_CONFIG, ...config };
  }

  indexEntity(entity: WorldEntity): void {
    this.entityIndex.set(entity.id, entity);
    // Index name
    const nameKey = entity.identity.canonicalName.toLowerCase().trim();
    const nameSet = this.aliasIndex.get(nameKey) || new Set();
    nameSet.add(entity.id);
    this.aliasIndex.set(nameKey, nameSet);
    // Index aliases
    for (const alias of entity.identity.aliases) {
      const key = alias.name.toLowerCase().trim();
      const set = this.aliasIndex.get(key) || new Set();
      set.add(entity.id);
      this.aliasIndex.set(key, set);
      if (alias.type === 'provider_id' || alias.type === 'external_id') {
        this.providerIdIndex.set(alias.name, entity.id);
      }
    }
    // Index by type
    const typeSet = this.entityTypeIndex.get(entity.identity.entityType) || new Set();
    typeSet.add(entity.id);
    this.entityTypeIndex.set(entity.identity.entityType, typeSet);
  }

  removeEntity(entityId: string): void {
    const entity = this.entityIndex.get(entityId);
    if (!entity) return;
    this.entityIndex.delete(entityId);
    // Clean alias index
    const nameKey = entity.identity.canonicalName.toLowerCase().trim();
    const nameSet = this.aliasIndex.get(nameKey);
    if (nameSet) { nameSet.delete(entityId); if (nameSet.size === 0) this.aliasIndex.delete(nameKey); }
    for (const alias of entity.identity.aliases) {
      const key = alias.name.toLowerCase().trim();
      const set = this.aliasIndex.get(key);
      if (set) { set.delete(entityId); if (set.size === 0) this.aliasIndex.delete(key); }
    }
    // Clean provider ID index
    for (const [pid, eid] of this.providerIdIndex) {
      if (eid === entityId) this.providerIdIndex.delete(pid);
    }
    // Clean type index
    const typeSet = this.entityTypeIndex.get(entity.identity.entityType);
    if (typeSet) { typeSet.delete(entityId); if (typeSet.size === 0) this.entityTypeIndex.delete(entity.identity.entityType); }
  }

  resolve(name: string, entityType?: EntityType, context?: Record<string, unknown>): ResolutionMatch[] {
    const lower = name.toLowerCase().trim();
    const candidates: ResolutionMatch[] = [];

    // Exact name match
    const exactIds = this.aliasIndex.get(lower) || new Set();
    for (const id of exactIds) {
      const entity = this.entityIndex.get(id);
      if (!entity) continue;
      if (entityType && entity.identity.entityType !== entityType) continue;
      candidates.push({
        entityId: id,
        score: 1.0,
        matchType: 'exact_name',
        evidence: [`Exact name match: "${name}"`],
      });
    }

    // Alias match (from provider IDs, external IDs)
    for (const [aliasName, eid] of this.providerIdIndex) {
      if (eid === lower || aliasName.toLowerCase() === lower) {
        const entity = this.entityIndex.get(eid);
        if (!entity) continue;
        if (entityType && entity.identity.entityType !== entityType) continue;
        if (!candidates.some(c => c.entityId === eid)) {
          candidates.push({
            entityId: eid,
            score: this.config.providerIdMatchThreshold,
            matchType: 'provider_id',
            evidence: [`Provider ID match: "${aliasName}"`],
          });
        }
      }
    }

    // Fuzzy name match
    if (candidates.length === 0 || candidates[0].score < this.config.fuzzyMatchThreshold) {
      for (const [aliasKey, ids] of this.aliasIndex) {
        const similarity = this.computeSimilarity(lower, aliasKey);
        if (similarity >= this.config.fuzzyMatchThreshold) {
          for (const id of ids) {
            const entity = this.entityIndex.get(id);
            if (!entity) continue;
            if (entityType && entity.identity.entityType !== entityType) continue;
            if (!candidates.some(c => c.entityId === id)) {
              candidates.push({
                entityId: id,
                score: similarity,
                matchType: 'fuzzy_name',
                evidence: [`Fuzzy match: "${name}" ~ "${aliasKey}" (score: ${similarity.toFixed(2)})`],
              });
            }
          }
        }
      }
    }

    // Context match (entity type bonus, tag matching)
    if (context) {
      for (let i = 0; i < candidates.length; i++) {
        const entity = this.entityIndex.get(candidates[i].entityId);
        if (!entity) continue;
        let contextBonus = 0;
        if (context.entityType && entity.identity.entityType === context.entityType) {
          contextBonus += 0.05;
        }
        if (context.tags && Array.isArray(context.tags)) {
          const tagOverlap = entity.tags.filter(t => (context.tags as string[]).includes(t)).length;
          contextBonus += Math.min(tagOverlap * 0.02, 0.1);
        }
        if (contextBonus > 0) {
          const updated = {
            ...candidates[i],
            score: Math.min(candidates[i].score + contextBonus, 1.0),
            matchType: candidates[i].matchType as ResolutionMatch['matchType'],
            evidence: [...candidates[i].evidence, `Context bonus: +${contextBonus.toFixed(2)}`],
          };
          candidates[i] = updated;
        }
      }
    }

    return candidates
      .sort((a, b) => b.score - a.score)
      .slice(0, this.config.maxCandidates);
  }

  autoMergeConfident(minConfidence = 0.9): { sourceId: string; targetId: string }[] {
    const merges: { sourceId: string; targetId: string }[] = [];
    const processed = new Set<string>();
    for (const [alias, ids] of this.aliasIndex) {
      if (ids.size < 2) continue;
      const idArray = Array.from(ids);
      for (let i = 0; i < idArray.length; i++) {
        for (let j = i + 1; j < idArray.length; j++) {
          const pair = [idArray[i], idArray[j]].sort().join(':');
          if (processed.has(pair)) continue;
          processed.add(pair);
          const a = this.entityIndex.get(idArray[i]);
          const b = this.entityIndex.get(idArray[j]);
          if (!a || !b) continue;
          if (a.identity.entityType !== b.identity.entityType) continue;
          // High confidence: same name, same type
          merges.push({ sourceId: idArray[j], targetId: idArray[i] });
        }
      }
    }
    return merges;
  }

  private computeSimilarity(a: string, b: string): number {
    if (a === b) return 1.0;
    if (a.includes(b) || b.includes(a)) {
      const shorter = a.length < b.length ? a : b;
      const longer = a.length < b.length ? b : a;
      return shorter.length / longer.length;
    }
    // Levenshtein-based similarity
    const maxLen = Math.max(a.length, b.length);
    if (maxLen === 0) return 1.0;
    const distance = this.levenshtein(a, b);
    return 1 - distance / maxLen;
  }

  private levenshtein(a: string, b: string): number {
    const m = a.length;
    const n = b.length;
    const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
    for (let i = 0; i <= m; i++) dp[i][0] = i;
    for (let j = 0; j <= n; j++) dp[0][j] = j;
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        dp[i][j] = Math.min(
          dp[i - 1][j] + 1,
          dp[i][j - 1] + 1,
          dp[i - 1][j - 1] + cost,
        );
      }
    }
    return dp[m][n];
  }

  getStats() {
    return {
      entities: this.entityIndex.size,
      aliases: this.aliasIndex.size,
      providerIds: this.providerIdIndex.size,
      typeCounts: Object.fromEntries(
        Array.from(this.entityTypeIndex.entries()).map(([k, v]) => [k, v.size])
      ),
    };
  }
}
