/**
 * /cross-books/[collectionId] — 跨书理解概览页。
 * 消费 GET /api/v1/cross-books/{collection_id} 及子端点。
 */
'use client';

import { use, useEffect, useState } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { GradeDot, gradeTextClass } from '@/aii/components/GradeMarkers';
import Link from 'next/link';

interface CrossBookOverview {
  collection_id: string;
  name: string;
  books: Array<{ book_id: string; title: string }>;
  concept_relations: number;
  thesis_relations: number;
  argument_relations: number;
  mechanism_relations: number;
  evidence_relations: number;
  contradictions: number;
  knowledge_gaps: number;
}

function SectionCard({
  title,
  count,
  icon,
  href,
  color = 'var(--accent,#2563eb)',
}: {
  title: string;
  count: number;
  icon: string;
  href: string;
  color?: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-3 p-4 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] hover:border-[color:var(--accent)]/50 transition-colors"
    >
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: `${color}15` }}
      >
        <span style={{ color }} className="text-xl">{icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[color:var(--foreground)] group-hover:text-[color:var(--accent)] transition-colors">
          {title}
        </p>
        <p className="text-xs text-[color:var(--text-tertiary)]">
          {count} 项
        </p>
      </div>
      <span className="text-2xl font-bold" style={{ color }}>
        {count}
      </span>
    </Link>
  );
}

export default function CrossBookPage({ params: paramsPromise }: { params: Promise<{ collectionId: string }> }) {
  const params = use(paramsPromise);
  const [state, run] = useApi((id: string) => api.getCrossBookOverview(id));
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<{ status: string; understanding_id?: string } | null>(null);

  useEffect(() => {
    void run(params.collectionId);
  }, [params.collectionId, run]);

  const d = state.data as CrossBookOverview | null;

  const handleRun = async () => {
    setRunning(true);
    const res = await api.runP14(params.collectionId);
    setRunning(false);
    if (res.ok && res.data) {
      setRunResult(res.data);
      void run(params.collectionId); // Refresh
    }
  };

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-2">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">{d?.name || params.collectionId}</span>
        </nav>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">{d?.name || '跨书理解'}</h1>
            <p className="text-sm text-[color:var(--text-secondary)]">
              {d?.books.length || 0} 本书 · {d?.concept_relations || 0} 概念关系 · {d?.thesis_relations || 0} 论题关系 · {d?.argument_relations || 0} 论证关系
            </p>
          </div>
          <div className="flex items-center gap-2">
            {!d ? (
              <button
                onClick={handleRun}
                disabled={running}
                className="px-4 py-2 rounded bg-[color:var(--accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                {running ? '运行中...' : '运行 P14 分析'}
              </button>
            ) : (
              <span className="px-3 py-1 rounded bg-green-500/20 text-green-400 text-xs font-medium">
                已完成分析
              </span>
            )}
          </div>
        </div>
      </header>

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.collectionId)} />}
      {!state.loading && !d && <OEmptyState title="跨书理解不存在" description="请先运行 P14 分析" />}

      {d && (
        <>
          {/* 书籍列表 */}
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
              书籍 · Books ({d.books.length})
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {d.books.map((b) => (
                <div
                  key={b.book_id}
                  className="p-3 rounded border border-[color:var(--border)] bg-[color:var(--card)]"
                >
                  <p className="font-medium">{b.title || b.book_id}</p>
                  <p className="text-xs text-[color:var(--text-tertiary)] font-mono">{b.book_id}</p>
                </div>
              ))}
            </div>
          </section>

          {/* 统计卡片网格 */}
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
              分析维度 · Dimensions
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              <SectionCard
                title="概念对齐"
                count={d.concept_relations}
                icon="🔗"
                href={`/cross-books/${params.collectionId}/concepts`}
                color="#2563eb"
              />
              <SectionCard
                title="论题比较"
                count={d.thesis_relations}
                icon="📝"
                href={`/cross-books/${params.collectionId}/theses`}
                color="#7c3aed"
              />
              <SectionCard
                title="论证比较"
                count={d.argument_relations}
                icon="⚖️"
                href={`/cross-books/${params.collectionId}/arguments`}
                color="#db2777"
              />
              <SectionCard
                title="矛盾检测"
                count={d.contradictions}
                icon="⚔️"
                href={`/cross-books/${params.collectionId}/contradictions`}
                color="#dc2626"
              />
              <SectionCard
                title="知识缺口"
                count={d.knowledge_gaps}
                icon="🕳️"
                href={`/cross-books/${params.collectionId}/gaps`}
                color="#f59e0b"
              />
              <SectionCard
                title="综合报告"
                count={1}
                icon="📊"
                href={`/cross-books/${params.collectionId}/synthesis`}
                color="#059669"
              />
            </div>
          </section>

          {/* 快速入口 */}
          <section className="flex flex-wrap gap-2">
            <Link
              href={`/cross-books/${params.collectionId}/expression`}
              className="px-4 py-2 rounded border border-[color:var(--border)] bg-[color:var(--card)] text-sm hover:border-[color:var(--accent)]/50 transition-colors"
            >
              📖 人类可读表达
            </Link>
            <Link
              href={`/cross-books/${params.collectionId}/pairwise`}
              className="px-4 py-2 rounded border border-[color:var(--border)] bg-[color:var(--card)] text-sm hover:border-[color:var(--accent)]/50 transition-colors"
            >
              📐 两两比较
            </Link>
            <Link
              href={`/cross-books/${params.collectionId}/query`}
              className="px-4 py-2 rounded border border-[color:var(--border)] bg-[color:var(--card)] text-sm hover:border-[color:var(--accent)]/50 transition-colors"
            >
              🔍 查询接口
            </Link>
          </section>

          {runResult && (
            <div className="p-3 rounded bg-blue-500/10 border border-blue-500/30 text-sm text-blue-300">
              运行完成: {runResult.status} · Understanding ID: {runResult.understanding_id}
            </div>
          )}
        </>
      )}
    </div>
  );
}