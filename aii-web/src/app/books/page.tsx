/**
 * /books — 书级理解 BU(AII-FRONTEND-DISPLAY-001 §五)。
 *
 * 命门:
 *   - 摘要标"AII 综合"
 *   - main_claims 每条带 stance_marker("X书主张")+ claim_grade(论断≠真理)
 *   - argument_structure:论点→论据,论据 grade 独立(哪些论据强/弱)← AII 核心价值
 * API:GET /api/bu/list + /api/bu/{id}(完整 synthesis_meta)。
 */
'use client';

import { useEffect, useState } from 'react';
import {
  OEpistemicBadge,
  OEmptyState,
  OLoadingState,
  OErrorState,
} from '@helios/blocks';
import { useApiNoArg, useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import { safeGrade } from '@/lib/grade';
import type { BuListItem, BuDetail } from '@/types/api';

function BuDetailPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const [state, run] = useApi(api.getBuDetail);
  useEffect(() => { void run(id); }, [id, run]);
  const d = state.data as BuDetail | null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div className="w-full max-w-2xl h-full overflow-y-auto bg-[color:var(--card)] border-l border-[color:var(--border)] p-5 flex flex-col gap-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-base font-semibold">书级理解</h2>
          <button onClick={onClose} className="text-[color:var(--text-secondary)] text-sm" aria-label="关闭">✕</button>
        </div>
        {state.loading && <OLoadingState rows={4} />}
        {state.error && <OErrorState error={state.error} onRetry={() => void run(id)} />}
        {d && (
          <>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <OEpistemicBadge grade={safeGrade(d.grade)} />
                <h3 className="text-lg font-semibold">{d.book_title}</h3>
              </div>
              <span className="text-xs px-2 py-0.5 self-start rounded-full bg-[color:var(--alert-warn-bg,#fef3c7)] text-[color:var(--alert-warn-fg,#78350f)] border border-[color:var(--alert-warn,#d97706)]/40">
                AII 综合
              </span>
              <p className="text-sm leading-relaxed">{d.summary}</p>
            </div>

            {/* 主要论断 — 命门:stance_marker + claim_grade */}
            <section className="flex flex-col gap-2">
              <h4 className="text-sm font-semibold">主要论断 / Main Claims</h4>
              <p className="text-xs text-[color:var(--text-tertiary,#888)]">每条论断带"立场标记"——这是书的主张,不等于真理。grade 独立标注。</p>
              {d.main_claims.map(c => (
                <div key={c.id} className="rounded-md border border-[color:var(--border)] p-3 flex flex-col gap-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-[color:var(--muted,#222)] text-[color:var(--text-secondary)]">{c.stance_marker}</span>
                    <OEpistemicBadge grade={safeGrade(c.claim_grade)} compact />
                  </div>
                  <p className="text-sm">{c.text}</p>
                </div>
              ))}
            </section>

            {/* 论点论据结构 — 命门:论据 grade 独立显示 */}
            <section className="flex flex-col gap-2">
              <h4 className="text-sm font-semibold">论点 → 论据 / Argument Structure</h4>
              <p className="text-xs text-[color:var(--text-tertiary,#888)]">每条论据的可信度独立显示,一眼看出哪些论据强、哪些弱。</p>
              {d.argument_structure.map(arg => (
                <div key={arg.id} className="rounded-md border border-[color:var(--border)] p-3 flex flex-col gap-2">
                  <div className="flex items-start gap-2">
                    <OEpistemicBadge grade={safeGrade(arg.thesis_grade)} compact />
                    <p className="text-sm font-medium flex-1">{arg.thesis}</p>
                  </div>
                  <ul className="flex flex-col gap-1.5 ml-2 border-l-2 border-[color:var(--border)] pl-3">
                    {arg.evidence.map((ev, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <OEpistemicBadge grade={safeGrade(ev.grade)} compact />
                        <span className="flex-1 text-[color:var(--text-secondary)]">{ev.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>

            {/* 章节骨架 */}
            {d.structure && (
              <section className="flex flex-col gap-2">
                <h4 className="text-sm font-semibold">章节骨架 / Structure</h4>
                <p className="text-sm leading-relaxed text-[color:var(--text-secondary)]">{d.structure}</p>
              </section>
            )}

            {/* 核心概念 → 链到 KU */}
            <section className="flex flex-col gap-2">
              <h4 className="text-sm font-semibold">核心概念 / Key Concepts</h4>
              <div className="flex flex-wrap gap-2">
                {d.key_concepts.map(kc => (
                  <a key={kc.ku_id} href={`/knowledge?ku=${kc.ku_id}`}
                    className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border border-[color:var(--border)] hover:border-[color:var(--accent,#2563eb)]/50">
                    <OEpistemicBadge grade={safeGrade(kc.grade)} compact />
                    {kc.label}
                  </a>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default function BooksPage() {
  const [state, run] = useApiNoArg(api.getBuList);
  const [detailId, setDetailId] = useState<string | null>(null);
  useEffect(() => { void run(); }, [run]);
  const items = (state.data ?? []) as BuListItem[];

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-5xl mx-auto">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">书级理解 / Book Understanding</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          每本书一个 BU。<strong>论断带立场标记(论断≠真理)</strong>,<strong>论据可信度独立显示</strong>。
        </p>
      </header>

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run()} />}
      {!state.loading && items.length === 0 && <OEmptyState title="暂无书级理解" description="后端 /api/bu/list 待实现" />}

      {items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map(bu => (
            <div key={bu.id} onClick={() => setDetailId(bu.id)}
              className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4 flex flex-col gap-2 cursor-pointer hover:border-[color:var(--accent,#2563eb)]/50 transition-colors">
              <div className="flex items-center gap-2">
                <OEpistemicBadge grade={safeGrade(bu.grade)} compact />
                <h3 className="text-sm font-medium flex-1">{bu.book_title}</h3>
                <span className="text-xs text-[color:var(--text-tertiary,#888)]">{bu.main_claim_count} 论断</span>
              </div>
              <span className="text-xs px-2 py-0.5 self-start rounded-full bg-[color:var(--alert-warn-bg,#fef3c7)] text-[color:var(--alert-warn-fg,#78350f)] border border-[color:var(--alert-warn,#d97706)]/40">AII 综合</span>
              <p className="text-xs text-[color:var(--text-secondary)] leading-relaxed line-clamp-3">{bu.summary}</p>
            </div>
          ))}
        </div>
      )}

      {detailId && <BuDetailPanel id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}
