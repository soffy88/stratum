/**
 * Adapter: stratum /api/v1/agents/* → OAIQAPanel + OAISummaryCard
 */

import { useQuery } from "@tanstack/react-query";
import type { QAResponse, OAISummaryCardProps } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type {
  RunAgentResponse,
  AgentRun,
  AgentRunDetail,
  AgentRunsResponse,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// OAIQAPanel adapter
// ---------------------------------------------------------------------------

/** Map backend RunAgentResponse → helios QAResponse */
function adaptQAResponse(res: RunAgentResponse): QAResponse {
  return {
    answer:
      res.status === "not_implemented"
        ? "reading_companion 暂未实现 (Phase 11D 补全)"
        : res.error ?? "Agent 运行中，暂无结果",
    citations: [],
    sources_used: undefined,
  };
}

/**
 * Hook for OAIQAPanel.onAsk.
 * Wraps POST /api/v1/agents/reading_companion/run and maps to QAResponse.
 * Returns 501 stub message while reading_companion is pending Phase 11D.
 */
export function useAgentQA() {
  return async (question: string): Promise<QAResponse> => {
    try {
      const res = await apiClient.post<RunAgentResponse>(
        "/api/v1/agents/reading_companion/run",
        { params: { query: question } }
      );
      return adaptQAResponse(res);
    } catch {
      return {
        answer: "reading_companion 暂不可用 (Phase 11D 补)",
        citations: [],
      };
    }
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
    summary:
      run.status === "completed"
        ? `[${run.agent_name}] 已完成`
        : `[${run.agent_name}] ${run.status}`,
    date: run.started_at ?? undefined,
    digestSent: run.status === "completed",
    citations: [],
  };
}

/** Hook: fetch runs for a given agent (GET /api/v1/agents/runs?agent=X) */
export function useAgentRuns(agentName: string) {
  return useQuery({
    queryKey: ["agent-runs", agentName],
    queryFn: () =>
      apiClient.get<AgentRunsResponse>(
        `/api/v1/agents/runs?agent=${agentName}`
      ),
  });
}

/** Hook: fetch a single run detail (GET /api/v1/agents/runs/{run_id}) */
export function useAgentRunDetail(runId: string) {
  return useQuery({
    queryKey: ["agent-run-detail", runId],
    queryFn: () => apiClient.get<AgentRunDetail>(`/api/v1/agents/runs/${runId}`),
    enabled: !!runId,
  });
}
