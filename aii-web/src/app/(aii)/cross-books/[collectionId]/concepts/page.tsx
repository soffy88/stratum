/**
 * /cross-books/[collectionId]/concepts — 概念对齐关系页。
 */
'use client';

import { use, useEffect, useState } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { GradeDot, gradeTextClass } from '@/aii/components/GradeMarkers';
import Link from 'next/link';

interface ConceptRelation {
  relation_id: string;
  source_book_id: string;
  target_book_id: string;
  source_concept_id: string;
  target_concept_id: string;
  relation: string;
  confidence: number;
  evidence: string[];
}

const RELATION_ICONS: Record<string, string> = {
  SAME_CONCEPT: '🟢',
  RELATED_CONCEPT: '🔵',
  ANALOGOUS: '🟡',
  GENERALIZES: '⬆️',
  SPECIALIZES: '⬇️',
  SAME_TERM_DIFFERENT_MEANING: '🔴',
  UNKNOWN: '⚪',
};

export default function CrossBookConceptsPage({ params: paramsPromise }: { params: Promise<{ collectionId: string }> }) {
  const params = use(paramsPromise);
  const [relationFilter, setRelationFilter] = useState<string>('all');
  const [state, run] = useApi((id: string) => api.getConceptRelations(id, relationFilter === 'all' ? undefined : relationFilter));

  useEffect(() => {
    void run(params.collectionId);
  }, [params.collectionId, relationFilter, run]);

  const items = (state.data as ConceptRelation[]) || [];

  const relationTypes = ['all', 'SAME_CONCEPT', 'RELATED_CONCEPT', 'ANALOGOUS', 'GENERALIZES', 'SPECIALIZES', 'SAME_TERM_DIFFERENT_MEANING'];

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-2">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <Link href={`/cross-books/${params.collectionId}`} className="hover:text-[color:var(--foreground)]">概览</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">概念对齐</span>
        </nav>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h1 className="text-xl font-semibold">概念对齐关系 ({items.length})</h1>
          <div className="flex gap-2 flex-wrap">
            {relationTypes.map(r => (
              <button
                key={r}
                onClick={() => setRelationFilter(r)}
                className={`px-3 py-1.5 rounded text-sm border transition-colors ${
                  relationFilter === r
                    ? 'bg-[color:var(--accent)] border-[color:var(--accent)] text-white'
                    : 'border-[color:var(--border)] text-[color:var(--foreground)] hover:border-[color:var(--accent)]'
                }`}
              >
                {r === 'all' ? '全部' : r}
              </button>
            ))}
          </div>
        </div>
      </header>

      {state.loading && <OLoadingState rows={6} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.collectionId)} />}
      {!state.loading && items.length === 0 && <OEmptyState title="无概念关系" description="暂无匹配的概念对齐结果" />}

      {!state.loading && items.length > 0 && (
        <div className="flex flex-col gap-3">
          {items.map((r) => (
            <div
              key={r.relation_id}
              className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4 flex flex-col gap-3"
            >
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-2xl">{RELATION_ICONS[r.relation] || '⚪'}</span>
                <span className="px-2 py-0.5 rounded text-xs font-medium border" style={{
                  background: r.relation === 'SAME_CONCEPT' ? 'rgba(16,185,129,0.15)' :
                    r.relation === 'SAME_TERM_DIFFERENT_MEANING' ? 'rgba(239,68,68,0.15)' :
                    'rgba(37,99,235,0.15)',
                  borderColor: r.relation === 'SAME_CONCEPT' ? '#10b981' :
                    r.relation === 'SAME_TERM_DIFFERENT_MEANING' ? '#ef4444' : '#2563eb',
                  color: r.relation === 'SAME_CONCEPT' ? '#10b981' :
                    r.relation === 'SAME_TERM_DIFFERENT_MEANING' ? '#ef4444' : '#2563eb',
                }}>
                  {r.relation}
                </span>
                <GradeDot grade={r.confidence >= 0.7 ? 'high' : r.confidence >= 0.4 ? 'moderate' : 'low'} size={8} />
                <span className="text-xs text-[color:var(--text-tertiary)]">
                  置信度: {Math.round(r.confidence * 100)}%
                </span>
                <span className="flex-1" />
                <span className="text-xs text-[color:var(--text-tertiary)] font-mono">
                  {r.source_book_id} ↔ {r.target_book_id}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-[color:var(--text-tertiary)] mb-1">源概念</p>
                  <Link
                    href={`/knowledge?ku=${r.source_concept_id}`}
                    className="font-medium text-sm hover:text-[color:var(--accent)]"
                  >
                    {r.source_concept_id}
                  </Link>
                  <p className="text-xs text-[color:var(--text-tertiary)] mt-0.5">{r.source_book_id}</p>
                </div>
                <div>
                  <p className="text-xs text-[color:var(--text-tertiary)] mb-1">目标概念</p>
                  <Link
                    href={`/knowledge?ku=${r.target_concept_id}`}
                    className="font-medium text-sm hover:text-[color:var(--accent)]"
                  >
                    {r.target_concept_id}
                  </Link>
                  <p className="text-xs text-[color:var(--text-tertiary)] mt-0.5">{r.target_book_id}</p>
                </div>
              </div>
              {r.evidence.length > 0 && (
                <details className="text-sm">
                  <summary className="text-[color:var(--text-secondary)] cursor-pointer">证据 ({r.evidence.length})</summary>
                  <ul className="mt-2 flex flex-col gap-1 ml-4">
                    {r.evidence.map((e, i) => (
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