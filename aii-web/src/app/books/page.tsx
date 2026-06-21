/**
 * /books — 书级理解 BU(AII-FRONTEND-DISPLAY-001 §五 + 视觉优化 BU-VISUAL-001)。
 *
 * 视觉减负原则:留白 + 分隔线 + 缩进 + 轻量色标,取代层层边框 + 重标签 + 装饰图标。
 * 命门红线(保留,轻量表达):
 *   - stance 立场 → 文字前缀 + 左色条(stanceMeta),不再用重标签框
 *   - grade 论据强弱 → 小色点 GradeDot(hover 看具体 grade),不再每条挂 OEpistemicBadge
 *   - "AII 综合非原文断言" → 顶部一句说明,不每条挂橙标
 */
'use client';

import { useEffect, useState } from 'react';
import { OEmptyState, OLoadingState, OErrorState } from '@helios/blocks';
import { useApiNoArg, useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import type { BuListItem, BuDetail } from '@/types/api';
import { GradeDot, gradeTextClass, stanceMeta } from '@/components/GradeMarkers';

/** 区块标题 + 细分隔线(取代多层框) */
function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mt-2">
      <h4 className="text-sm font-semibold tracking-wide text-[color:var(--text-secondary)] uppercase shrink-0">{children}</h4>
      <span className="flex-1 h-px bg-[color:var(--border)]" />
    </div>
  );
}

function BuDetailPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const [state, run] = useApi(api.getBuDetail);
  useEffect(() => { void run(id); }, [id, run]);
  const d = state.data as BuDetail | null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-2xl h-full overflow-y-auto bg-[color:var(--card)] border-l border-[color:var(--border)] px-7 py-6 flex flex-col gap-7"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-sm text-[color:var(--text-secondary)]">书级理解</h2>
          <button onClick={onClose} className="text-[color:var(--text-secondary)] text-sm hover:text-[color:var(--foreground)]" aria-label="关闭">✕</button>
        </div>
        {state.loading && <OLoadingState rows={4} />}
        {state.error && <OErrorState error={state.error} onRetry={() => void run(id)} />}
        {d && (
          <>
            {/* 标题区:书名最重,grade 用小色点,综合声明一句话(不挂橙标) */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2.5">
                <GradeDot grade={d.grade} size={10} />
                <h3 className="text-2xl font-semibold leading-tight">{d.book_title}</h3>
              </div>
              <p className="text-[15px] leading-loose text-[color:var(--foreground)]">{d.summary}</p>
              <p className="text-xs text-[color:var(--text-tertiary,#888)]">
                以下为 AII 综合的书级理解,非原文直接断言;论断带立场标记,论据可信度以色点表示(悬停看具体等级)。
              </p>
            </div>

            {/* 主要论断 — 命门:stance 轻量前缀+左色条,grade 小色点 */}
            <section className="flex flex-col gap-4">
              <SectionHeading>主要论断 · Main Claims</SectionHeading>
              <ul className="flex flex-col gap-5">
                {d.main_claims.map(c => {
                  const st = stanceMeta(c.stance_marker);
                  return (
                    <li key={c.id} className="flex gap-3 pl-1">
                      {/* 左色条:stance 颜色区分 */}
                      <span className="w-0.5 shrink-0 rounded-full self-stretch" style={{ background: st.bar }} aria-hidden />
                      <div className="flex flex-col gap-1 flex-1">
                        <p className="text-[15px] leading-relaxed">
                          <span className="text-[color:var(--text-secondary)] font-medium">{st.prefix}:</span>{' '}
                          {c.text}
                        </p>
                        <span className="inline-flex items-center gap-1.5 text-xs text-[color:var(--text-tertiary,#888)]">
                          <GradeDot grade={c.claim_grade} />
                          <span className="sr-only">可信度</span>
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>

            {/* 论点 → 论据 — 命门:论据 grade 小色点 + 颜色深浅;缩进表层级,无框 */}
            <section className="flex flex-col gap-4">
              <SectionHeading>论点 → 论据 · Argument</SectionHeading>
              <ul className="flex flex-col gap-6">
                {d.argument_structure.map(arg => (
                  <li key={arg.id} className="flex flex-col gap-2.5">
                    {/* 论点:稍重字体 + grade 小色点 */}
                    <div className="flex items-start gap-2">
                      <GradeDot grade={arg.thesis_grade} size={9} />
                      <p className="text-[15px] font-medium leading-relaxed flex-1 -mt-0.5">{arg.thesis}</p>
                    </div>
                    {/* 论据:缩进 + 小圆点列表,grade 小色点 + 文字颜色深浅,无框 */}
                    <ul className="flex flex-col gap-2.5 ml-4 pl-3 border-l border-[color:var(--border)]">
                      {arg.evidence.map((ev, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm leading-relaxed">
                          <GradeDot grade={ev.grade} />
                          <span className={`flex-1 ${gradeTextClass(ev.grade)}`}>{ev.text}</span>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </section>

            {/* 章节骨架 */}
            <section className="flex flex-col gap-4">
              <SectionHeading>章节骨架 · Structure</SectionHeading>
              <p className="text-sm leading-relaxed whitespace-pre-wrap text-[color:var(--text-secondary)]">{d.structure}</p>
            </section>

            {/* 核心概念 → 链到 KU(轻量 chip,grade 小色点) */}
            <section className="flex flex-col gap-4">
              <SectionHeading>核心概念 · Key Concepts</SectionHeading>
              <div className="flex flex-wrap gap-x-5 gap-y-2.5">
                {d.key_concepts.map(kc => (
                  <a key={kc.ku_id} href={`/knowledge?ku=${kc.ku_id}`}
                    className="inline-flex items-center gap-2 text-sm text-[color:var(--foreground)] hover:text-[color:var(--accent,#2563eb)] transition-colors">
                    <GradeDot grade={kc.grade} />
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
    <div className="aii-page-content flex flex-col gap-5 max-w-5xl mx-auto">
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
        <>
          {/* 综合声明:整区顶部一句,不每卡挂橙标 */}
          <p className="text-xs text-[color:var(--text-tertiary,#888)] -mt-2">以下为 AII 综合的书级理解,非原文直接断言。</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4">
            {items.map(bu => (
              <div key={bu.id} onClick={() => setDetailId(bu.id)}
                className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-5 flex flex-col gap-2.5 cursor-pointer hover:border-[color:var(--accent,#2563eb)]/50 transition-colors">
                <div className="flex items-center gap-2.5">
                  <GradeDot grade={bu.grade} />
                  <h3 className="text-[15px] font-medium flex-1">{bu.book_title}</h3>
                  <span className="text-xs text-[color:var(--text-tertiary,#888)]">{bu.main_claim_count} 论断</span>
                </div>
                <p className="text-sm text-[color:var(--text-secondary)] leading-relaxed line-clamp-3">{bu.summary}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {detailId && <BuDetailPanel id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}
