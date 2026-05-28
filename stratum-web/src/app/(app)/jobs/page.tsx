"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { ScheduledJobsResponse, ScheduledJob } from "@/lib/types";

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: () => apiClient.get<ScheduledJobsResponse>("/api/scheduled_jobs"),
  });

  const toggleJob = useMutation({
    mutationFn: (job: ScheduledJob) =>
      apiClient.put(`/api/scheduled_jobs/${job.id}`, { enabled: !job.enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] }),
  });

  const deleteJob = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/scheduled_jobs/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] }),
  });

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">定时任务</h1>
        <button onClick={() => setShowCreate(!showCreate)} className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm">
          新建
        </button>
      </div>

      {showCreate && <CreateJobForm onDone={() => { setShowCreate(false); queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] }); }} />}

      <div className="space-y-2">
        {data?.items.map((job) => (
          <div key={job.id} className="flex items-center justify-between p-3 border border-[var(--color-border)] rounded">
            <div>
              <span className="font-medium">{job.name}</span>
              <span className="ml-2 text-xs text-[var(--color-muted)]">{job.agent_name} · {job.cron_expression}</span>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => toggleJob.mutate(job)} className={`text-xs px-2 py-1 rounded ${job.enabled ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                {job.enabled ? "启用" : "禁用"}
              </button>
              <button onClick={() => deleteJob.mutate(job.id)} className="text-xs text-red-600 hover:underline">删除</button>
            </div>
          </div>
        ))}
        {data?.items.length === 0 && <p className="text-[var(--color-muted)]">暂无定时任务</p>}
      </div>
    </div>
  );
}

function CreateJobForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [agentName, setAgentName] = useState("daily_digest");
  const [cron, setCron] = useState("0 8 * * *");

  const create = useMutation({
    mutationFn: () => apiClient.post("/api/scheduled_jobs", { name, agent_name: agentName, cron_expression: cron }),
    onSuccess: onDone,
  });

  return (
    <div className="p-4 border border-[var(--color-border)] rounded mb-4 space-y-3">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="任务名称" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
      <input value={agentName} onChange={(e) => setAgentName(e.target.value)} placeholder="Agent 名称" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
      <input value={cron} onChange={(e) => setCron(e.target.value)} placeholder="Cron 表达式" className="w-full border border-[var(--color-border)] rounded px-3 py-2" />
      <button onClick={() => create.mutate()} disabled={!name} className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50">创建</button>
    </div>
  );
}
