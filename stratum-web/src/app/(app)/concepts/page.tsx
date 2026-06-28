"use client";

// 概念来自 AII 的 concept_onto(5632 个,739 个有关联 KU),经 /api/aii 代理读取。
// stratum 自身的 concepts 表为空,故此页改读 AII 概念。
import { useEffect, useState } from "react";

interface Concept { id: string; name: string; ku_count: number; }

export default function ConceptsPage() {
  const [items, setItems] = useState<Concept[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const pageSize = 90;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (q.trim()) params.set("q", q.trim());
    fetch(`/api/aii/api/concepts?${params.toString()}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        const data = d?.data ?? d;
        setItems(data?.items ?? []);
        setTotal(data?.total ?? 0);
      })
      .catch(() => { if (!cancelled) setItems([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [q, page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">概念</h1>
      <p className="text-sm text-[var(--color-muted)] mb-4">
        共 {total.toLocaleString()} 个概念，按关联知识单元数排序。
      </p>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setPage(1); }}
        placeholder="搜索概念…"
        className="w-full md:w-80 border border-[var(--color-border)] rounded px-3 py-2 mb-4 text-sm"
      />
      {loading && <p className="text-[var(--color-muted)]">加载中…</p>}
      {!loading && items.length === 0 && <p className="text-[var(--color-muted)]">暂无概念。</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {items.map((c) => (
          <div
            key={c.id}
            className="flex items-center justify-between p-3 border border-[var(--color-border)] rounded"
          >
            <span className="font-medium truncate" title={c.name}>{c.name}</span>
            <span className="text-xs text-[var(--color-muted)] shrink-0 ml-2 tabular-nums">{c.ku_count} KU</span>
          </div>
        ))}
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-5">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1.5 rounded border border-[var(--color-border)] text-sm disabled:opacity-40">上一页</button>
          <span className="text-sm tabular-nums">{page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1.5 rounded border border-[var(--color-border)] text-sm disabled:opacity-40">下一页</button>
        </div>
      )}
    </div>
  );
}
