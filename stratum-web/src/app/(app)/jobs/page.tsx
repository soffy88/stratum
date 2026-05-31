"use client";

import { useState } from "react";
import { OScheduledJobsManager } from "@helios/blocks";
import { useScheduledJobs } from "@/lib/adapters/jobs";

export default function JobsPage() {
  const { jobs, isLoading, toggleEnabled, editCron, remove, runNow, create } =
    useScheduledJobs();
  const [showCreate, setShowCreate] = useState(false);

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">定时任务</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm"
        >
          新建
        </button>
      </div>

      {showCreate && (
        <CreateJobForm
          onDone={async (payload) => {
            await create(payload);
            setShowCreate(false);
          }}
        />
      )}

      <OScheduledJobsManager
        jobs={jobs}
        onToggleEnabled={toggleEnabled}
        onEditCron={editCron}
        onDelete={remove}
        onRunNow={runNow}
      />
    </div>
  );
}

function CreateJobForm({
  onDone,
}: {
  onDone: (payload: {
    name: string;
    agent_name: string;
    cron_expression: string;
  }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [agentName, setAgentName] = useState("daily_digest");
  const [cron, setCron] = useState("0 8 * * *");
  const [pending, setPending] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setPending(true);
    try {
      await onDone({ name, agent_name: agentName, cron_expression: cron });
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="p-4 border border-[var(--color-border)] rounded mb-4 space-y-3">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="任务名称"
        className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm"
      />
      <select
        value={agentName}
        onChange={(e) => setAgentName(e.target.value)}
        className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm"
      >
        <option value="daily_digest">daily_digest</option>
        <option value="weekly_review">weekly_review</option>
        <option value="reading_companion">reading_companion</option>
      </select>
      <input
        value={cron}
        onChange={(e) => setCron(e.target.value)}
        placeholder="Cron 表达式 (例: 0 8 * * *)"
        className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm font-mono"
      />
      <button
        onClick={handleCreate}
        disabled={!name.trim() || pending}
        className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50"
      >
        {pending ? "创建中..." : "创建"}
      </button>
    </div>
  );
}
