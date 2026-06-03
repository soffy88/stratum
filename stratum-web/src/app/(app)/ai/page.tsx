"use client";

import { useState } from "react";
import Link from "next/link";
import { OAIQAPanel, OAISummaryCard } from "@helios/blocks";
import { useAgentQA, useAgentRuns, adaptSummaryCard } from "@/lib/adapters/agents";
import type { AgentRun, RunAgentResponse } from "@/lib/types";
import { AGENT_OPTIONS } from "@/lib/agent-options";

type Tab = "qa" | "summary" | "run";

function AgentRunPanel() {
  const [agentName, setAgentName] = useState("daily_digest");
  const [result, setResult] = useState<RunAgentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const runs = useAgentRuns(agentName);

  async function runAgent() {
    setLoading(true);
    setResult(null);
    const res = await fetch(`/api/v1/agents/${agentName}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
      credentials: "include",
    });
    setResult(await res.json());
    setLoading(false);
    // Refresh run history after run completes
    void runs.refetch();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select
          value={agentName}
          onChange={(e) => setAgentName(e.target.value)}
          className="border border-[var(--color-border)] rounded px-3 py-1.5 text-sm"
        >
          {AGENT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <button
          onClick={runAgent}
          disabled={loading}
          className="px-4 py-1.5 bg-[var(--color-accent)] text-white rounded text-sm disabled:opacity-50"
        >
          {loading ? "运行中…" : "运行"}
        </button>
      </div>

      {result && (
        <div className="p-3 border border-[var(--color-border)] rounded bg-[var(--color-surface)] text-sm">
          <p className="font-medium mb-1">
            状态:{" "}
            <span
              className={
                result.status === "completed" ? "text-green-600" : "text-red-600"
              }
            >
              {result.status}
            </span>
          </p>
          {result.run_id && (
            <p className="text-xs text-[var(--color-muted)] mb-2">
              Run ID:{" "}
              <Link
                href={`/agents/runs/${result.run_id}`}
                className="underline hover:text-[var(--color-primary)]"
              >
                {result.run_id}
              </Link>
            </p>
          )}
          {result.findings != null && (
            <pre className="text-xs overflow-auto max-h-64 whitespace-pre-wrap mt-1">
              {JSON.stringify(result.findings, null, 2)}
            </pre>
          )}
          {result.error != null && (
            <p className="text-red-500 text-xs mt-1">{String(result.error)}</p>
          )}
        </div>
      )}

      {/* Run history for selected agent */}
      <div className="mt-4">
        <h3 className="text-sm font-medium text-[var(--color-muted)] mb-2">
          历史运行记录
        </h3>
        {runs.isLoading && (
          <p className="text-xs text-[var(--color-muted)]">加载中...</p>
        )}
        {!runs.isLoading && (runs.data?.items ?? []).length === 0 && (
          <p className="text-xs text-[var(--color-muted)]">暂无运行记录</p>
        )}
        <div className="space-y-1">
          {(runs.data?.items ?? []).slice(0, 5).map((run: AgentRun) => (
            <Link
              key={run.id}
              href={`/agents/runs/${run.id}`}
              className="flex items-center justify-between p-2 border border-[var(--color-border)] rounded text-xs hover:bg-[var(--color-surface)] transition"
            >
              <span
                className={
                  run.status === "completed" ? "text-green-600" : "text-[var(--color-muted)]"
                }
              >
                {run.status}
              </span>
              <span className="text-[var(--color-muted)]">
                {run.started_at?.slice(0, 19).replace("T", " ") ?? "—"}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function AIPage() {
  const [tab, setTab] = useState<Tab>("qa");
  const onAsk = useAgentQA();
  const runs = useAgentRuns("daily_digest");

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">AI 助手</h1>

      <div className="flex gap-4 border-b border-[var(--color-border)] mb-6">
        <TabBtn active={tab === "qa"} onClick={() => setTab("qa")}>问答</TabBtn>
        <TabBtn active={tab === "summary"} onClick={() => setTab("summary")}>摘要</TabBtn>
        <TabBtn active={tab === "run"} onClick={() => setTab("run")}>运行 Agent</TabBtn>
      </div>

      {tab === "qa" && (
        <OAIQAPanel
          onAsk={onAsk}
          placeholder="问一个关于你的文档的问题..."
        />
      )}

      {tab === "summary" && (
        <div className="space-y-3">
          {runs.isLoading && (
            <p className="text-sm text-[var(--color-muted)]">加载中...</p>
          )}
          {!runs.isLoading && (runs.data?.items ?? []).length === 0 && (
            <p className="text-sm text-[var(--color-muted)]">暂无摘要记录</p>
          )}
          {(runs.data?.items ?? []).map((run: AgentRun) => {
            const props = adaptSummaryCard(run);
            return (
              <OAISummaryCard
                key={run.id}
                summary={props.summary}
                date={props.date}
                digestSent={props.digestSent}
                citations={props.citations}
              />
            );
          })}
        </div>
      )}

      {tab === "run" && <AgentRunPanel />}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`pb-2 px-1 text-sm font-medium border-b-2 ${
        active
          ? "border-[var(--color-primary)] text-[var(--color-foreground)]"
          : "border-transparent text-[var(--color-muted)]"
      }`}
    >
      {children}
    </button>
  );
}
