"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { RunAgentResponse, AgentRunsResponse, AgentRun } from "@/lib/types";

type Tab = "qa" | "summary";

export default function AIPage() {
  const [tab, setTab] = useState<Tab>("qa");

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">AI 助手</h1>

      <div className="flex gap-4 border-b border-[var(--color-border)] mb-6">
        <TabButton active={tab === "qa"} onClick={() => setTab("qa")}>问答</TabButton>
        <TabButton active={tab === "summary"} onClick={() => setTab("summary")}>摘要</TabButton>
      </div>

      {tab === "qa" && <QAPanel />}
      {tab === "summary" && <SummaryPanel />}
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`pb-2 px-1 text-sm font-medium border-b-2 ${
        active ? "border-[var(--color-primary)] text-[var(--color-foreground)]" : "border-transparent text-[var(--color-muted)]"
      }`}
    >
      {children}
    </button>
  );
}

function QAPanel() {
  const [question, setQuestion] = useState("");

  const qaMutation = useMutation({
    mutationFn: (query: string) =>
      apiClient.post<RunAgentResponse>("/api/agents/reading_companion/run", { params: { query } }),
  });

  const handleAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    qaMutation.mutate(question);
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleAsk} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="问一个关于你的文档的问题..."
          className="flex-1 border border-[var(--color-border)] rounded px-3 py-2"
        />
        <button
          type="submit"
          disabled={qaMutation.isPending}
          className="px-4 py-2 bg-[var(--color-primary)] text-white rounded disabled:opacity-50"
        >
          {qaMutation.isPending ? "思考中..." : "提问"}
        </button>
      </form>

      {qaMutation.error && (
        <p className="text-red-600">错误: {qaMutation.error.message}</p>
      )}

      {qaMutation.data && (
        <div className="p-4 border border-[var(--color-border)] rounded">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs px-1.5 py-0.5 bg-[var(--color-border)] rounded">
              {qaMutation.data.agent_run.status}
            </span>
            <span className="text-xs text-[var(--color-muted)]">
              {qaMutation.data.agent_run.agent_name}
            </span>
          </div>
          {qaMutation.data.agent_run.output ? (
            <p className="whitespace-pre-wrap">{qaMutation.data.agent_run.output}</p>
          ) : (
            <p className="text-[var(--color-muted)]">{qaMutation.data.message}</p>
          )}
        </div>
      )}
    </div>
  );
}

function SummaryPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["agent-runs-digest"],
    queryFn: () => apiClient.get<AgentRunsResponse>("/api/agents/runs?agent=daily_digest"),
  });

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;
  if (error) return <p className="text-red-600">加载失败</p>;

  const runs = data?.items ?? [];
  if (runs.length === 0) return <p className="text-[var(--color-muted)]">暂无摘要记录</p>;

  return (
    <div className="space-y-3">
      {runs.map((run: AgentRun) => (
        <div key={run.id} className="p-4 border border-[var(--color-border)] rounded">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs px-1.5 py-0.5 bg-[var(--color-border)] rounded">{run.status}</span>
            {run.started_at && <span className="text-xs text-[var(--color-muted)]">{new Date(run.started_at).toLocaleDateString()}</span>}
          </div>
          {run.output ? (
            <p className="whitespace-pre-wrap text-sm">{run.output}</p>
          ) : (
            <p className="text-sm text-[var(--color-muted)]">无输出</p>
          )}
        </div>
      ))}
    </div>
  );
}
