"use client";

import { useState } from "react";
import { OAIQAPanel, OAISummaryCard } from "@helios/blocks";
import { useAgentQA, useAgentRuns, adaptSummaryCard } from "@/lib/adapters/agents";
import type { AgentRun } from "@/lib/types";

type Tab = "qa" | "summary";

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
