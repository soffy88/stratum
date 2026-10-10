/**
 * /cross-books/[collectionId]/query — 跨书查询交互页。
 * 消费 POST /api/v1/cross-books/{collection_id}/query。
 */
'use client';

import { use, useState } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import * as api from '@/aii/lib/api-client';
import Link from 'next/link';

interface QueryResultItem {
  relation_id?: string;
  contradiction_id?: string;
  gap_id?: string;
  [key: string]: any;
}

interface CrossBookQueryResponse {
  items: QueryResultItem[];
  total: number;
  query: string;
  traceability: Record<string, string[]>;
}

const QUERY_TYPES = [
  { value: 'concepts', label: '共享概念', icon: '🔗' },
  { value: 'contradictions', label: '矛盾', icon: '⚔️' },
  { value: 'arguments', label: '论证关系', icon: '⚖️' },
  { value: 'gaps', label: '知识缺口', icon: '🕳️' },
  { value: 'pairwise', label: '两两比较', icon: '📐' },
  { value: 'synthesis', label: '综合报告', icon: '📊' },
];

export default function CrossBookQueryPage({ params: paramsPromise }: { params: Promise<{ collectionId: string }> }) {
  const params = use(paramsPromise);
  const [queryType, setQueryType] = useState<'concepts'>('concepts');
  const [filter, setFilter] = useState<Record<string, string>>({});
  const [state, run] = useState<{ loading: boolean; data?: CrossBookQueryResponse; error?: string }>({
    loading: false,
  });

  const executeQuery = async () => {
    setState({ loading: true, data: undefined, error: undefined });
    try {
      const res = await api.queryCrossBook(params.collectionId, {
        query_type: queryType,
        filter: Object.keys(filter).length ? filter : undefined,
      });
      if (res.ok) {
        setState({ loading: false, data: res.data as CrossBookQueryResponse, error: undefined });
      } else {
        setState({ loading: false, data: undefined, error: res.error || '查询失败' });
      }
    } catch (e) {
      setState({ loading: false, data: undefined, error: String(e) });
    }
  };

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-2">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <Link href={`/cross-books/${params.collectionId}`} className="hover:text-[color:var(--foreground)]">概览</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">查询接口</span>
        </nav>
        <h1 className="text-xl font-semibold">跨书查询</h1>
      </header>

      {/* 查询类型选择 */}
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
          查询类型
        </h3>
        <div className="flex flex-wrap gap-2">
          {QUERY_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => { setQueryType(t.value as any); setFilter({}); }}
              className={`px-4 py-2 rounded border text-sm flex items-center gap-2 transition-colors ${
                queryType === t.value
                  ? 'bg-[color:var(--accent)] border-[color:var(--accent)] text-white'
                  : 'border-[color:var(--border)] text-[color:var(--foreground)] hover:border-[color:var(--accent)]'
              }`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </section>

      {/* 过滤器 */}
      {(queryType === 'pairwise') && (
        <section className="flex flex-col gap-3 p-4 rounded border border-[color:var(--border)] bg-[color:var(--card)]">
          <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
            过滤条件
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-[color:var(--text-tertiary)] mb-1">Book A ID</label>
              <input
                type="text"
                value={filter.book_a || ''}
                onChange={e => setFilter({ ...filter, book_a: e.target.value })}
                className="w-full px-3 py-2 rounded border border-[color:var(--border)] bg-[color:var(--background)] text-[color:var(--foreground)]"
                placeholder="sub-capital"
              />
            </div>
            <div>
              <label className="block text-xs text-[color:var(--text-tertiary)] mb-1">Book B ID</label>
              <input
                type="text"
                value={filter.book_b || ''}
                onChange={e => setFilter({ ...filter, book_b: e.target.value })}
                className="w-full px-3 py-2 rounded border border-[color:var(--border)] bg-[color:var(--background)] text-[color:var(--foreground)]"
                placeholder="sub-keynes"
              />
            </div>
          </div>
        </section>
      )}

      {/* 执行按钮 */}
      <button
        onClick={executeQuery}
        disabled={state.loading}
        className="px-6 py-2.5 rounded bg-[color:var(--accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 w-fit"
      >
        {state.loading ? '查询中...' : '执行查询'}
      </button>

      {/* 结果 */}
      {state.loading && <OLoadingState rows={6} />}
      {state.error && <OErrorState error={state.error} onRetry={executeQuery} />}
      {state.data && state.data.total === 0 && !state.loading && <OEmptyState title="无结果" description="当前条件下未找到匹配项" />}

      {state.data && state.data.total > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[color:var(--text-secondary)]">
              找到 {state.data.total} 项结果 · 查询: {state.data.query}
            </p>
          </div>
          <div className="flex flex-col gap-3">
            {state.data.items.map((item, i) => (
              <details key={`${i}-${item.relation_id || item.contradiction_id || item.gap_id || i}`} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4">
                <summary className="flex items-center gap-3 cursor-pointer font-medium">
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-[color:var(--accent)]/15 text-[color:var(--accent)] border border-[color:var(--accent)]">
                    {item.relation || item.type || 'Item'}
                  </span>
                  <span className="text-sm text-[color:var(--foreground)]">
                    {item.source_thesis || item.element_a || item.description || item.source_concept_id || item.source_argument || JSON.stringify(item).slice(0, 80)}
                  </span>
                </summary>
                <div className="mt-3 text-sm text-[color:var(--text-secondary)] font-mono">
                  <pre className="whitespace-pre-wrap">{JSON.stringify(item, null, 2)}</pre>
                </div>
                {state.data.traceability && Object.keys(state.data.traceability).length > 0 && (
                  <details className="mt-3">
                    <summary className="text-xs text-[color:var(--text-tertiary)] cursor-pointer">追溯链</summary>
                    <pre className="mt-2 whitespace-pre-wrap text-xs text-[color:var(--text-tertiary)] font-mono">
                      {JSON.stringify(state.data.traceability, null, 2)}
                    </pre>
                  </details>
                )}
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}