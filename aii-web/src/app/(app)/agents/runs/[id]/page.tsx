"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAgentRunDetail } from "@/lib/adapters/agents";

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "completed"
      ? "bg-green-100 text-green-800"
      : status === "failed"
        ? "bg-red-100 text-red-800"
        : status === "running"
          ? "bg-blue-100 text-blue-800"
          : "bg-gray-100 text-gray-700";
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${color}`}>
      {status}
    </span>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  if (value == null) return null;
  return (
    <section className="mt-4">
      <h2 className="text-sm font-semibold text-[var(--color-muted)] mb-1">
        {label}
      </h2>
      <pre className="text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded p-3 overflow-auto max-h-72 whitespace-pre-wrap">
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </section>
  );
}

export default function AgentRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: run, isLoading, error } = useAgentRunDetail(id ?? "");

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <p className="text-[var(--color-muted)] text-sm">加载中...</p>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <p className="text-red-500 text-sm">Agent run 不存在或无权访问</p>
        <button
          onClick={() => router.back()}
          className="mt-3 text-sm underline text-[var(--color-muted)]"
        >
          返回
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <Link
            href="/ai"
            className="text-xs text-[var(--color-muted)] hover:underline"
          >
            ← AI 助手
          </Link>
          <h1 className="text-xl font-semibold mt-1">Agent Run 详情</h1>
        </div>
        <StatusBadge status={run.status} />
      </div>

      {/* Meta */}
      <div className="grid grid-cols-2 gap-2 text-sm border border-[var(--color-border)] rounded p-3 bg-[var(--color-surface)]">
        <div>
          <span className="text-[var(--color-muted)]">Agent</span>
          <p className="font-mono">{run.agent_name}</p>
        </div>
        <div>
          <span className="text-[var(--color-muted)]">Run ID</span>
          <p className="font-mono text-xs">{run.id}</p>
        </div>
        <div>
          <span className="text-[var(--color-muted)]">开始时间</span>
          <p>{run.started_at?.slice(0, 19).replace("T", " ") ?? "—"}</p>
        </div>
        <div>
          <span className="text-[var(--color-muted)]">完成时间</span>
          <p>{run.completed_at?.slice(0, 19).replace("T", " ") ?? "—"}</p>
        </div>
        {run.total_input_tokens != null && (
          <div>
            <span className="text-[var(--color-muted)]">Token 消耗</span>
            <p>
              {run.total_input_tokens}↑ / {run.total_output_tokens}↓
            </p>
          </div>
        )}
        {run.cost_usd != null && run.cost_usd > 0 && (
          <div>
            <span className="text-[var(--color-muted)]">费用</span>
            <p>${run.cost_usd.toFixed(4)}</p>
          </div>
        )}
      </div>

      {/* Error */}
      {run.error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          <span className="font-medium">错误: </span>
          {String(run.error)}
        </div>
      )}

      {/* Content sections */}
      <JsonBlock label="Findings" value={run.findings} />
      <JsonBlock label="Citations" value={run.citations} />
      <JsonBlock label="Trace" value={run.trace} />
      <JsonBlock label="Files Generated" value={run.files_generated} />
    </div>
  );
}
