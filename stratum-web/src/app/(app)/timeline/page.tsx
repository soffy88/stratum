"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";

interface TimelineItem {
  id: string;
  title?: string;
  mime?: string;
  text_excerpt?: string;
  substrate_id?: string;
  created_at: string;
}

interface TimeBucket {
  month: string;
  substrates: TimelineItem[];
  notes: TimelineItem[];
  highlights: TimelineItem[];
}

interface TimelineResponse {
  buckets: TimeBucket[];
}

const MEDIUM_OPTIONS = [
  { value: "", label: "全部" },
  { value: "pdf", label: "PDF" },
  { value: "webpage", label: "网页" },
  { value: "markdown", label: "笔记" },
];

function monthLabel(month: string) {
  const [year, m] = month.split("-");
  return `${year} 年 ${m} 月`;
}

export default function TimelinePage() {
  const [medium, setMedium] = useState("");
  const [expandedMonths, setExpandedMonths] = useState<Set<string>>(new Set());

  const now = new Date();
  const oneYearAgo = new Date(now.getFullYear() - 1, now.getMonth(), 1);

  const { data, isLoading } = useQuery({
    queryKey: ["timeline", medium],
    queryFn: () =>
      apiClient.get<TimelineResponse>(
        `/api/v1/timeline?from_date=${oneYearAgo.toISOString()}&to_date=${now.toISOString()}${medium ? `&medium=${medium}` : ""}`,
      ),
  });

  function toggleMonth(month: string) {
    setExpandedMonths((prev) => {
      const next = new Set(prev);
      if (next.has(month)) next.delete(month);
      else next.add(month);
      return next;
    });
  }

  const buckets = data?.buckets ?? [];

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">时光机</h1>
        <div className="flex gap-1">
          {MEDIUM_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setMedium(opt.value)}
              className={`px-2.5 py-1 text-xs rounded border transition ${
                medium === opt.value
                  ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5 text-[var(--color-primary)]"
                  : "border-[var(--color-border)] hover:bg-[var(--color-surface)]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm text-[var(--color-muted)]">加载中...</p>}

      {!isLoading && buckets.length === 0 && (
        <p className="text-sm text-[var(--color-muted)] text-center py-16">
          最近一年暂无记录
        </p>
      )}

      <div className="space-y-3">
        {buckets.map((bucket) => {
          const total =
            bucket.substrates.length + bucket.notes.length + bucket.highlights.length;
          const expanded = expandedMonths.has(bucket.month);
          return (
            <div
              key={bucket.month}
              className="border border-[var(--color-border)] rounded-lg overflow-hidden"
            >
              <button
                onClick={() => toggleMonth(bucket.month)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-[var(--color-surface)] transition"
              >
                <span className="font-medium text-sm">{monthLabel(bucket.month)}</span>
                <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                  {bucket.substrates.length > 0 && (
                    <span>📄 {bucket.substrates.length} 文档</span>
                  )}
                  {bucket.notes.length > 0 && (
                    <span>📝 {bucket.notes.length} 笔记</span>
                  )}
                  {bucket.highlights.length > 0 && (
                    <span>✏️ {bucket.highlights.length} 高亮</span>
                  )}
                  {total === 0 && <span className="text-[var(--color-muted)]">空</span>}
                  <span>{expanded ? "▲" : "▼"}</span>
                </div>
              </button>

              {expanded && (
                <div className="border-t border-[var(--color-border)] px-4 py-3 space-y-4">
                  {bucket.substrates.length > 0 && (
                    <section>
                      <h3 className="text-xs font-semibold text-[var(--color-muted)] mb-2">
                        文档
                      </h3>
                      <ul className="space-y-1">
                        {bucket.substrates.map((s) => (
                          <li key={s.id}>
                            <Link
                              href={`/documents/${s.id}`}
                              className="text-sm hover:underline"
                            >
                              {s.title || s.id}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                  {bucket.notes.length > 0 && (
                    <section>
                      <h3 className="text-xs font-semibold text-[var(--color-muted)] mb-2">
                        笔记
                      </h3>
                      <ul className="space-y-1">
                        {bucket.notes.map((n) => (
                          <li key={n.id}>
                            <Link href={`/notes/${n.id}`} className="text-sm hover:underline">
                              {n.title || n.id}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                  {bucket.highlights.length > 0 && (
                    <section>
                      <h3 className="text-xs font-semibold text-[var(--color-muted)] mb-2">
                        高亮
                      </h3>
                      <ul className="space-y-1">
                        {bucket.highlights.map((h) => (
                          <li
                            key={h.id}
                            className="text-sm text-[var(--color-muted)] border-l-2 border-[var(--color-border)] pl-2"
                          >
                            {h.text_excerpt || "(无摘录)"}
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
