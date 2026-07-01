/**
 * /evolution — 进化 Page(REQ-001 P3)。
 *
 * 数据流(骨架):
 *   1. mount 时 fetch evolution history + pending proposals
 *   2. 用 OEventTimeline 渲染历史(按时间排序)
 *   3. pending 单独一区,可点「接受 / 拒绝」(治理 action)
 *
 * TODO for AII:
 *   - 接受按钮调 /governance/action(action: "promote" 或类似)
 *   - 加 filter:仅看回滚 / 仅看接受
 *   - pending 项加 OConfirmDialog 二次确认
 */
'use client';

import { useEffect } from 'react';
import {
  OEventTimeline,
  OEmptyState,
  OErrorState,
  OLoadingState,
  type TimelineEvent,
} from '@helios/blocks';
import { useApiNoArg } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { DegradedBanner } from '@/aii/components/DegradedBanner';
import type { EvolutionEvent } from '@/aii/types/api';

function toTimelineEvent(e: EvolutionEvent): TimelineEvent {
  // 把 body 放 detail,actor + kind 拼到 subtitle
  const subtitleParts: string[] = [];
  if (e.actor) subtitleParts.push(`by ${e.actor}`);
  subtitleParts.push(e.kind);
  return {
    id: e.id,
    time: e.time,
    title: e.title,
    subtitle: subtitleParts.join(' · '),
    status: e.status,
    detail: e.body,
  };
}

export default function EvolutionPage() {
  const [state, run] = useApiNoArg(api.getEvolution);

  useEffect(() => {
    void run();
  }, [run]);

  return (
    <div className="aii-page-content flex flex-col gap-6 max-w-4xl mx-auto">
      <header>
        <h1 className="text-xl font-semibold">进化 / Evolution</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          图的版本演进 — 接受 / 拒绝 / 回滚 全记录。
        </p>
      </header>

      {state.degraded && <DegradedBanner onRetry={() => void run()} />}

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run()} />}

      {state.data && (
        <>
          {/* 待决提案 */}
          {state.data.pending.length > 0 && (
            <section className="flex flex-col gap-2">
              <h2 className="text-sm font-medium uppercase tracking-wide opacity-70">
                待决 / Pending ({state.data.pending.length})
              </h2>
              <ul className="flex flex-col gap-2">
                {state.data.pending.map((e) => (
                  <li
                    key={e.id}
                    className="p-3 rounded border border-[color:var(--alert-warn,#d97706)] bg-[color:var(--bg-cell)] flex items-start gap-3"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium">{e.title}</div>
                      {e.body && (
                        <div className="text-xs text-[color:var(--text-secondary)] mt-1">{e.body}</div>
                      )}
                      <div className="text-[10px] opacity-60 mt-1">
                        {new Date(e.time).toLocaleString('zh-CN')}
                      </div>
                    </div>
                    {/* TODO: AII business logic — 接 governance/action 接受/拒绝 + OConfirmDialog */}
                    <div className="flex gap-2 shrink-0">
                      <button
                        type="button"
                        className="px-3 py-1 rounded text-xs border border-current"
                        onClick={() => {
                          // eslint-disable-next-line no-console
                          console.log('[evolution] accept', e.id);
                        }}
                      >
                        接受 / Accept
                      </button>
                      <button
                        type="button"
                        className="px-3 py-1 rounded text-xs border border-current opacity-70"
                        onClick={() => {
                          // eslint-disable-next-line no-console
                          console.log('[evolution] reject', e.id);
                        }}
                      >
                        拒绝 / Reject
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 历史时间线 */}
          <section className="flex flex-col gap-2">
            <h2 className="text-sm font-medium uppercase tracking-wide opacity-70">
              历史 / History
            </h2>
            {state.data.history.length === 0 ? (
              <OEmptyState variant="minimal" title="尚无历史事件" />
            ) : (
              <OEventTimeline events={state.data.history.map(toTimelineEvent)} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
