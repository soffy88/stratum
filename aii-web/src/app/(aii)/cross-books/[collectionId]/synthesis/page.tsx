/**
 * /cross-books/[collectionId]/synthesis — 跨书综合报告页。
 */
'use client';

import { use, useEffect } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import Link from 'next/link';

interface Synthesis {
  common_ground: string[];
  major_differences: string[];
  supporting_theories: string[];
  competing_theories: string[];
  evidence_convergence: string[];
  evidence_divergence: string[];
  unresolved_conflicts: Array<{ description: string; confidence: number }>;
  knowledge_gaps: Array<{ description: string; type: string }>;
  higher_order_synthesis: string;
}

export default function CrossBookSynthesisPage({ params: paramsPromise }: { params: Promise<{ collectionId: string }> }) {
  const params = use(paramsPromise);
  const [state, run] = useApi((id: string) => api.getCrossBookSynthesis(id));

  useEffect(() => {
    void run(params.collectionId);
  }, [params.collectionId, run]);

  const s = state.data as Synthesis | null;

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-2">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <Link href="/cross-books" className="hover:text-[color:var(--foreground)]">跨书分析</Link>
          <span>/</span>
          <Link href={`/cross-books/${params.collectionId}`} className="hover:text-[color:var(--foreground)]">概览</Link>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">综合报告</span>
        </nav>
        <h1 className="text-xl font-semibold">跨书综合报告</h1>
      </header>

      {state.loading && <OLoadingState rows={6} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.collectionId)} />}
      {!state.loading && !s && <OEmptyState title="无综合报告" description="请先运行 P14 分析" />}

      {s && (
        <div className="flex flex-col gap-6">
          {/* 共同基础 */}
          {s.common_ground.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                🟢 共同基础 ({s.common_ground.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.common_ground.map((c, i) => (
                  <li key={i} className="text-sm leading-relaxed">{c}</li>
                ))}
              </ul>
            </section>
          )}

          {/* 主要差异 */}
          {s.major_differences.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                🔴 主要差异 ({s.major_differences.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.major_differences.map((d, i) => (
                  <li key={i} className="text-sm leading-relaxed">{d}</li>
                ))}
              </ul>
            </section>
          )}

          {/* 支持理论 */}
          {s.supporting_theories.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                🤝 支持理论 ({s.supporting_theories.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.supporting_theories.map((t, i) => (
                  <li key={i} className="text-sm leading-relaxed">{t}</li>
                ))}
              </ul>
            </section>
          )}

          {/* 竞争理论 */}
          {s.competing_theories.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                ⚔️ 竞争理论 ({s.competing_theories.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.competing_theories.map((t, i) => (
                  <li key={i} className="text-sm leading-relaxed">{t}</li>
                ))}
              </ul>
            </section>
          )}

          {/* 证据收敛 */}
          {s.evidence_convergence.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                📈 证据收敛 ({s.evidence_convergence.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.evidence_convergence.map((e, i) => (
                  <li key={i} className="text-sm leading-relaxed">{e}</li>
                ))}
              </ul>
            </section>
          )}

          {/* 证据发散 */}
          {s.evidence_divergence.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                📉 证据发散 ({s.evidence_divergence.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.evidence_divergence.map((e, i) => (
                  <li key={i} className="text-sm leading-relaxed">{e}</li>
                ))}
              </ul>
            </section>
          )}

          {/* 未解决冲突 */}
          {s.unresolved_conflicts.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                ⚠️ 未解决冲突 ({s.unresolved_conflicts.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.unresolved_conflicts.map((c, i) => (
                  <li key={i} className="text-sm leading-relaxed flex items-start gap-2">
                    <GradeDot grade={c.confidence >= 0.7 ? 'high' : c.confidence >= 0.4 ? 'moderate' : 'low'} size={8} />
                    <span>{c.description}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 知识缺口 */}
          {s.knowledge_gaps.length > 0 && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                🕳️ 知识缺口 ({s.knowledge_gaps.length})
              </h3>
              <ul className="flex flex-col gap-2 ml-4">
                {s.knowledge_gaps.map((g, i) => (
                  <li key={i} className="text-sm leading-relaxed flex items-start gap-2">
                    <span className="text-[color:var(--accent)] font-bold shrink-0">{g.type}:</span>
                    <span>{g.description}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 高阶综合 */}
          {s.higher_order_synthesis && (
            <section className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase flex items-center gap-2">
                🧠 高阶综合
              </h3>
              <p className="text-base leading-relaxed text-[color:var(--foreground)]">{s.higher_order_synthesis}</p>
            </section>
          )}

          <Link
            href={`/cross-books/${params.collectionId}/expression`}
            className="px-4 py-2 rounded border border-[color:var(--accent)] text-[color:var(--accent)] text-sm font-medium hover:bg-[color:var(--accent)]/10 transition-colors"
          >
            查看人类可读表达 →
          </Link>
        </div>
      )}
    </div>
  );
}