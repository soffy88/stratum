/**
 * Adapter: stratum /api/agents/* → OAIQAPanel + OAISummaryCard
 */

import { useQuery } from "@tanstack/react-query";
import type { QAResponse, OAISummaryCardProps } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type { RunAgentResponse, AgentRun, AgentRunsResponse } from "@/lib/types";

// ---------------------------------------------------------------------------
// OAIQAPanel adapter
// ---------------------------------------------------------------------------

/** Map backend RunAgentResponse → helios QAResponse */
function adaptQAResponse(res: RunAgentResponse): QAResponse {
  return {
    answer: res.agent_run.output ?? res.message,
    citations: [],
    sources_used: undefined,
  };
}

/**
 * Hook for OAIQAPanel.onAsk.
 * Wraps POST /api/agents/reading_companion/run and maps to QAResponse.
 * NOTE: backend currently returns a stub (status: "pending"). The Block
 * handles the pending/answer states internally.
 */
export function useAgentQA() {
  return async (question: string): Promise<QAResponse> => {
    const res = await apiClient.post<RunAgentResponse>(
      "/api/agents/reading_companion/run",
      { params: { query: question } }
    );
    return adaptQAResponse(res);
  };
}

// ---------------------------------------------------------------------------
// OAISummaryCard adapter
// ---------------------------------------------------------------------------

/** Map backend AgentRun → OAISummaryCard props */
export function adaptSummaryCard(
  run: AgentRun
): Pick<OAISummaryCardProps, "summary" | "date" | "digestSent" | "citations"> {
  return {
    summary: run.output ?? "摘要生成中...",
    date: run.started_at ?? undefined,
    digestSent: run.status === "completed",
    citations: [],
  };
}

/** Hook: fetch daily_digest runs for SummaryPanel */
export function useAgentRuns(agentName: string) {
  return useQuery({
    queryKey: ["agent-runs", agentName],
    queryFn: () =>
      apiClient.get<AgentRunsResponse>(`/api/agents/runs?agent=${agentName}`),
  });
}
