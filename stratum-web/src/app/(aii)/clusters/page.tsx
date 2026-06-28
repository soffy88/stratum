/**
 * /clusters — 知识簇 KC(AII-FRONTEND-DISPLAY-001 §四)。
 *
 * 命门:每个 KC 摘要标注"AII 综合,非原文断言";grade ≤ 源 KU,永不 proven。
 * API:GET /api/kc/list + /api/kc/{id}(含 source_ku_ids)。
 */
'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  OEpistemicBadge,
  OEmptyState,
  OLoadingState,
  OErrorState,
} from '@helios/blocks';
import { useApi } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { MathText } from '@/aii/components/MathText';
import type { KcListItem, KcDetail } from '@/aii/types/api';

function SynthesisTag() {
  return (
    <span
      className="text-xs px-2 py-0.5 rounded-full bg-[color:var(--alert-warn-bg,#fef3c7)] text-[color:var(--alert-warn-fg,#78350f)] border border-[color:var(--alert-warn,#d97706)]/40"
      title="此摘要由 AII 综合生成,不是原文的直接断言"
    >
      AII 综合 · 非原文断言
    </span>
  );
}

function BiText({ zh, en }: { zh: string; en?: string }) {
  const [showEn, setShowEn] = useState(false);
  return (
    <div className="flex flex-col gap-1.5">
      <MathText text={zh} className="text-sm leading-relaxed" />
      {en && (
        <>
          <button onClick={() => setShowEn(v => !v)} className="self-start text-xs text-[color:var(--text-secondary)] hover:text-[color:var(--accent,#2563eb)]">
            <span className="inline-block w-3">{showEn ? '▾' : '▸'}</span> 英文原文
          </button>
          {showEn && <MathText text={en} className="text-sm leading-relaxed text-[color:var(--text-secondary)] border-l-2 border-[color:var(--border)] pl-2" />}
        </>
      )}
    </div>
  );
}

function MemberRow({ m, showSource }: { m: KcDetail['members'][number]; showSource?: boolean }) {
  const [open, setOpen] = useState(false);
  const [showEn, setShowEn] = useState(false);
  const zh = m.natural_text_zh || m.natural_text;
  return (
    <div className="rounded-md border border-[color:var(--border)] p-2.5 text-sm flex flex-col gap-1.5">
      <button onClick={() => setOpen(v => !v)} className="flex items-start gap-2 text-left w-full">
        <OEpistemicBadge grade={m.grade} compact />
        <span className="flex-1 min-w-0 leading-relaxed">{m.title || zh.slice(0, 50)}</span>
        {showSource && m.source_book && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[color:var(--accent,#2563eb)]/10 text-[color:var(--accent,#2563eb)] whitespace-nowrap">{m.source_book.split('（')[0]}</span>
        )}
        <span className="text-xs text-[color:var(--text-tertiary,#888)]">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="pl-2 border-l-2 border-[color:var(--border)] flex flex-col gap-1.5">
          <MathText text={zh} className="text-sm leading-relaxed" />
          {m.natural_text_en && (
            <>
              <button onClick={() => setShowEn(v => !v)} className="self-start text-xs text-[color:var(--text-secondary)] hover:text-[color:var(--accent,#2563eb)]">
                <span className="inline-block w-3">{showEn ? '▾' : '▸'}</span> 英文原文
              </button>
              {showEn && <MathText text={m.natural_text_en} className="text-sm leading-relaxed text-[color:var(--text-secondary)]" />}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function KcDetailPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const [state, run] = useApi(api.getKcDetail);
  useEffect(() => { void run(id); }, [id, run]);
  const d = state.data as KcDetail | null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div className="w-full max-w-md h-full overflow-y-auto bg-[color:var(--card)] border-l border-[color:var(--border)] p-5 flex flex-col gap-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-base font-semibold">知识簇详情</h2>
          <button onClick={onClose} className="text-[color:var(--text-secondary)] text-sm" aria-label="关闭">✕</button>
        </div>
        {state.loading && <OLoadingState rows={3} />}
        {state.error && <OErrorState error={state.error} onRetry={() => void run(id)} />}
        {d && (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              <OEpistemicBadge grade={d.grade} />
              <span className="text-xs text-[color:var(--text-secondary)]">{d.community_size} 个 KU</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base font-medium">{d.community_label}</h3>
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                d.kind === 'spectral'
                  ? 'bg-[color:var(--accent,#7c3aed)]/15 text-[color:var(--accent,#7c3aed)]'
                  : 'bg-[color:var(--text-tertiary,#888)]/15 text-[color:var(--text-secondary)]'
              }`}>{d.kind === 'spectral' ? '跨书主题' : '书内章节'}</span>
            </div>
            <div className="flex flex-col gap-2">
              <SynthesisTag />
              <BiText zh={d.summary} en={d.summary_en} />
            </div>
            {d.kind === 'spectral' && (
              <p className="text-xs text-[color:var(--text-tertiary,#888)] leading-relaxed">
                跨书主题:汇集各书的同类知识,随新书加入而增长(成员标来源书)。
              </p>
            )}
            <section className="flex flex-col gap-2">
              <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] uppercase tracking-wide">成员 KU / Members（点开看讲透）</h4>
              {d.members.map(m => <MemberRow key={m.id} m={m} showSource={d.kind === 'spectral'} />)}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function ClustersPage() {
  const [state, run] = useApi(api.getKcList);
  const [view, setView] = useState<'chapter' | 'spectral'>('chapter');
  const [detailId, setDetailId] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const substrate = searchParams.get('substrate') || 'microecon_en_full_v2';
  const [bookTitle, setBookTitle] = useState('');
  useEffect(() => { void run({ view, substrate }); }, [run, view, substrate]);
  useEffect(() => {
    api.getBooks().then(r => {
      if (r.ok && r.data) setBookTitle(r.data.items.find(b => b.substrate_id === substrate)?.title || '');
    });
  }, [substrate]);

  const items = ((state.data as any)?.items ?? state.data ?? []) as KcListItem[];

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-5xl mx-auto">
      <header className="flex flex-col gap-1">
        <nav className="text-xs text-[color:var(--text-secondary)] flex items-center gap-1.5 flex-wrap">
          <Link href="/book" className="hover:text-[color:var(--accent,#2563eb)]">📚 书级理解</Link>
          <span>›</span>
          {bookTitle && <Link href={`/book`} className="hover:text-[color:var(--accent,#2563eb)] font-medium text-[color:var(--text-primary)]">{bookTitle}</Link>}
          <span>›</span>
          <span>知识簇</span>
        </nav>
        <h1 className="text-xl font-semibold">知识簇 / Knowledge Clusters{bookTitle && <span className="text-sm font-normal text-[color:var(--text-secondary)] ml-2">· {bookTitle}</span>}</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          {view === 'chapter'
            ? '📖 书内章节结构,按章顺序(固定)。点 KC 看摘要 + 成员 KU。'
            : '🕸 跨书主题,概念关联聚合(随新书加入而增长)。每个主题汇集各书的同类 KU(标来源书)。'}
          <span className="ml-1"><strong>簇摘要是 AII 综合,非原文断言</strong>。</span>
        </p>
        <div className="flex gap-2 mt-1">
          {([['chapter', '按章 · 书内结构'], ['spectral', '谱社区 · 跨书主题']] as const).map(([v, label]) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                view === v
                  ? 'bg-[color:var(--accent,#2563eb)]/15 text-[color:var(--accent,#2563eb)] border-[color:var(--accent,#2563eb)]/40'
                  : 'border-[color:var(--border)] text-[color:var(--text-secondary)]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run({ view, substrate })} />}
      {!state.loading && items.length === 0 && <OEmptyState title="暂无知识簇" description="后端 /api/kc/list 待实现" />}

      {items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map(kc => (
            <div
              key={kc.id}
              onClick={() => setDetailId(kc.id)}
              className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4 flex flex-col gap-2 cursor-pointer hover:border-[color:var(--accent,#2563eb)]/50 transition-colors"
            >
              <div className="flex items-center gap-2 flex-wrap">
                <OEpistemicBadge grade={kc.grade} compact />
                <span className="text-xs text-[color:var(--text-tertiary,#888)] ml-auto">{kc.community_size} KU</span>
              </div>
              <h3 className="text-sm font-medium">{kc.community_label}</h3>
              <SynthesisTag />
              <p className="text-xs text-[color:var(--text-secondary)] leading-relaxed line-clamp-3">{kc.summary}</p>
            </div>
          ))}
        </div>
      )}

      {detailId && <KcDetailPanel id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

export default function ClustersPageWrapper() {
  return (
    <Suspense fallback={<div className="aii-page-content"><OLoadingState rows={4} /></div>}>
      <ClustersPage />
    </Suspense>
  );
}
