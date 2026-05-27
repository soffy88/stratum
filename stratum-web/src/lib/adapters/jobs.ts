/**
 * Adapter: stratum /api/scheduled_jobs → OScheduledJobsManager
 *
 * helios ScheduledJob has more fields than the backend returns.
 * This adapter fills in sensible defaults for display-only fields.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ScheduledJobWithStatus, AgentName } from "@helios/blocks";
import { apiClient } from "@/lib/api-client";
import type { ScheduledJob, ScheduledJobsResponse } from "@/lib/types";

// Builtin job names that cannot be deleted (only toggled)
// NOTE: "weekly_review" is NOT in helios AgentName type — it's a stratum-only
// extension. TECHNICAL_DEBT: align AgentName enum when helios adds it.
const BUILTIN_AGENTS: AgentName[] = [
  "daily_digest",
  "reading_companion",
];

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

export interface UseScheduledJobsResult {
  jobs: ScheduledJobWithStatus[];
  isLoading: boolean;
  toggleEnabled: (job: ScheduledJobWithStatus, newEnabled: boolean) => void;
  editCron: (job: ScheduledJobWithStatus) => void;
  remove: (job: ScheduledJobWithStatus) => void;
  runNow: (job: ScheduledJobWithStatus) => void;
  /** Create new job (not a Block prop — called externally from CreateJobForm) */
  create: (payload: { name: string; agent_name: string; cron_expression: string }) => Promise<void>;
}

/** Hook that provides all data and callbacks for OScheduledJobsManager */
export function useScheduledJobs(): UseScheduledJobsResult {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: () => apiClient.get<ScheduledJobsResponse>("/api/scheduled_jobs"),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] });

  const toggleMutation = useMutation({
    mutationFn: ({ job, enabled }: { job: ScheduledJobWithStatus; enabled: boolean }) =>
      apiClient.put(`/api/scheduled_jobs/${job.id}`, { enabled }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (job: ScheduledJobWithStatus) =>
      apiClient.delete(`/api/scheduled_jobs/${job.id}`),
    onSuccess: invalidate,
  });

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; agent_name: string; cron_expression: string }) =>
      apiClient.post("/api/scheduled_jobs", payload),
    onSuccess: invalidate,
  });

  return {
    jobs: (data?.items ?? []).map(adaptJob),
    isLoading,
    toggleEnabled: (job, enabled) => toggleMutation.mutate({ job, enabled }),
    editCron: (_job) => {
      // TECHNICAL_DEBT: OScheduledJobsManager.onEditCron — cron edit UI not
      // yet implemented. Placeholder: no-op. Future: show edit dialog.
    },
    remove: (job) => deleteMutation.mutate(job),
    runNow: (job) => {
      void apiClient.post(`/api/agents/${job.agent_name}/run`, {});
    },
    create: async (payload) => { await createMutation.mutateAsync(payload); },
  };
}
