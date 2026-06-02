/**
 * Adapter: stratum /api/v1/scheduled-jobs → OScheduledJobsManager
 *
 * Phase 15 P1-B2 fixes:
 *   - Path updated: /api/scheduled_jobs → /api/v1/scheduled-jobs
 *   - List returns plain array (not {items:[]}); adapter handles both
 *   - runNow uses /api/v1/scheduled-jobs/{id}/run-now (not agent run directly)
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ScheduledJobWithStatus, AgentName } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type { ScheduledJob, ScheduledJobsResponse } from "@/lib/types";

// Builtin job names that cannot be deleted (only toggled)
const BUILTIN_AGENTS: AgentName[] = ["daily_digest", "reading_companion"];

/** Map backend ScheduledJob → helios ScheduledJobWithStatus */
function adaptJob(job: ScheduledJob): ScheduledJobWithStatus {
  return {
    id: job.id,
    user_id: "",
    name: job.name,
    agent_name: job.agent_name as AgentName,
    agent_params: "{}",
    cron_expression: job.cron_expression,
    timezone: job.timezone,
    enabled: job.enabled,
    notify_on_completion: false,
    notify_on_failure: false,
    max_runtime_seconds: 300,
    created_at: job.created_at ?? new Date().toISOString(),
    updated_at: job.created_at ?? new Date().toISOString(),
    is_builtin: BUILTIN_AGENTS.includes(job.agent_name as AgentName),
    next_run_at: null,
    last_run_at: null,
    last_status: null,
  };
}

/** Normalize API response: list_jobs returns plain array; test mocks may return {items:[]}. */
function toJobArray(data: unknown): ScheduledJob[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as ScheduledJob[];
  const obj = data as { items?: ScheduledJob[] };
  return obj.items ?? [];
}

export interface UseScheduledJobsResult {
  jobs: ScheduledJobWithStatus[];
  isLoading: boolean;
  toggleEnabled: (job: ScheduledJobWithStatus, newEnabled: boolean) => void;
  editCron: (job: ScheduledJobWithStatus) => void;
  remove: (job: ScheduledJobWithStatus) => void;
  runNow: (job: ScheduledJobWithStatus) => void;
  create: (payload: {
    name: string;
    agent_name: string;
    cron_expression: string;
  }) => Promise<void>;
}

/** Hook that provides all data and callbacks for OScheduledJobsManager */
export function useScheduledJobs(): UseScheduledJobsResult {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: () =>
      apiClient.get<ScheduledJobsResponse>("/api/v1/scheduled-jobs"),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] });

  const toggleMutation = useMutation({
    mutationFn: ({
      job,
      enabled,
    }: {
      job: ScheduledJobWithStatus;
      enabled: boolean;
    }) => apiClient.put(`/api/v1/scheduled-jobs/${job.id}`, { enabled }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (job: ScheduledJobWithStatus) =>
      apiClient.delete(`/api/v1/scheduled-jobs/${job.id}`),
    onSuccess: invalidate,
  });

  const createMutation = useMutation({
    mutationFn: (payload: {
      name: string;
      agent_name: string;
      cron_expression: string;
    }) => apiClient.post("/api/v1/scheduled-jobs", payload),
    onSuccess: invalidate,
  });

  return {
    jobs: toJobArray(data).map(adaptJob),
    isLoading,
    toggleEnabled: (job, enabled) => toggleMutation.mutate({ job, enabled }),
    editCron: (_job) => {
      // TECHNICAL_DEBT: cron edit UI not yet implemented — see TECHNICAL_DEBT.md
    },
    remove: (job) => deleteMutation.mutate(job),
    // P1-B2: run-now via /api/v1/scheduled-jobs/{id}/run-now (not agent directly)
    runNow: (job) => {
      void apiClient.post(`/api/v1/scheduled-jobs/${job.id}/run-now`, {});
    },
    create: async (payload) => {
      await createMutation.mutateAsync(payload);
    },
  };
}
