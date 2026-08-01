/**
 * Adapter: stratum POST /api/v1/retrieve → multi-stage retrieval
 */

import { apiClient } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RetrieveOptions {
  query: string;
  substrate_ids?: string[];
  max_results: number;
  min_score: number;
  use_rerank: boolean;
}

export interface RetrievalResult {
  substrate_id: string;
  score: number;
  rerank_score: number | null;
  l0_summary: string;
  l1_summary: string | null;
  title: string;
  source_path: string;
}

export interface TrajectoryStep {
  phase: "coarse" | "expand" | "drill";
  duration_ms: number;
  result_count: number;
  siblings_added?: number;
}

export interface RetrievalTrajectory {
  steps: TrajectoryStep[];
  total_ms: number;
}

export interface RetrieveResponse {
  query: string;
  results: RetrievalResult[];
  trajectory: RetrievalTrajectory;
  total_ms: number;
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

export async function retrieve(
  query: string,
  opts?: Partial<RetrieveOptions>
): Promise<RetrieveResponse | null> {
  try {
    return await apiClient.post<RetrieveResponse>("/api/v1/retrieve", {
      query,
      substrate_ids: opts?.substrate_ids,
      max_results: opts?.max_results ?? 10,
      min_score: opts?.min_score ?? 0.1,
      use_rerank: opts?.use_rerank ?? true,
    });
  } catch {
    return null;
  }
}
