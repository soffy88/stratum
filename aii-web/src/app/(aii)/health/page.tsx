/**
 * /health — 图健康度 Page(REQ-001 P1)。
 *
 * 数据流(骨架):
 *   1. mount 时自动 fetch /graph/health
 *   2. 渲染:OEpistemicDistribution + 健康总分 + 反证总数 + 上次审计时间
 *   3. degraded → DegradedBanner(图统计也可能因 LLM 不可用而降级)
 *
 * TODO for AII:
 *   - 接 OKPICard 显示 total_nodes / total_edges / defeater_count / health_score
 *   - OEpistemicDistribution 点击 segment 跳 Query Page 过滤该 grade
 *   - 加趋势图(7d health_score 折线,用 OAnimatedChart 或自己写 svg)
 *   - 加「手动触发审计」按钮(governance/action 触发)
 */
'use client';

import { useEffect } from 'react';
import {
  OEpistemicDistribution,
  OEmptyState,
  OErrorState,
  OLoadingState,
} from '@helios/blocks';
import { useApiNoArg } from '@/aii/hooks/useApi';
import * as api from '@/aii/lib/api-client';
import { DegradedBanner } from '@/aii/components/DegradedBanner';

export default function HealthPage() {
  const [state, run] = useApiNoArg(api.getGraphHealth);

  useEffect(() => {
    void run();
  }, [run]);

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-5xl mx-auto">
      <header>
        <h1 className="text-xl font-semibold">图健康 / Graph Health</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          认识论可信度分布与图整体状态概览。
        </p>
      </header>

      {state.degraded && <DegradedBanner onRetry={() => void run()} />}

      {state.loading && <OLoadingState rows={4} />}
      {state.error && <OErrorState error={state.error} onRetry={() => void run()} />}
      {!state.loading && !state.error && !state.data && (
        <OEmptyState title="尚无数据" description="刷新或检查后端连接" />
      )}

      {state.data && (
        <div className="flex flex-col gap-6">
          {/* 顶部 KPI 行 — TODO: AII business logic — 换成 OKPICard */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPIBlock label="总节点 / Nodes" value={state.data.total_nodes} />
            <KPIBlock label="总边 / Edges" value={state.data.total_edges} />
            <KPIBlock label="反证 / Defeaters" value={state.data.defeater_count} />
            <KPIBlock
              label="健康分 / Score"
              value={
                state.data.health_score !== undefined
                  ? `${(state.data.health_score * 100).toFixed(0)}%`
                  : '—'
              }
            />
          </div>

          {/* 可信度分布 */}
          <section className="flex flex-col gap-2">
            <h2 className="text-sm font-medium uppercase tracking-wide opacity-70">
              可信度分布 / Confidence distribution
            </h2>
            <OEpistemicDistribution
              counts={state.data.grade_distribution}
              // TODO: AII business logic — onSegmentClick={(grade) => router.push(`/query?grade=${grade}`)}
              onSegmentClick={(grade, count) => {
                // eslint-disable-next-line no-console
                console.log('[health] clicked', grade, count);
              }}
            />
          </section>

          {state.data.last_audit_at && (
            <p className="text-xs text-[color:var(--text-secondary)]">
              上次审计 / Last audit: {new Date(state.data.last_audit_at).toLocaleString('zh-CN')}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function KPIBlock({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-3 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-cell)]">
      <div className="text-[10px] uppercase tracking-wide text-[color:var(--text-secondary)]">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}
