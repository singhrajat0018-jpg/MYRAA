// ============================================================================
// MYRAA Knowledge Graph Engine
// ============================================================================

import {
  KnowledgeGraph, GraphNode, GraphEdge, RelationshipType,
  WorldEntity, WorldEvent, TemporalFact,
  ObservationStatus, SourceClass,
  generateWorldId, nowISO,
} from './contracts';

export interface GraphTraversalResult {
  readonly nodes: readonly GraphNode[];
  readonly edges: readonly GraphEdge[];
  readonly path: readonly GraphEdge[];
  readonly depth: number;
}

export interface GraphNeighbor {
  readonly node: GraphNode;
  readonly edge: GraphEdge;
  readonly direction: 'outgoing' | 'incoming';
}

export class KnowledgeGraphEngine {
  private graph: KnowledgeGraph = {
    nodes: new Map(),
    edges: new Map(),
    adjacency: new Map(),
  };
  private nodeTypeIndex: Map<string, Set<string>> = new Map();
  private edgeRelationshipIndex: Map<RelationshipType, Set<string>> = new Map();
  private entityNodeMap: Map<string, string> = new Map(); // entity ID -> graph node ID
  private eventNodeMap: Map<string, string> = new Map(); // event ID -> graph node ID

  // ==========================================================================
  // Node Operations
  // ==========================================================================

  addNode(type: GraphNode['type'], label: string, metadata: Record<string, unknown> = {}): GraphNode {
    const id = generateWorldId();
    const now = nowISO();
    const node: GraphNode = { id, type, label, metadata, createdAt: now, updatedAt: now };
    this.graph.nodes.set(id, node);
    this.graph.adjacency.set(id, new Set());
    const typeSet = this.nodeTypeIndex.get(type) || new Set();
    typeSet.add(id);
    this.nodeTypeIndex.set(type, typeSet);
    return node;
  }

  getNode(id: string): GraphNode | undefined {
    return this.graph.nodes.get(id);
  }

  getNodesByType(type: GraphNode['type']): GraphNode[] {
    const ids = this.nodeTypeIndex.get(type) || new Set();
    return Array.from(ids).map(id => this.graph.nodes.get(id)!).filter(Boolean);
  }

  removeNode(id: string): boolean {
    const node = this.graph.nodes.get(id);
    if (!node) return false;
    // Remove all edges connected to this node
    const edgeIds = this.graph.adjacency.get(id) || new Set();
    for (const edgeId of edgeIds) {
      this.removeEdge(edgeId);
    }
    this.graph.nodes.delete(id);
    this.graph.adjacency.delete(id);
    const typeSet = this.nodeTypeIndex.get(node.type);
    if (typeSet) typeSet.delete(id);
    return true;
  }

  // ==========================================================================
  // Edge Operations
  // ==========================================================================

  addEdge(
    sourceId: string,
    targetId: string,
    relationship: RelationshipType,
    options: {
      observationStatus?: ObservationStatus;
      confidence?: number;
      validFrom?: string;
      validTo?: string;
      sourceRef?: string;
      metadata?: Record<string, unknown>;
    } = {}
  ): GraphEdge | null {
    const source = this.graph.nodes.get(sourceId);
    const target = this.graph.nodes.get(targetId);
    if (!source || !target) return null;
    const id = generateWorldId();
    const now = nowISO();
    const edge: GraphEdge = {
      id,
      sourceId,
      targetId,
      relationship,
      observationStatus: options.observationStatus || 'UNKNOWN',
      confidence: options.confidence ?? 0.5,
      validFrom: options.validFrom || now,
      validTo: options.validTo,
      sourceRef: options.sourceRef || '',
      metadata: options.metadata || {},
    };
    this.graph.edges.set(id, edge);
    const srcAdj = this.graph.adjacency.get(sourceId) || new Set();
    srcAdj.add(id);
    this.graph.adjacency.set(sourceId, srcAdj);
    const tgtAdj = this.graph.adjacency.get(targetId) || new Set();
    tgtAdj.add(id);
    this.graph.adjacency.set(targetId, tgtAdj);
    const relSet = this.edgeRelationshipIndex.get(relationship) || new Set();
    relSet.add(id);
    this.edgeRelationshipIndex.set(relationship, relSet);
    return edge;
  }

  getEdge(id: string): GraphEdge | undefined {
    return this.graph.edges.get(id);
  }

  removeEdge(id: string): boolean {
    const edge = this.graph.edges.get(id);
    if (!edge) return false;
    this.graph.edges.delete(id);
    const srcAdj = this.graph.adjacency.get(edge.sourceId);
    if (srcAdj) srcAdj.delete(id);
    const tgtAdj = this.graph.adjacency.get(edge.targetId);
    if (tgtAdj) tgtAdj.delete(id);
    const relSet = this.edgeRelationshipIndex.get(edge.relationship);
    if (relSet) relSet.delete(id);
    return true;
  }

  getEdgesByRelationship(relationship: RelationshipType): GraphEdge[] {
    const ids = this.edgeRelationshipIndex.get(relationship) || new Set();
    return Array.from(ids).map(id => this.graph.edges.get(id)!).filter(Boolean);
  }

  // ==========================================================================
  // Traversal
  // ==========================================================================

  getNeighbors(nodeId: string, maxDepth = 1): GraphNeighbor[] {
    const neighbors: GraphNeighbor[] = [];
    const visited = new Set<string>();
    const queue: { id: string; depth: number }[] = [{ id: nodeId, depth: 0 }];
    while (queue.length > 0) {
      const { id, depth } = queue.shift()!;
      if (depth >= maxDepth) continue;
      if (visited.has(id)) continue;
      visited.add(id);
      const edgeIds = this.graph.adjacency.get(id) || new Set();
      for (const edgeId of edgeIds) {
        const edge = this.graph.edges.get(edgeId);
        if (!edge) continue;
        const neighborId = edge.sourceId === id ? edge.targetId : edge.sourceId;
        const neighborNode = this.graph.nodes.get(neighborId);
        if (!neighborNode) continue;
        neighbors.push({
          node: neighborNode,
          edge,
          direction: edge.sourceId === id ? 'outgoing' : 'incoming',
        });
        if (depth + 1 < maxDepth) {
          queue.push({ id: neighborId, depth: depth + 1 });
        }
      }
    }
    return neighbors;
  }

  findPath(sourceId: string, targetId: string, maxDepth = 6): GraphEdge[][] {
    const paths: GraphEdge[][] = [];
    const queue: { nodeId: string; path: GraphEdge[] }[] = [{ nodeId: sourceId, path: [] }];
    const visited = new Set<string>();
    while (queue.length > 0 && paths.length < 10) {
      const { nodeId, path } = queue.shift()!;
      if (nodeId === targetId && path.length > 0) {
        paths.push(path);
        continue;
      }
      if (path.length >= maxDepth) continue;
      visited.add(nodeId);
      const edgeIds = this.graph.adjacency.get(nodeId) || new Set();
      for (const edgeId of edgeIds) {
        const edge = this.graph.edges.get(edgeId);
        if (!edge) continue;
        const nextId = edge.sourceId === nodeId ? edge.targetId : edge.sourceId;
        if (!visited.has(nextId)) {
          queue.push({ nodeId: nextId, path: [...path, edge] });
        }
      }
    }
    return paths;
  }

  getSubgraph(nodeId: string, depth = 2): { nodes: GraphNode[]; edges: GraphEdge[] } {
    const nodeIds = new Set<string>();
    const edgeIds = new Set<string>();
    const queue: { id: string; d: number }[] = [{ id: nodeId, d: 0 }];
    while (queue.length > 0) {
      const { id, d } = queue.shift()!;
      if (d > depth || nodeIds.has(id)) continue;
      nodeIds.add(id);
      const adj = this.graph.adjacency.get(id) || new Set();
      for (const eid of adj) {
        edgeIds.add(eid);
        const edge = this.graph.edges.get(eid);
        if (edge) {
          const nextId = edge.sourceId === id ? edge.targetId : edge.sourceId;
          if (d + 1 <= depth) queue.push({ id: nextId, d: d + 1 });
        }
      }
    }
    return {
      nodes: Array.from(nodeIds).map(id => this.graph.nodes.get(id)!).filter(Boolean),
      edges: Array.from(edgeIds).map(id => this.graph.edges.get(id)!).filter(Boolean),
    };
  }

  // ==========================================================================
  // Entity/Event Integration
  // ==========================================================================

  addEntityNode(entity: WorldEntity): GraphNode {
    const node = this.addNode('entity', entity.identity.canonicalName, {
      entityType: entity.identity.entityType,
      importance: entity.importance,
      entityId: entity.id,
    });
    this.entityNodeMap.set(entity.id, node.id);
    return node;
  }

  addEventNode(event: WorldEvent): GraphNode {
    const node = this.addNode('event', event.title, {
      eventType: event.type,
      importance: event.importance,
      eventId: event.id,
      timestamp: event.timestamp,
    });
    this.eventNodeMap.set(event.id, node.id);
    return node;
  }

  addFactEdge(fact: TemporalFact, sourceRef: string): GraphEdge | null {
    const subjectNodeId = this.entityNodeMap.get(fact.subjectId);
    if (!subjectNodeId) return null;
    if (fact.objectId) {
      const objectNodeId = this.entityNodeMap.get(fact.objectId);
      if (!objectNodeId) return null;
      return this.addEdge(subjectNodeId, objectNodeId, 'RELATES_TO', {
        observationStatus: fact.observationStatus,
        confidence: fact.confidence,
        validFrom: fact.validFrom,
        validTo: fact.validTo,
        sourceRef,
        metadata: { predicate: fact.predicate, factId: fact.id },
      });
    }
    return null;
  }

  linkEventToEntities(event: WorldEvent, sourceRef: string): GraphEdge[] {
    const eventNodeId = this.eventNodeMap.get(event.id);
    if (!eventNodeId) return [];
    const edges: GraphEdge[] = [];
    for (const entityId of event.entityIds) {
      const entityNodeId = this.entityNodeMap.get(entityId);
      if (!entityNodeId) continue;
      const edge = this.addEdge(eventNodeId, entityNodeId, 'MENTIONS', {
        observationStatus: 'OBSERVED',
        confidence: 1.0,
        sourceRef,
      });
      if (edge) edges.push(edge);
    }
    return edges;
  }

  linkEvents(event1Id: string, event2Id: string, relationship: RelationshipType): GraphEdge | null {
    const n1 = this.eventNodeMap.get(event1Id);
    const n2 = this.eventNodeMap.get(event2Id);
    if (!n1 || !n2) return null;
    return this.addEdge(n1, n2, relationship, {
      observationStatus: 'OBSERVED',
      confidence: 0.7,
    });
  }

  // ==========================================================================
  // Query
  // ==========================================================================

  searchNodes(query: string, type?: GraphNode['type'], limit = 20): GraphNode[] {
    const lower = query.toLowerCase();
    const results: { node: GraphNode; score: number }[] = [];
    const candidates = type ? (this.nodeTypeIndex.get(type) || new Set()) :
      new Set(this.graph.nodes.keys());
    for (const id of candidates) {
      const node = this.graph.nodes.get(id);
      if (!node) continue;
      const label = node.label.toLowerCase();
      let score = 0;
      if (label === lower) score = 100;
      else if (label.startsWith(lower)) score = 80;
      else if (label.includes(lower)) score = 60;
      if (score > 0) results.push({ node, score });
    }
    return results.sort((a, b) => b.score - a.score).slice(0, limit).map(r => r.node);
  }

  // ==========================================================================
  // Stats
  // ==========================================================================

  getStats() {
    return {
      nodes: this.graph.nodes.size,
      edges: this.graph.edges.size,
      nodeTypes: Object.fromEntries(
        Array.from(this.nodeTypeIndex.entries()).map(([k, v]) => [k, v.size])
      ),
      edgeTypes: Object.fromEntries(
        Array.from(this.edgeRelationshipIndex.entries()).map(([k, v]) => [k, v.size])
      ),
      entityNodes: this.entityNodeMap.size,
      eventNodes: this.eventNodeMap.size,
    };
  }

  getGraph(): KnowledgeGraph {
    return this.graph;
  }
}
