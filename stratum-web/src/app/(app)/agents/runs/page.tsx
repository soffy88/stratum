"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { AGENT_OPTIONS } from "@/lib/agent-options";

type RunItem = {
  id: string;
  agent_name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
};

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "completed"
      ? "bg-green-100 text-green-800"
      : status === "failed"
        ? "bg-red-100 text-red-800"
        : status === "running"
          ? "bg-blue-100 text-blue-800"
          : "bg-gray-100 text-gray-700";
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${cls}`}>
      {status}
    </span>
  );
}

export default function RunsListPage() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    const url =
      filter === "all"
        ? "/api/v1/agents/runs"
        : `/api/v1/agents/runs?agent=${filter}`;
    apiClient
      .get<{ items: RunItem[] }>(url)
      .then((d) => { setRuns(d.items ?? []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filter]);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Agent 运行历史</h1>
        <Link
          href="/ai"
          className="text-sm text-[var(--color-muted)] hover:underline"
        >
          ← AI 助手
        </Link>
      </div>

      <select
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4 border border-[var(--color-border)] rounded px-3 py-1.5 text-sm"
      >
        <option value="all">所有 Agent</option>
        {AGENT_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {loading ? (
        <p className="text-sm text-[var(--color-muted)]">加载中...</p>
      ) : runs.length === 0 ? (
        <p className="text-sm text-[var(--color-muted)]">
          还没有运行记录。去{" "}
          <Link href="/ai" className="underline hover:text-[var(--color-primary)]">
            AI 助手
          </Link>
          {" "}运行一个 Agent。
        </p>
      ) : (
        <div className="space-y-2">
          {runs.map((r) => (
            <Link
              key={r.id}
              href={`/agents/runs/${r.id}`}
              className="flex items-center justify-between p-3 border border-[var(--color-border)] rounded bg-[var(--color-surface)] hover:bg-[var(--color-border)]/30 transition text-sm"
            >
              <div>
                <span className="font-medium">{r.agent_name}</span>
                <span className="text-xs text-[var(--color-muted)] ml-3">
                  {r.started_at?.slice(0, 19).replace("T", " ") ?? "—"}
                </span>
              </div>
              <StatusBadge status={r.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
