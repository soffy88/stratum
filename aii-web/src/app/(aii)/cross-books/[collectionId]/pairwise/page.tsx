/**
 * /cross-books/[collectionId]/pairwise — 两两书籍比较页。
 */
'use client';

import { useEffect } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import Link from 'next/link';

interface PairwiseComparison {
  book_a_id: string;
  book_b_id: string;
  concept_relations: api.ConceptRelationItem[];
  thesis_relations: api.ThesisRelationItem[];
  argument_relations: api.ArgumentRelationItem[];
  contradictions: api.ContradictionItem[];
}

export default function CrossBookPairwisePage({ params }: { params: { collectionId: string } }) {
  const [state, run] = useApi((id: string) => api.getPairwiseComparisons(id));

  useEffect(() => {
    void run(params.collectionId);
  }, [params.collectionId, run]);

  const items = (state.data as PairwiseComparison[]) || [];

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-2">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <Link href={`/cross-books/${params.collectionId}`} className="hover:text-[color:var(--foreground)]">概览</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">两两比较</span>
        </nav>
        <h1 className="text-xl font-semibold">两两书籍比较 ({items.length} 对)</h1>
      </header>

      {state.loading && <OLoadingState rows={6} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.collectionId)} />}
      {!state.loading && items.length === 0 && <OEmptyState title="无两两比较" description="至少需要 2 本书" />}

      {!state.loading && items.length > 0 && (
        <div className="flex flex-col gap-4">
          {items.map((p) => (
            <div
              key={`${p.book_a_id}-${p.book_b_id}`}
              className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5 flex flex-col gap-4"
            >
              <header className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="px-3 py-1 rounded bg-[color:var(--accent)]/15 text-[color:var(--accent)] text-sm font-medium">
                    {p.book_a_id}
                  </span>
                  <span className="text-[color:var(--text-tertiary)]">↔</span>
                  <span className="px-3 py-1 rounded bg-[color:var(--accent)]/15 text-[color:var(--accent)] text-sm font-medium">
                    {p.book_b_id}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-sm text-[color:var(--text-tertiary)]">
                  <span>概念: {p.concept_relations.length}</span>
                  <span>论题: {p.thesis_relations.length}</span>
                  <span>论证: {p.argument_relations.length}</span>
                  <span className="text-red-400">矛盾: {p.contradictions.length}</span>
                </div>
              </header>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Link
                  href={`/cross-books/${params.collectionId}/concepts?filter[book_a]=${p.book_a_id}&filter[book_b]=${p.book_b_id}`}
                  className="p-3 rounded border border-[color:var(--border)] hover:border-[color:var(--accent)] transition-colors"
                >
                  <p className="text-xs text-[color:var(--text-tertiary)]">概念关系</p>
                  <p className="text-2xl font-bold">{p.concept_relations.length}</p>
                </Link>
                <Link
                  href={`/cross-books/${params.collectionId}/theses?filter[book_a]=${p.book_a_id}&filter[book_b]=${p.book_b_id}`}
                  className="p-3 rounded border border-[color:var(--border)] hover:border-[color:var(--accent)] transition-colors"
                >
                  <p className="text-xs text-[color:var(--text-tertiary)]">论题关系</p>
                  <p className="text-2xl font-bold">{p.thesis_relations.length}</p>
                </Link>
                <Link
                  href={`/cross-books/${params.collectionId}/arguments?filter[book_a]=${p.book_a_id}&filter[book_b]=${p.book_b_id}`}
                  className="p-3 rounded border border-[color:var(--border)] hover:border-[color:var(--accent)] transition-colors"
                >
                  <p className="text-xs text-[color:var(--text-tertiary)]">论证关系</p>
                  <p className="text-2xl font-bold">{p.argument_relations.length}</p>
                </Link>
                <Link
                  href={`/cross-books/${params.collectionId}/contradictions?filter[book_a]=${p.book_a_id}&filter[book_b]=${p.book_b_id}`}
                  className="p-3 rounded border border-[color:var(--border)] hover:border-[color:var(--accent)] transition-colors"
                >
                  <p className="text-xs text-[color:var(--text-tertiary)]">矛盾</p>
                  <p className="text-2xl font-bold text-red-400">{p.contradictions.length}</p>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}