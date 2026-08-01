"use client";

import { useState } from "react";
import { OSemanticSearch } from "@helios/blocks";
import { useStratumSearch } from "@/lib/adapters/search";
import { SearchPanel } from "@/components/SearchPanel";
import { ViewSwitcher } from "@/components/ViewSwitcher";
import { retrieve } from "@/lib/adapters/retrieval";
import type {
  RetrieveResponse,
  RetrievalResult,
  TrajectoryStep,
} from "@/lib/adapters/retrieval";

type SearchMode = "simple" | "advanced";
type AdvancedMode = "search" | "retrieval";

// ---------------------------------------------------------------------------
// Trajectory visualization
// ---------------------------------------------------------------------------

const PHASE_COLORS: Record<string, string> = {
  coarse: "bg-blue-500",
  expand: "bg-amber-500",
  drill: "bg-emerald-500",
};

const PHASE_LABELS: Record<string, string> = {
  coarse: "粗筛",
  expand: "扩展",
  drill: "精钻",
};

function TrajectoryBar({ steps, totalMs }: { steps: TrajectoryStep[]; totalMs: number }) {
  return (
    <div className="space-y-2">
      {/* bar */}
      <div className="flex h-3 rounded-full overflow-hidden bg-[var(--color-border)]">
        {steps.map((s) => (
          <div
            key={s.phase}
            className={`${PHASE_COLORS[s.phase] ?? "bg-gray-500"} transition-all`}
            style={{ width: `${Math.max((s.duration_ms / totalMs) * 100, 4)}%` }}
            title={`${PHASE_LABELS[s.phase] ?? s.phase}: ${s.duration_ms}ms (${s.result_count} results)`}
          />
        ))}
      </div>
      {/* legend */}
      <div className="flex flex-wrap gap-3 text-xs text-[var(--color-muted)]">
        {steps.map((s) => (
          <span key={s.phase} className="flex items-center gap-1">
            <span className={`inline-block w-2 h-2 rounded-full ${PHASE_COLORS[s.phase] ?? "bg-gray-500"}`} />
            {PHASE_LABELS[s.phase] ?? s.phase} {s.duration_ms}ms
            {s.siblings_added != null ? ` (+${s.siblings_added})` : ""} · {s.result_count}条
          </span>
        ))}
      </div>
      {/* total latency */}
      <p className="text-xs text-[var(--color-muted)]">
        检索耗时: {totalMs}ms ({steps.map((s) => `${PHASE_LABELS[s.phase] ?? s.phase} ${s.duration_ms}ms`).join(" + ")})
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rerank badge
// ---------------------------------------------------------------------------

function RerankBadge({ score }: { score: number | null }) {
  if (score == null) return null;
  const color =
    score > 5
      ? "bg-emerald-500/20 text-emerald-400"
      : score >= 3
        ? "bg-amber-500/20 text-amber-400"
        : "bg-red-500/20 text-red-400";
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Retrieval result card
// ---------------------------------------------------------------------------

function RetrievalCard({ item, useRerank }: { item: RetrievalResult; useRerank: boolean }) {
  return (
    <div className="p-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-[var(--color-foreground)]">{item.title}</span>
        <div className="flex items-center gap-2 shrink-0">
          {useRerank && <RerankBadge score={item.rerank_score} />}
          <span className="text-xs text-[var(--color-muted)] font-mono">
            {(item.score * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <p className="text-sm text-[var(--color-muted)] mt-1">{item.l0_summary}</p>
      {item.l1_summary && (
        <p className="text-sm text-[var(--color-foreground)]/70 mt-1.5 border-l-2 border-[var(--color-border)] pl-2">
          {item.l1_summary}
        </p>
      )}
      {item.source_path && (
        <p className="text-xs text-[var(--color-muted)] mt-1.5">📎 {item.source_path}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Retrieval panel (advanced retrieval mode)
// ---------------------------------------------------------------------------

function RetrievalPanel() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<RetrieveResponse | null>(null);
  const [error, setError] = useState(false);
  const [useRerank, setUseRerank] = useState(true);
  const [maxResults, setMaxResults] = useState(10);
  const [viewFilter, setViewFilter] = useState<Record<string, unknown>>({});

  async function doSearch() {
    if (!query.trim()) return;
    setLoading(true);
    setError(false);
    setResponse(null);
    const res = await retrieve(query, {
      max_results: maxResults,
      use_rerank: useRerank,
    });
    if (res) {
      setResponse(res);
    } else {
      setError(true);
    }
    setLoading(false);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm text-[var(--color-muted)]">
        <span>视角:</span>
        <ViewSwitcher onViewChange={setViewFilter} />
      </div>

      {/* search input */}
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && doSearch()}
        placeholder="输入检索内容..."
        className="w-full p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted)]"
      />

      {/* options */}
      <div className="flex flex-wrap items-center gap-4 text-sm text-[var(--color-muted)]">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={useRerank}
            onChange={(e) => setUseRerank(e.target.checked)}
          />
          Rerank
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <span>最大结果: {maxResults}</span>
          <input
            type="range"
            min={5}
            max={50}
            step={5}
            value={maxResults}
            onChange={(e) => setMaxResults(Number(e.target.value))}
            className="w-24 accent-[var(--color-primary)]"
          />
        </label>
      </div>

      {/* loading / error */}
      {loading && <p className="text-[var(--color-muted)]">检索中…</p>}
      {error && <p className="text-red-400 text-sm">检索失败，请重试</p>}

      {/* results */}
      {response && (
        <div className="space-y-4">
          {/* trajectory */}
          <TrajectoryBar steps={response.trajectory.steps} totalMs={response.trajectory.total_ms} />

          {/* result list */}
          <div className="space-y-2">
            {response.results.length === 0 && (
              <p className="text-[var(--color-muted)] text-sm">无匹配结果</p>
            )}
            {response.results.map((item, i) => (
              <RetrievalCard key={`${item.substrate_id}-${i}`} item={item} useRerank={useRerank} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SearchPage() {
  const onSearch = useStratumSearch();
  const [mode, setMode] = useState<SearchMode>("simple");
  const [advancedMode, setAdvancedMode] = useState<AdvancedMode>("search");

  return (
    <div className="max-w-4xl mx-auto">
      {/* mode toggle */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">搜索</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMode(mode === "simple" ? "advanced" : "simple")}
            className="text-sm text-[var(--color-muted)] border border-[var(--color-border)] px-3 py-1 rounded hover:bg-[var(--color-border)] transition"
          >
            {mode === "simple" ? "高级搜索" : "基础搜索"}
          </button>
        </div>
      </div>

      {/* simple mode */}
      {mode === "simple" && (
        <OSemanticSearch onSearch={onSearch} placeholder="输入搜索内容..." />
      )}

      {/* advanced mode */}
      {mode === "advanced" && (
        <div className="space-y-3">
          {/* sub-mode toggle */}
          <div className="flex gap-1 p-0.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] w-fit">
            <button
              onClick={() => setAdvancedMode("search")}
              className={`text-sm px-3 py-1 rounded-md transition ${
                advancedMode === "search"
                  ? "bg-[var(--color-primary)] text-white"
                  : "text-[var(--color-muted)] hover:text-[var(--color-foreground)]"
              }`}
            >
              搜索
            </button>
            <button
              onClick={() => setAdvancedMode("retrieval")}
              className={`text-sm px-3 py-1 rounded-md transition flex items-center gap-1 ${
                advancedMode === "retrieval"
                  ? "bg-[var(--color-primary)] text-white"
                  : "text-[var(--color-muted)] hover:text-[var(--color-foreground)]"
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              检索
            </button>
          </div>

          {advancedMode === "search" ? (
            <SearchPanel />
          ) : (
            <RetrievalPanel />
          )}
        </div>
      )}
    </div>
  );
}
