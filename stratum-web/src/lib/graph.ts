import { apiClient } from './api-client';

export interface GraphEntity {
  id: string;
  name: string;
  type: string;
  description?: string;
  mention_count: number;
}

export interface GraphRelation {
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface Subgraph {
  nodes: GraphEntity[];
  edges: GraphRelation[];
  seed: string;
}

export interface GraphQueryResult {
  answer: string;
  sources: string[];
  entities_used: string[];
}

export const listEntities = (q?: string) => {
  const qs = q ? `?q=${encodeURIComponent(q)}&limit=50` : '?limit=50';
  return apiClient.get<GraphEntity[]>(`/api/v1/graph/entities${qs}`);
};

export const getSubgraph = (entityId: string, maxHops = 2) =>
  apiClient.get<Subgraph>(`/api/v1/graph/subgraph/${entityId}?max_hops=${maxHops}`);

export const queryGraph = (question: string, maxHops = 2) =>
  apiClient.post<GraphQueryResult>('/api/v1/graph/query', { question, max_hops: maxHops });
