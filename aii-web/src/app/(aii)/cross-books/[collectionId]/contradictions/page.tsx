/**
 * /cross-books/[collectionId]/contradictions — 矛盾检测页。
 */
'use client';

import { use, useEffect } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { GradeDot, gradeTextClass } from '@/aii/components/GradeMarkers';
import Link from 'next/link';

interface Contradiction {
  contradiction_id: string;
  book_a_id: string;
  book_b_id: string;
  type: string;
  element_a: string;
  element_b: string;
  description: string;
  confidence: number;
  evidence: string[];
}

const TYPE_ICONS: Record<string, string> = {
  THEORETICAL_CONFLICT: '⚔️',
  DEFINITIONAL_CONFLICT: '📖',
  EVIDENTIAL_CONFLICT: '📊',
  DIRECT_CONTRADICTION: '❌',
  UNKNOWN: '⚪',
};

const TYPE_COLORS: Record<string, string> = {
  THEORETICAL_CONFLICT: '#dc2626',
  DEFINITIONAL_CONFLICT: '#7c3aed',
  EVIDENTIAL_CONFLICT: '#f59e0b',
  DIRECT_CONTRADICTION: '#ef4444',
  UNKNOWN: '#6b7280',
};

export default function CrossBookContradictionsPage({ params: paramsPromise }: { params: Promise<{ collectionId: string }> }) {
  const params = use(paramsPromise);
  const [state, run] = useApi((id: string) => api.getContradictions(id));

  useEffect(() => {
    void run(params.collectionId);
  }, [params.collectionId, run]);

  const items = (state.data as Contradiction[]) || [];

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-2">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <Link href={`/cross-books/${params.collectionId}`} className="hover:text-[color:var(--foreground)]">概览</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">矛盾检测</span>
        </nav>
        <h1 className="text-xl font-semibold">矛盾检测 ({items.length})</h1>
      </header>

      {state.loading && <OLoadingState rows={6} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.collectionId)} />}
      {!state.loading && items.length === 0 && <OEmptyState title="无矛盾" description="未检测到跨书矛盾" />}

      {!state.loading && items.length > 0 && (
        <div className="flex flex-col gap-3">
          {items.map((c) => (
            <div
              key={c.contradiction_id}
              className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4 flex flex-col gap-3"
              style={{ borderLeft: `4px solid ${TYPE_COLORS[c.type] || TYPE_COLORS.UNKNOWN}` }}
            >
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-2xl">{TYPE_ICONS[c.type] || '⚪'}</span>
                <span className="px-2 py-0.5 rounded text-xs font-medium border" style={{
                  background: `${TYPE_COLORS[c.type] || TYPE_COLORS.UNKNOWN}15`,
                  borderColor: TYPE_COLORS[c.type] || TYPE_COLORS.UNKNOWN,
                  color: TYPE_COLORS[c.type] || TYPE_COLORS.UNKNOWN,
                }}>
                  {c.type}
                </span>
                <GradeDot grade={c.confidence >= 0.7 ? 'high' : c.confidence >= 0.4 ? 'moderate' : 'low'} size={8} />
                <span className="text-xs text-[color:var(--text-tertiary)]">
                  置信度: {Math.round(c.confidence * 100)}%
                </span>
                <span className="flex-1" />
                <span className="text-xs text-[color:var(--text-tertiary)] font-mono">
                  {c.book_a_id} ↔ {c.book_b_id}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded bg-[color:var(--background)] border border-[color:var(--border)]">
                  <p className="text-xs text-[color:var(--text-tertiary)] mb-1">要素 A ({c.book_a_id})</p>
                  <p className="font-medium text-sm">{c.element_a}</p>
                </div>
                <div className="p-3 rounded bg-[color:var(--background)] border border-[color:var(--border)]">
                  <p className="text-xs text-[color:var(--text-tertiary)] mb-1">要素 B ({c.book_b_id})</p>
                  <p className="font-medium text-sm">{c.element_b}</p>
                </div>
              </div>
              <p className="text-sm leading-relaxed text-[color:var(--foreground)]">{c.description}</p>
              {c.evidence.length > 0 && (
                <details className="text-sm">
                  <summary className="text-[color:var(--text-secondary)] cursor-pointer">证据 ({c.evidence.length})</summary>
                  <ul className="mt-2 flex flex-col gap-1 ml-4">
                    {c.evidence.map((e, i) => (
                      <li key={i} className="text-[color:var(--text-tertiary)] font-mono text-xs">{e}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}