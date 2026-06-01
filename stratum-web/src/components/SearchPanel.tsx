"use client";
import { useState } from "react";

interface SearchResult {
  id: string;
  type: string;
  title: string;
  score: number;
  highlight?: string | null;
  citation?: { deep_link?: string } | null;
}

export function SearchPanel() {
  const [queryText, setQueryText] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [mode, setMode] = useState("augmented");
  const [rerank, setRerank] = useState(false);
  const [expand, setExpand] = useState(false);
  const [loading, setLoading] = useState(false);

  async function search() {
    if (!queryText.trim()) return;
    setLoading(true);
    const res = await fetch("/api/v1/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: queryText, mode, top_k: 20, rerank, expand }),
      credentials: "include",
    });
    const data = await res.json();
    setResults(data.results || []);
    setLoading(false);
  }

  return (
    <div className="p-4">
      <input
        value={queryText}
        onChange={(e) => setQueryText(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && search()}
        placeholder="搜索你的知识库..."
        className="w-full p-3 border border-[var(--color-border)] rounded-lg"
      />
      <div className="flex gap-4 mt-2 text-sm text-[var(--color-muted)]">
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="checkbox"
            checked={rerank}
            onChange={(e) => setRerank(e.target.checked)}
          />
          Rerank
        </label>
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="checkbox"
            checked={expand}
            onChange={(e) => setExpand(e.target.checked)}
          />
          Expand
        </label>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="border border-[var(--color-border)] rounded px-1"
        >
          <option value="augmented">Augmented</option>
          <option value="strict">Strict</option>
        </select>
      </div>
      {loading && <p className="mt-4 text-[var(--color-muted)]">搜索中…</p>}
      <div className="mt-4 space-y-3">
        {results.map((r) => (
          <div key={r.id} className="p-3 border border-[var(--color-border)] rounded">
            <div className="flex justify-between items-start">
              <span className="font-medium">{r.title}</span>
              <span className="text-xs bg-[var(--color-border)] px-2 py-0.5 rounded ml-2 shrink-0">
                {r.type}
              </span>
            </div>
            {r.highlight && (
              <p className="text-sm text-[var(--color-muted)] mt-1">{r.highlight}</p>
            )}
            {r.citation?.deep_link && (
              <p className="text-xs text-blue-500 mt-1">📎 {r.citation.deep_link}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
