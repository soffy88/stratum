/**
 * /cross-books/[collectionId]/gaps — 知识缺口页。
 */
'use client';

import { useEffect } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { GradeDot } from '@/aii/components/GradeMarkers';
import Link from 'next/link';

interface KnowledgeGap {
  gap_id: string;
  type: string;
  description: string;
  affected_books: string[];
  related_concepts: string[];
  confidence: number;
}

const TYPE_LABELS: Record<string, string> = {
  UNANSWERED: '未回答问题',
  BOOK_SET_LIMIT: '书籍集合限制',
  WEAK_EVIDENCE: '证据薄弱',
  MISSING_CONCEPT: '概念缺失',
  UNKNOWN: '未知',
};

const TYPE_ICONS: Record<string, string> = {
  UNANSWERED: '❓',
  BOOK_SET_LIMIT: '📚',
  WEAK_EVIDENCE: '📉',
  MISSING_CONCEPT: '🧩',
  UNKNOWN: '❓',
};

export default function CrossBookGapsPage({ params }: { params: { collectionId: string } }) {
  const [state, run] = useApi((id: string) => api.getKnowledgeGaps(id));

  useEffect(() => {
    void run(params.collectionId);
  }, [params.collectionId, run]);

  const items = (state.data as KnowledgeGap[]) || [];

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-2">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <Link href={`/cross-books/${params.collectionId}`} className="hover:text-[color:var(--foreground)]">概览</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">知识缺口</span>
        </nav>
        <h1 className="text-xl font-semibold">知识缺口 ({items.length})</h1>
      </header>

      {state.loading && <OLoadingState rows={6} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.collectionId)} />}
      {!state.loading && items.length === 0 && <OEmptyState title="无知识缺口" description="当前书籍集合覆盖完整" />}

      {!state.loading && items.length > 0 && (
        <div className="flex flex-col gap-3">
          {items.map((g) => (
            <div
              key={g.gap_id}
              className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4 flex flex-col gap-3"
            >
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-2xl">{TYPE_ICONS[g.type] || '❓'}</span>
                <span className="px-2 py-0.5 rounded text-xs font-medium border border-[color:var(--border)]">
                  {TYPE_LABELS[g.type] || g.type}
                </span>
                <GradeDot grade={g.confidence >= 0.7 ? 'high' : g.confidence >= 0.4 ? 'moderate' : 'low'} size={8} />
                <span className="text-xs text-[color:var(--text-tertiary)]">
                  置信度: {Math.round(g.confidence * 100)}%
                </span>
                <span className="flex-1" />
                <span className="text-xs text-[color:var(--text-tertiary)]">
                  影响: {g.affected_books.join(', ')}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-[color:var(--foreground)]">{g.description}</p>
              {g.related_concepts.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs text-[color:var(--text-tertiary)]">相关概念:</span>
                  {g.related_concepts.map((c) => (
                    <Link
                      key={c}
                      href={`/knowledge?ku=${c}`}
                      className="px-2 py-0.5 text-xs rounded border border-[color:var(--border)] bg-[color:var(--card)] hover:border-[color:var(--accent)]"
                    >
                      {c}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}