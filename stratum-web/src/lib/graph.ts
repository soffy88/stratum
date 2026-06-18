import { apiClient } from './apiClient';

export interface GraphEntity {
  id: string;
  name: string;
  type: string;        // concept | method | person | system
  description?: string;
  mention_count: number;
}

export interface GraphRelation {
  source: string;      // entity_id
  target: string;      // entity_id
  type: string;        // affects | defines | part_of | supports | contradicts
  weight: number;
}

export interface Subgraph {
  nodes: GraphEntity[];
  edges: GraphRelation[];
  seed: string;
}

export interface GraphQueryResult {
  answer: string;
  sources: string[];           // substrate_ids
  entities_used: string[];     // entity names
}

export const listEntities = (q?: string) =>
  apiClient
    .get<GraphEntity[]>('/api/v1/graph/entities', { params: { q, limit: 50 } })
    .then(r => r.data);

export const getSubgraph = (entityId: string, maxHops = 2) =>
  apiClient
    .get<Subgraph>(`/api/v1/graph/subgraph/${entityId}`, { params: { max_hops: maxHops } })
    .then(r => r.data);

export const queryGraph = (question: string, maxHops = 2) =>
  apiClient
    .post<GraphQueryResult>('/api/v1/graph/query', { question, max_hops: maxHops })
    .then(r => r.data);
