/**
 * Metrics adapter — ingestion / search / agent run metrics.
 *
 * Pattern mirrors adapters/agents.ts:
 *   - Import apiClient
 *   - try/catch, return null on error
 *   - Export typed interfaces
 */
import { apiClient } from '@/lib/api-client';

// ── Ingestion ──────────────────────────────────────────────────────────────────

export interface IngestionSummary {
  total_substrate_count: number;
  new_last_24h: number;
  with_l0_pct: number;
  with_l1_pct: number;
  with_l2_pct: number;
  with_embedding_pct: number;
}

export interface IngestionTimeSeriesPoint {
  date: string;
  count: number;
}

export interface IngestionMetrics {
  summary: IngestionSummary;
  time_series: IngestionTimeSeriesPoint[];
}

// ── Search ─────────────────────────────────────────────────────────────────────

export interface SearchSummary {
  total_queries: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  avg_result_count: number;
  queries_last_24h: number;
}

export interface LatencyHistogramBucket {
  bucket: string;
  count: number;
}

export interface SearchMetrics {
  summary: SearchSummary;
  latency_histogram: LatencyHistogramBucket[];
}

// ── Agents ─────────────────────────────────────────────────────────────────────

export interface AgentSummary {
  total_runs: number;
  success_rate: number;
  avg_duration_sec: number;
  runs_last_24h: number;
}

export interface AgentBreakdown {
  agent: string;
  runs: number;
  success_rate: number;
  avg_duration: number;
}

export interface AgentMetrics {
  summary: AgentSummary;
  by_agent: AgentBreakdown[];
}

// ── Fetchers ───────────────────────────────────────────────────────────────────

export async function getIngestionMetrics(): Promise<IngestionMetrics | null> {
  try {
    return await apiClient.get<IngestionMetrics>('/api/v1/metrics/ingestion');
  } catch {
    return null;
  }
}

export async function getSearchMetrics(): Promise<SearchMetrics | null> {
  try {
    return await apiClient.get<SearchMetrics>('/api/v1/metrics/search');
  } catch {
    return null;
  }
}

export async function getAgentMetrics(): Promise<AgentMetrics | null> {
  try {
    return await apiClient.get<AgentMetrics>('/api/v1/metrics/agents');
  } catch {
    return null;
  }
}
