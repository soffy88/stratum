/**
 * /cross-books/[collectionId]/expression — 人类可读表达页。
 * 直接渲染后端 ExpressionGenerator 生成的完整文本。
 */
'use client';

import { use, useEffect } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import Link from 'next/link';

interface ExpressionResponse {
  collection_id: string;
  collection_name: string;
  book_count: number;
  concept_summary: string;
  thesis_summary: string;
  argument_summary: string;
  contradiction_summary: string;
  gap_summary: string;
  synthesis: string;
  pairwise_comparisons: string;
  quality: string;
}

export default function CrossBookExpressionPage({ params: paramsPromise }: { params: Promise<{ collectionId: string }> }) {
  const params = use(paramsPromise);
  const [state, run] = useApi((id: string) => api.getCrossBookExpression(id));

  useEffect(() => {
    void run(params.collectionId);
  }, [params.collectionId, run]);

  const e = state.data as ExpressionResponse | null;

  return (
    <div className="aii-page-content max-w-4xl mx-auto">
      <header className="flex flex-col gap-2 mb-8">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <Link href={`/cross-books/${params.collectionId}`} className="hover:text-[color:var(--foreground)]">概览</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">人类可读表达</span>
        </nav>
        <h1 className="text-2xl font-semibold">{e?.collection_name || '跨书理解表达'}</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">{e?.book_count || 0} 本书 · Collection: {e?.collection_id}</p>
      </header>

      {state.loading && <OLoadingState rows={10} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.collectionId)} />}
      {!state.loading && !e && <OEmptyState title="无表达内容" description="请先运行 P14 分析" />}

      {e && (
        <article className="prose prose-invert max-w-none flex flex-col gap-6">
          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">概念对齐</h2>
            <p className="mt-3 text-base leading-relaxed">{e.concept_summary}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">论题比较</h2>
            <p className="mt-3 text-base leading-relaxed">{e.thesis_summary}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">论证比较</h2>
            <p className="mt-3 text-base leading-relaxed">{e.argument_summary}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">矛盾检测</h2>
            <p className="mt-3 text-base leading-relaxed">{e.contradiction_summary}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">知识缺口</h2>
            <p className="mt-3 text-base leading-relaxed">{e.gap_summary}</p>
          </section>

          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">综合报告</h2>
            <div className="mt-3 whitespace-pre-wrap text-base leading-relaxed font-mono text-sm">{e.synthesis}</div>
          </section>

          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">两两比较</h2>
            <div className="mt-3 whitespace-pre-wrap text-base leading-relaxed font-mono text-sm">{e.pairwise_comparisons}</div>
          </section>

          <section>
            <h2 className="text-lg font-semibold border-b border-[color:var(--border)] pb-2">质量指标 (Q19-Q26)</h2>
            <div className="mt-3 whitespace-pre-wrap text-base leading-relaxed font-mono text-sm">{e.quality}</div>
          </section>
        </article>
      )}
    </div>
  );
}