/**
 * /clusters — 知识簇 KC(AII-FRONTEND-DISPLAY-001 §四)。
 *
 * 命门:每个 KC 摘要标注"AII 综合,非原文断言";grade ≤ 源 KU,永不 proven。
 * API:GET /api/kc/list + /api/kc/{id}(含 source_ku_ids)。
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
import type { KcListItem, KcDetail } from '@/types/api';

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
              <OEpistemicBadge grade={safeGrade(d.grade)} />
              <span className="text-xs text-[color:var(--text-secondary)]">{d.community_size} 个 KU</span>
            </div>
            <h3 className="text-base font-medium">{d.community_label}</h3>
            <div className="flex flex-col gap-2">
              <SynthesisTag />
              <p className="text-sm leading-relaxed">{d.summary}</p>
            </div>
            <section className="flex flex-col gap-2">
              <h4 className="text-xs font-semibold text-[color:var(--text-secondary)] uppercase tracking-wide">成员 KU / Members</h4>
              {d.members.map(m => (
                <div key={m.id} className="rounded-md border border-[color:var(--border)] p-2.5 text-sm flex items-start gap-2">
                  <OEpistemicBadge grade={safeGrade(m.grade)} compact />
                  <span className="flex-1">{m.natural_text}</span>
                </div>
              ))}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default function ClustersPage() {
  const [state, run] = useApiNoArg(api.getKcList);
  const [detailId, setDetailId] = useState<string | null>(null);
  useEffect(() => { void run(); }, [run]);

  const items = (state.data ?? []) as KcListItem[];

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-5xl mx-auto">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">知识簇 / Knowledge Clusters</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          社区检测聚合的主题簇。<strong>簇摘要是 AII 综合,非原文断言</strong>;簇 grade 永不超过其源 KU。
        </p>
      </header>

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run()} />}
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
                <OEpistemicBadge grade={safeGrade(kc.grade)} compact />
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
