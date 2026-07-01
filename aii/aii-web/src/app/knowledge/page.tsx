/**
 * /knowledge — KU 浏览(AII-FRONTEND-DISPLAY-001 §二)。
 *
 * 命门:grade 视觉区分(OEpistemicBadge);merge_count>1 标"多书共有"。
 * 筛选:grade / knowledge_type / 来源书 / 是否合并过。
 * API:GET /api/ku/list(分页/筛选)+ /api/ku/{id}(详情,sources 多表述)。
 */
'use client';

import { useEffect, useState, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  OEpistemicBadge,
  OFilterChip,
  OEmptyState,
  OLoadingState,
  OErrorState,
  EPISTEMIC_GRADE_LABEL,
  type EpistemicGrade,
  type OFilterChipOption,
} from '@helios/blocks';
import { useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import { MathText } from '@/components/MathText';
import type { KuListItem, KuDetail, KnowledgeType } from '@/types/api';

const GRADE_OPTS: OFilterChipOption[] = (
  ['proven','high','moderate','low','unverified','contradicted'] as EpistemicGrade[]
).map(g => ({ value: g, label: EPISTEMIC_GRADE_LABEL[g].zh }));

const TYPE_OPTS: OFilterChipOption[] = (
  ['theorem','definition','concept','claim','method','observation'] as KnowledgeType[]
).map(t => ({ value: t, label: t }));

/** 双语:中文(简体)主显 + 英文原文折叠(箭头展开)。无中文时回退英文。 */
function BilingualText({ zh, en }: { zh?: string | null; en: string }) {
  const [showEn, setShowEn] = useState(false);
  const hasZh = !!zh && zh.trim().length > 0;
  return (
    <div className="flex flex-col gap-1.5">
      <MathText text={hasZh ? (zh as string) : en} className="text-sm leading-relaxed" />
      {hasZh && (
        <>
          <button
            onClick={e => { e.stopPropagation(); setShowEn(v => !v); }}
            className="self-start text-xs text-[color:var(--text-secondary)] hover:text-[color:var(--accent,#2563eb)] flex items-center gap-1"
          >
            <span className="inline-block w-3">{showEn ? '▾' : '▸'}</span> 英文原文
          </button>
          {showEn && (
            <MathText text={en} className="text-sm leading-relaxed text-[color:var(--text-secondary)] border-l-2 border-[color:var(--border)] pl-2" />
          )}
        </>
      )}
    </div>
  );
}

function KuDetailPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const [state, run] = useApi(api.getKuDetail);
  useEffect(() => { void run(id); }, [id, run]);
  const d = state.data as KuDetail | null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-md h-full overflow-y-auto bg-[color:var(--card)] border-l border-[color:var(--border)] p-5 flex flex-col gap-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-base font-semibold">KU 详情</h2>
          <button onClick={onClose} className="text-[color:var(--text-secondary)] text-sm" aria-label="关闭">✕</button>
        </div>
        {state.loading && <OLoadingState rows={3} />}
        {state.error && <OErrorState error={state.error} onRetry={() => void run(id)} />}
        {d && (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              <OEpistemicBadge grade={d.grade} defeaterCount={d.defeater_count} />
              <span className="text-xs px-2 py-0.5 rounded-full border border-[color:var(--border)]">{d.knowledge_type}</span>
              {d.merge_count > 1 && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-[color:var(--accent,#2563eb)]/15 text-[color:var(--accent,#2563eb)] border border-[color:var(--accent,#2563eb)]/30">
                  多书共有 ×{d.merge_count}
                </span>
              )}
            </div>
            {d.title && <h3 className="text-base font-semibold text-[color:var(--text-primary)]">{d.title}</h3>}
            <BilingualText zh={d.natural_text_zh} en={d.natural_text} />

            <section className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold text-[color:var(--text-secondary)] uppercase tracking-wide">来源表述 / Sources</h3>
              {d.sources.map((s, i) => (
                <div key={i} className="rounded-md border border-[color:var(--border)] p-2.5 text-sm">
                  <div className="text-xs text-[color:var(--text-secondary)] mb-1">{s.substrate_title}{s.locator ? ` · ${s.locator}` : ''}</div>
                  <div>{s.text}</div>
                </div>
              ))}
              {d.merge_count > 1 && (
                <p className="text-xs text-[color:var(--text-tertiary,#888)]">跨书去重:同一知识在多本书的不同表述被归并为一条 KU。</p>
              )}
            </section>

            {d.defeaters.length > 0 && (
              <section className="flex flex-col gap-2">
                <h3 className="text-xs font-semibold text-[color:var(--alert-error,#dc2626)] uppercase tracking-wide">反证 / Defeaters</h3>
                {d.defeaters.map(df => (
                  <div key={df.id} className="rounded-md border border-[color:var(--alert-error,#dc2626)]/40 p-2.5 text-sm">
                    {df.text} <span className="text-xs text-[color:var(--text-tertiary,#888)]">(weight={df.weight})</span>
                  </div>
                ))}
              </section>
            )}

            <section className="flex flex-col gap-2">
              <h3 className="text-xs font-semibold text-[color:var(--text-secondary)] uppercase tracking-wide">关联边 / Edges</h3>
              {d.edges.map((e, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={e.relation_type === 'contradicts' ? 'text-[color:var(--alert-error,#dc2626)] font-medium' : ''}>{e.relation_type}</span>
                  <span className="text-[color:var(--text-tertiary,#888)]">→</span>
                  <span className="flex-1 truncate">{e.target_text}</span>
                  <span className="text-[color:var(--text-tertiary,#888)]" title={e.extraction_method === 'rule' ? '规则边(可信)' : 'LLM 边(线索)'}>
                    {e.extraction_method === 'rule' ? '— rule' : '┄ llm'}
                  </span>
                </div>
              ))}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function KnowledgePage() {
  const [state, run] = useApi(api.getKuList);
  const [grade, setGrade] = useState<string[]>([]);
  const [type, setType] = useState<string[]>([]);
  const [mergedOnly, setMergedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);

  const searchParams = useSearchParams();
  const substrate = searchParams.get('substrate') || undefined;
  const [bookTitle, setBookTitle] = useState('');
  useEffect(() => {
    if (!substrate) { setBookTitle(''); return; }
    api.getBooks().then(r => {
      if (r.ok && r.data) setBookTitle(r.data.items.find(b => b.substrate_id === substrate)?.title || '');
    });
  }, [substrate]);
  const load = useCallback(() => {
    void run({
      grade: (grade[0] as EpistemicGrade) || undefined,
      type: (type[0] as KnowledgeType) || undefined,
      merged_only: mergedOnly || undefined,
      substrate: substrate || undefined,
      page,
      page_size: 20,
    });
  }, [grade, type, mergedOnly, substrate, page, run]);

  useEffect(() => { load(); }, [load]);

  const data = state.data;
  const items = (data?.items ?? []) as KuListItem[];
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-5xl mx-auto">
      <header className="flex flex-col gap-1">
        {bookTitle && (
          <nav className="text-xs text-[color:var(--text-secondary)] flex items-center gap-1.5 flex-wrap">
            <Link href="/book" className="hover:text-[color:var(--accent,#2563eb)]">📚 书级理解</Link>
            <span>›</span>
            <span className="font-medium text-[color:var(--text-primary)]">{bookTitle}</span>
            <span>›</span>
            <span>讲透 KU</span>
          </nav>
        )}
        <h1 className="text-xl font-semibold">知识库 / Knowledge Units{bookTitle && <span className="text-sm font-normal text-[color:var(--text-secondary)] ml-2">· {bookTitle}</span>}</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          浏览 KU。<strong>每条标注可信度 grade</strong>;<strong>多书共有</strong>的 KU 体现跨书去重。
        </p>
      </header>

      {/* 筛选器 */}
      <div className="flex flex-col gap-2">
        <OFilterChip label="可信度" options={GRADE_OPTS} selected={grade} onChange={(s) => { setGrade(s); setPage(1); }} single showAll />
        <OFilterChip label="类型" options={TYPE_OPTS} selected={type} onChange={(s) => { setType(s); setPage(1); }} single showAll />
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={mergedOnly} onChange={e => { setMergedOnly(e.target.checked); setPage(1); }} />
          只看多书共有(merge_count&gt;1)
        </label>
      </div>

      {state.loading && <OLoadingState rows={5} />}
      {state.error && <OErrorState error={state.error} onRetry={load} />}
      {!state.loading && data && items.length === 0 && (
        <OEmptyState title="没有匹配的 KU" description="尝试调整筛选条件" />
      )}

      {items.length > 0 && (
        <>
          <div className="text-xs text-[color:var(--text-secondary)]">
            共 {data!.total.toLocaleString()} 条{(grade[0] || type[0] || mergedOnly) ? '(已筛选)' : ''} · 第 {data!.page}/{totalPages} 页
          </div>
          <ul className="flex flex-col gap-2">
            {items.map(ku => (
              <li
                key={ku.id}
                onClick={() => setDetailId(ku.id)}
                className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-3 flex flex-col gap-2 cursor-pointer hover:border-[color:var(--accent,#2563eb)]/50 transition-colors"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <OEpistemicBadge grade={ku.grade} defeaterCount={ku.defeater_count} compact />
                  <span className="text-xs px-1.5 py-0.5 rounded border border-[color:var(--border)] text-[color:var(--text-secondary)]">{ku.knowledge_type}</span>
                  {ku.merge_count > 1 && (
                    <span className="text-xs px-1.5 py-0.5 rounded-full bg-[color:var(--accent,#2563eb)]/15 text-[color:var(--accent,#2563eb)]">多书共有 ×{ku.merge_count}</span>
                  )}
                  <span className="text-xs text-[color:var(--text-tertiary,#888)] ml-auto">{ku.substrate_title}</span>
                </div>
                {ku.title && <div className="text-sm font-semibold text-[color:var(--text-primary)]">{ku.title}</div>}
                <BilingualText zh={ku.natural_text_zh} en={ku.natural_text} />
              </li>
            ))}
          </ul>

          {/* 分页 */}
          <div className="flex items-center justify-center gap-3 pt-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 rounded border border-[color:var(--border)] text-sm disabled:opacity-40">上一页</button>
            <span className="text-sm tabular-nums">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 rounded border border-[color:var(--border)] text-sm disabled:opacity-40">下一页</button>
          </div>
        </>
      )}

      {detailId && <KuDetailPanel id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

export default function KnowledgePageWrapper() {
  return (
    <Suspense fallback={null}>
      <KnowledgePage />
    </Suspense>
  );
}
