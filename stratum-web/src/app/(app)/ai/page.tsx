"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { OAIQAPanel, OAISummaryCard } from "@helios/blocks";
import { useAgentQA, useAgentRuns, adaptSummaryCard } from "@/lib/adapters/agents";
import { apiClient } from "@/lib/api-client";
import type { AgentRun, RunAgentResponse } from "@/lib/types";
import { AGENT_OPTIONS } from "@/lib/agent-options";

type Tab = "qa" | "summary" | "run";

// ── D1: Agent info cards ──────────────────────────────────────────────────────

function AgentInfoCards({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (value: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
      {AGENT_OPTIONS.map((agent) => (
        <button
          key={agent.value}
          onClick={() => onSelect(agent.value)}
          className={`text-left p-4 border rounded transition ${
            selected === agent.value
              ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
              : "border-[var(--color-border)] hover:border-[var(--color-primary)]/50 hover:bg-[var(--color-surface)]"
          }`}
        >
          <h3 className="font-semibold text-sm">{agent.label}</h3>
          <p className="text-xs text-[var(--color-muted)] mt-1">{agent.description}</p>
          {agent.requiresParam && (
            <span className="text-xs text-amber-600 mt-2 inline-block">
              需要参数: {agent.requiresParam}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// ── D2: Param inputs ──────────────────────────────────────────────────────────

function AgentParamsForm({
  agentName,
  question,
  substrateId,
  onQuestion,
  onSubstrateId,
}: {
  agentName: string;
  question: string;
  substrateId: string;
  onQuestion: (v: string) => void;
  onSubstrateId: (v: string) => void;
}) {
  const agent = AGENT_OPTIONS.find((o) => o.value === agentName);
  if (!agent?.requiresParam) return null;

  if (agent.requiresParam === "question") {
    return (
      <input
        type="text"
        placeholder="输入你的问题..."
        value={question}
        onChange={(e) => onQuestion(e.target.value)}
        className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm mb-3 bg-[var(--color-surface)]"
      />
    );
  }

  if (agent.requiresParam === "substrate_id") {
    return (
      <input
        type="text"
        placeholder="输入 substrate_id (在文档详情页 URL 中复制)"
        value={substrateId}
        onChange={(e) => onSubstrateId(e.target.value)}
        className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm mb-3 bg-[var(--color-surface)]"
      />
    );
  }

  return null;
}

// ── D3: Inline run result ─────────────────────────────────────────────────────

type CitationLike = { text_excerpt?: string; substrate_id?: string; deep_link?: string };

function RunResult({ result }: { result: RunAgentResponse }) {
  return (
    <div className="mt-4 p-4 border border-[var(--color-border)] rounded bg-[var(--color-surface)]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium">运行结果</span>
        <span
          className={`text-xs px-2 py-0.5 rounded font-medium ${
            result.status === "completed"
              ? "bg-green-100 text-green-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          {result.status}
        </span>
      </div>

      {result.findings != null && (
        <div className="mb-3">
          <h4 className="text-xs font-semibold text-[var(--color-muted)] mb-1">Findings</h4>
          {typeof result.findings === "string" ? (
            <p className="text-sm whitespace-pre-wrap">{result.findings}</p>
          ) : (
            <pre className="text-xs bg-[var(--color-background)] border border-[var(--color-border)] rounded p-2 overflow-auto max-h-48 whitespace-pre-wrap">
              {JSON.stringify(result.findings, null, 2)}
            </pre>
          )}
        </div>
      )}

      {result.citations != null && (result.citations as unknown[]).length > 0 && (
        <div className="mb-3">
          <h4 className="text-xs font-semibold text-[var(--color-muted)] mb-1">引用</h4>
          <ul className="space-y-1">
            {(result.citations as CitationLike[]).map((c, i) => (
              <li key={i} className="text-xs">
                {c.deep_link ? (
                  <a
                    href={c.deep_link}
                    className="text-[var(--color-primary)] hover:underline"
                  >
                    {c.text_excerpt ?? c.substrate_id ?? c.deep_link}
                  </a>
                ) : (
                  <span className="text-[var(--color-muted)]">
                    {c.text_excerpt ?? c.substrate_id ?? JSON.stringify(c)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.error && (
        <p className="text-xs text-red-600 mb-2">{String(result.error)}</p>
      )}

      {result.run_id && (
        <Link
          href={`/agents/runs/${result.run_id}`}
          className="text-xs text-[var(--color-primary)] hover:underline"
        >
          查看完整详情 →
        </Link>
      )}
    </div>
  );
}

// ── D4: Recent runs (cross-agent, last 5) ────────────────────────────────────

function RecentRuns() {
  const [runs, setRuns] = useState<AgentRun[]>([]);

  useEffect(() => {
    apiClient
      .get<{ items: AgentRun[] }>("/api/v1/agents/runs?limit=5")
      .then((d) => setRuns(d.items ?? []))
      .catch(() => {});
  }, []);

  if (runs.length === 0) return null;

  return (
    <div className="mt-8 pt-6 border-t border-[var(--color-border)]">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium">最近运行</h3>
        <Link
          href="/agents/runs"
          className="text-xs text-[var(--color-muted)] hover:underline"
        >
          查看全部 →
        </Link>
      </div>
      <div className="space-y-1">
        {runs.map((r) => (
          <Link
            key={r.id}
            href={`/agents/runs/${r.id}`}
            className="flex items-center justify-between p-2 border border-[var(--color-border)] rounded text-xs hover:bg-[var(--color-surface)] transition"
          >
            <span className="font-medium">{r.agent_name}</span>
            <div className="flex items-center gap-3">
              <span className="text-[var(--color-muted)]">
                {r.started_at?.slice(0, 19).replace("T", " ") ?? "—"}
              </span>
              <span
                className={
                  r.status === "completed"
                    ? "text-green-600"
                    : r.status === "failed"
                      ? "text-red-600"
                      : "text-[var(--color-muted)]"
                }
              >
                {r.status}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ── AgentRunPanel (D1+D2+D3+D4 integrated) ───────────────────────────────────

function AgentRunPanel() {
  const [agentName, setAgentName] = useState("daily_digest");
  const [question, setQuestion] = useState("");
  const [substrateId, setSubstrateId] = useState("");
  const [result, setResult] = useState<RunAgentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const runs = useAgentRuns(agentName);

  function buildBody() {
    const agent = AGENT_OPTIONS.find((o) => o.value === agentName);
    if (!agent?.requiresParam) return {};
    if (agent.requiresParam === "question" && question.trim()) {
      return { input: { question: question.trim() } };
    }
    if (agent.requiresParam === "substrate_id" && substrateId.trim()) {
      return { input: { substrate_id: substrateId.trim() } };
    }
    return {};
  }

  async function runAgent() {
    setLoading(true);
    setResult(null);
    try {
      const data = await apiClient.post<RunAgentResponse>(
        `/api/v1/agents/${agentName}/run`,
        buildBody(),
      );
      setResult(data);
      void runs.refetch();
    } catch {
      setResult({ run_id: "", agent_name: agentName, status: "failed", error: "请求失败" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      {/* D1 */}
      <AgentInfoCards selected={agentName} onSelect={(v) => { setAgentName(v); setResult(null); }} />

      {/* D2 */}
      <AgentParamsForm
        agentName={agentName}
        question={question}
        substrateId={substrateId}
        onQuestion={setQuestion}
        onSubstrateId={setSubstrateId}
      />

      <button
        onClick={runAgent}
        disabled={loading}
        className="px-5 py-2 bg-[var(--color-accent)] text-white rounded text-sm disabled:opacity-50"
      >
        {loading ? "运行中…" : `运行 ${AGENT_OPTIONS.find((o) => o.value === agentName)?.label ?? agentName}`}
      </button>

      {/* D3 */}
      {result && <RunResult result={result} />}

      {/* Per-agent recent history (existing behaviour) */}
      <div className="mt-6">
        <h3 className="text-xs font-medium text-[var(--color-muted)] mb-2">
          {AGENT_OPTIONS.find((o) => o.value === agentName)?.label} 历史
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
              <span className={run.status === "completed" ? "text-green-600" : "text-[var(--color-muted)]"}>
                {run.status}
              </span>
              <span className="text-[var(--color-muted)]">
                {run.started_at?.slice(0, 19).replace("T", " ") ?? "—"}
              </span>
            </Link>
          ))}
        </div>
      </div>

      {/* D4 */}
      <RecentRuns />
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AIPage() {
  const [tab, setTab] = useState<Tab>("qa");
  const onAsk = useAgentQA();
  const runs = useAgentRuns("daily_digest");

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">AI 助手</h1>

      <div className="flex items-end justify-between border-b border-[var(--color-border)] mb-6">
        <div className="flex gap-4">
          <TabBtn active={tab === "qa"} onClick={() => setTab("qa")}>问答</TabBtn>
          <TabBtn active={tab === "summary"} onClick={() => setTab("summary")}>摘要</TabBtn>
          <TabBtn active={tab === "run"} onClick={() => setTab("run")}>运行 Agent</TabBtn>
        </div>
        <Link
          href="/agents/runs"
          className="text-xs text-[var(--color-muted)] hover:underline pb-2"
        >
          查看运行历史 →
        </Link>
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
