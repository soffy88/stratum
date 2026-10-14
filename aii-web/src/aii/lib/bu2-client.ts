/**
 * BU2 (Book Understanding v2) client — /api/v1/bu/* on stratum-sl.
 * Uses the authenticated apiClient (Bearer + refresh), returns raw JSON.
 */
import { apiClient } from '@/lib/api-client';

const base = (runId: string) => `/api/v1/bu/${encodeURIComponent(runId)}`;

export interface Bu2ListItem {
  id: string;
  run_id: string;
  substrate_id: string;
  book_title: string;
  summary: string;
  grade: string;
  version: number;
  status: string;
  created_at: string;
}

export interface Bu2ChapterSummary {
  chapter_id: string;
  chapter_question: string | null;
  primary_role: string | null;
  concepts_introduced: number;
  arguments_count: number;
  evidence_count: number;
}

export interface Bu2Detail {
  id: string;
  run_id: string;
  book_title: string;
  status: string;
  version: number;
  coverage_score: number;
  verification_score: number;
  chapters: Bu2ChapterSummary[];
}

export interface Bu2Claim {
  claim: string;
  is_supported: boolean | null;
  evidence_refs: string[];
  presented_as: 'SOURCE' | 'MODEL_INFERENCE';
}

export interface Bu2ChapterDetail {
  chapter_id: string;
  chapter_question: string | null;
  chapter_goal: string | null;
  chapter_thesis: string | null;
  primary_role: string | null;
  claims: Bu2Claim[];
  arguments_refs: string[];
}

export interface Bu2Gate {
  gate_number: number;
  gate_name: string;
  status: string;
  score: number | null;
  detail: string | null;
  evidence: unknown;
}

export interface Bu2QualityGates {
  run_id: string;
  all_passed: boolean;
  hard_gates: Bu2Gate[];
  six_dimension: Bu2Gate | null;
}

export interface Bu2Evidence {
  id: string;
  chapter_id: string;
  kind: string;
  locator: string;
  quote: string;
  strength: string | null;
  verified: boolean | null;
}

export interface Bu2Argument {
  id: string;
  chapter_id: string | null;
  claim: string | null;
  premises: string[];
  inference_steps: string[];
  conclusion: string | null;
  evidence: Bu2Evidence[];
  is_supported: boolean | null;
}

export interface Bu2GraphNode { id: string; node_type: string; label: string; chapter_id: string | null }
export interface Bu2GraphEdge { id: string; source_node_id: string; target_node_id: string; relation_type: string }
export interface Bu2Graph {
  kind: 'reasoning' | 'argument';
  total_nodes: number;
  total_edges: number;
  nodes: Bu2GraphNode[];
  edges: Bu2GraphEdge[];
}

export interface Bu2Evolution {
  concept_ref: string;
  chapter_ref: string;
  evolution_type: string;
  definition: string;
  version: number;
}

export interface Bu2GuideStep {
  concept: string;
  chapter_id: string;
  kind: string;
  requires: string[];
  quote: string;
}

export interface Bu2LearningGuide {
  step_count: number;
  steps: Bu2GuideStep[];
  by_chapter: Record<string, string[]>;
  chapter_order: string[];
  cycles: string[];
}

/** The bounded P13 synthesis summary (see api-client BuSynthesis). */
export interface Bu2Synthesis {
  run_id: string;
  book_id: string;
  view: 'summary' | 'concepts' | 'claims' | 'full';
  available_views: string[];
  thesis: {
    core_thesis: string;
    core_thesis_provenance?: string | null;
    counts: Record<string, number>;
  };
  problem_definition?: string;
  counts?: {
    concepts: number;
    claims: number;
    mechanisms: number;
    arithmetic_arguments: Record<string, number>;
  };
  claims_summary?: Record<string, unknown>;
  chapters?: { chapter_count: number; assignments: Array<Record<string, unknown>> };
  concept_roles?: Record<string, number>;
  unresolved_questions?: { count: number; items: string[] };
  limitations?: { count: number; items: string[] };
  author_model?: Record<string, unknown>;
  contradictions?: Record<string, unknown>;
  core_concepts?: Array<{ concept_id: string; label: string; role: string; chapter_refs: string[] }>;
  concepts?: Array<{
    concept_id: string;
    label: string;
    role: string;
    definition?: string;
    chapter_refs: string[];
    prerequisites?: string[];
  }>;
  claims?: Array<{
    claim_id: string;
    claim: string;
    is_supported: boolean | null;
    chapter_ids: string[];
    evidence_ids: string[];
  }>;
  total?: number;
  offset?: number;
  limit?: number;
  has_more?: boolean;
}

export const bu2 = {
  list: () => apiClient.get<Bu2ListItem[]>('/api/v1/bu'),
  detail: (runId: string) => apiClient.get<Bu2Detail>(base(runId)),
  chapter: (runId: string, chapterId: string) =>
    apiClient.get<Bu2ChapterDetail>(`${base(runId)}/chapters/${encodeURIComponent(chapterId)}`),
  gates: (runId: string) => apiClient.get<Bu2QualityGates>(`${base(runId)}/quality-gates`),
  evidence: (runId: string, chapterId?: string, limit = 50, offset = 0) =>
    apiClient.get<{ total: number; items: Bu2Evidence[] }>(
      `${base(runId)}/evidence?limit=${limit}&offset=${offset}${chapterId ? `&chapter_id=${encodeURIComponent(chapterId)}` : ''}`,
    ),
  arguments: (runId: string, chapterId?: string) =>
    apiClient.get<{ total: number; items: Bu2Argument[] }>(
      `${base(runId)}/arguments${chapterId ? `?chapter_id=${encodeURIComponent(chapterId)}` : ''}`,
    ),
  graph: (runId: string, kind: 'reasoning' | 'argument', limit = 300) =>
    apiClient.get<Bu2Graph>(`${base(runId)}/graph?kind=${kind}&limit=${limit}`),
  learningGuide: (runId: string, limit = 500) =>
    apiClient.get<Bu2LearningGuide>(`${base(runId)}/learning-guide?limit=${limit}`),
  evolution: (runId: string, limit = 100, offset = 0) =>
    apiClient.get<{ total: number; items: Bu2Evolution[] }>(
      `${base(runId)}/concept-evolution?limit=${limit}&offset=${offset}`,
    ),
  synthesis: (runId: string) => apiClient.get<Bu2Synthesis>(`${base(runId)}/synthesis`),
  synthesisPage: (runId: string, view: 'concepts' | 'claims', limit = 50, offset = 0, chapter?: string) =>
    apiClient.get<Bu2Synthesis>(
      `${base(runId)}/synthesis?view=${view}&limit=${limit}&offset=${offset}${
        chapter ? `&chapter=${encodeURIComponent(chapter)}` : ''
      }`,
    ),
};
