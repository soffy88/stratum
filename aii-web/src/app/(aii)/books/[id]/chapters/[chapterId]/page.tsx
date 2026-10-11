/**
 * /books/[id]/chapters/[chapterId] — 章节级 BU 理解。
 * 直接消费 GET /api/v1/bu/{run_id}/chapters/{chapter_id}。
 */
'use client';

import { use, useEffect, useState } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { GradeDot, gradeTextClass } from '@/aii/components/GradeMarkers';
import { PptExportDialog } from '@/components/ppt/PptExportDialog';

interface ChapterDetail {
  chapter_id: string;
  title: string;
  role: string;
  summary: string;
  concepts: Array<{ ku_id: string; label: string; grade: string; definition: string }>;
  claims: Array<{ id: string; text: string; grade: string; evidence_ids: string[] }>;
  evidence: Array<{ id: string; quote: string; grade: string; locator: string }>;
  mechanisms: Array<{ id: string; description: string; grade: string }>;
  questions: string[];
  conclusions: string[];
  quality_score: number;
  provenance: Record<string, string[]>;
  created_at: string;
}

interface BuContext {
  run_id: string;
  book_title: string;
}

function ChapterDetailPage({ params: paramsPromise }: { params: Promise<{ id: string; chapterId: string }> }) {
  const params = use(paramsPromise);
  const [buContext, setBuContext] = useState<BuContext | null>(null);
  const [pptOpen, setPptOpen] = useState(false);
  const [state, run] = useApi((id: string) => api.getChapterDetail(id, params.chapterId));

  useEffect(() => {
    // Load BU context first
    api.getBuDetail(params.id).then(res => {
      if (res.ok && res.data) {
        setBuContext({ run_id: res.data.run_id ?? params.id, book_title: res.data.book_title });
      }
    });
    void run(params.id);
  }, [params.id, params.chapterId, run]);

  const d = state.data as ChapterDetail | null;

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-5xl mx-auto">
      <header className="flex flex-col gap-1">
        <nav className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)]">
          <a href="/books" className="hover:text-[color:var(--foreground)]">书级理解</a>
          <span>/</span>
          <a href={`/books/${params.id}`} className="hover:text-[color:var(--foreground)]">
            {buContext?.book_title || 'Book'}
          </a>
          <span>/</span>
          <span className="text-[color:var(--foreground)] font-medium">章节: {params.chapterId}</span>
        </nav>
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-xl font-semibold">{d?.title || `章节 ${params.chapterId}`}</h1>
          <button
            onClick={() => setPptOpen(true)}
            className="shrink-0 text-sm px-3 py-1.5 rounded-md border border-[color:var(--border)] hover:border-[color:var(--accent,#2563eb)]/60 transition-colors"
          >
            生成 PPT
          </button>
        </div>
        <p className="text-sm text-[color:var(--text-secondary)]">
          角色: <strong>{d?.role || '未知'}</strong> · 质量分: <strong>{d?.quality_score?.toFixed(2) || '0'}</strong>
        </p>
      </header>

      <PptExportDialog
        open={pptOpen}
        onClose={() => setPptOpen(false)}
        runId={buContext?.run_id ?? params.id}
        chapterId={params.chapterId}
        bookTitle={buContext?.book_title}
      />

      {state.loading && <OLoadingState rows={6} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run(params.id)} />}
      {!state.loading && !d && <OEmptyState title="章节不存在" description="该章节无 BU 理解结果" />}

      {d && (
        <>
          {/* 概览 */}
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">概览 · Summary</h3>
            <p className="text-[15px] leading-relaxed text-[color:var(--foreground)]">{d.summary}</p>
          </section>

          {/* 核心概念 */}
          {d.concepts.length > 0 && (
            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
                核心概念 · Concepts ({d.concepts.length})
              </h3>
              <div className="flex flex-wrap gap-2">
                {d.concepts.map((c) => (
                  <a
                    key={c.ku_id}
                    href={`/knowledge?ku=${c.ku_id}`}
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded border border-[color:var(--border)] bg-[color:var(--card)] text-sm hover:border-[color:var(--accent)] transition-colors"
                  >
                    <GradeDot grade={c.grade as any} size={8} />
                    <span className="font-medium">{c.label}</span>
                    <span className="text-xs text-[color:var(--text-tertiary)]">({c.grade})</span>
                  </a>
                ))}
              </div>
            </section>
          )}

          {/* 主要论断 */}
          {d.claims.length > 0 && (
            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
                主要论断 · Claims ({d.claims.length})
              </h3>
              <ul className="flex flex-col gap-3">
                {d.claims.map((c) => (
                  <li key={c.id} className="flex gap-3 pl-2">
                    <GradeDot grade={c.grade as any} size={9} />
                    <div className="flex flex-col gap-1 flex-1">
                      <p className="text-[15px] leading-relaxed">{c.text}</p>
                      <span className={`inline-flex items-center gap-1.5 text-xs ${gradeTextClass(c.grade as any)}`}>
                        <GradeDot grade={c.grade as any} size={7} />
                        证据: {c.evidence_ids.length} 条
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 证据 */}
          {d.evidence.length > 0 && (
            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
                证据 · Evidence ({d.evidence.length})
              </h3>
              <ul className="flex flex-col gap-2">
                {d.evidence.map((e, i) => (
                  <li key={e.id} className="flex gap-3 pl-2">
                    <GradeDot grade={e.grade as any} size={9} />
                    <div className="flex flex-col gap-1 flex-1">
                      <p className="text-sm leading-relaxed text-[color:var(--foreground)]">"{e.quote}"</p>
                      <span className="text-xs text-[color:var(--text-tertiary)]">
                        定位: {e.locator || '未知'}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 机制 */}
          {d.mechanisms.length > 0 && (
            <section className="flex flex-col gap-3">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
                机制 · Mechanisms ({d.mechanisms.length})
              </h3>
              <ul className="flex flex-col gap-2">
                {d.mechanisms.map((m) => (
                  <li key={m.id} className="flex gap-3 pl-2">
                    <GradeDot grade={m.grade as any} size={9} />
                    <p className="text-sm leading-relaxed flex-1">{m.description}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 问题 */}
          {d.questions.length > 0 && (
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
                问题 · Questions ({d.questions.length})
              </h3>
              <ul className="flex flex-col gap-1.5">
                {d.questions.map((q, i) => (
                  <li key={i} className="text-sm leading-relaxed flex items-start gap-2">
                    <span className="text-[color:var(--accent)] font-bold shrink-0">Q{i + 1}.</span>
                    <span>{q}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 结论 */}
          {d.conclusions.length > 0 && (
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
                结论 · Conclusions ({d.conclusions.length})
              </h3>
              <ul className="flex flex-col gap-1.5">
                {d.conclusions.map((c, i) => (
                  <li key={i} className="text-sm leading-relaxed flex items-start gap-2">
                    <span className="text-[color:var(--accent)] font-bold shrink-0">C{i + 1}.</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 追溯链 */}
          {Object.keys(d.provenance).length > 0 && (
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase">
                追溯链 · Provenance
              </h3>
              <div className="text-xs text-[color:var(--text-tertiary)] font-mono">
                <pre className="whitespace-pre-wrap">{JSON.stringify(d.provenance, null, 2)}</pre>
              </div>
            </section>
          )}

          {/* 创建时间 */}
          <p className="text-xs text-[color:var(--text-tertiary)] border-t border-[color:var(--border)] pt-3">
            创建时间: {new Date(d.created_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}

export default ChapterDetailPage;