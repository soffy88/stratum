/**
 * /dashboard — 概览仪表盘(AII-FRONTEND-DISPLAY-001 §一)。
 *
 * ★命门:可信度分布卡片醒目呈现"绝大部分未确证"——不回避、不美化。
 *
 * 数据:GET /api/stats/overview + /api/stats/ingestion(后端待实现;mock 模式可跑)。
 * 布局:OGridFrame 响应式网格(blocks 2.0.0,等价文档点名的 OWidgetGrid)。
 */
'use client';

import { useEffect } from 'react';
import {
  OGridFrame,
  OKPICard,
  OEpistemicDistribution,
  OEmptyState,
  OLoadingState,
  OErrorState,
} from '@helios/blocks';
import { useApiNoArg } from '@/hooks/useApi';
import { AnimatedNumber, useStaggerReveal } from '@/components/motion/Motion';
import * as api from '@/lib/api-client';

function Card({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="dash-card rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && <span className="text-xs text-[color:var(--text-tertiary,#888)]">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

export default function DashboardPage() {
  const [overview, runOverview] = useApiNoArg(api.getStatsOverview);
  const [ingestion, runIngestion] = useApiNoArg(api.getStatsIngestion);

  useEffect(() => { void runOverview(); void runIngestion(); }, [runOverview, runIngestion]);

  // 数据到达后,区块卡片交错入场(降级安全:未装 animejs / reduced-motion 时元素本就可见)
  useStaggerReveal('.dash-card', [overview.data], { delay: 70, translateY: 14 });

  const d = overview.data;
  const ing = ingestion.data;

  return (
    <div className="aii-page-content flex flex-col gap-5 max-w-6xl mx-auto">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">概览 / Knowledge Overview</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          知识库成果总览。<strong>可信度分布是 AII 的诚实窗口</strong> —— 大部分知识尚未确证,如实呈现。
        </p>
      </header>

      {overview.loading && <OLoadingState rows={4} />}
      {overview.error && <OErrorState error={overview.error} onRetry={() => void runOverview()} />}

      {d && (
        <>
          {/* KPI 行:知识总量 */}
          <OGridFrame cols={{ sm: 2, md: 4 }} gap="md">
            <OKPICard data={{ label: 'KU 知识单元', primary: d.ku_count }} />
            <OKPICard data={{ label: '关系边', primary: d.edge_count }} />
            <OKPICard data={{ label: 'KC 知识簇', primary: d.kc_count }} />
            <OKPICard data={{ label: 'BU 书级理解', primary: d.bu_count }} />
          </OGridFrame>

          <OGridFrame cols={{ sm: 1, md: 2 }} gap="md">
            {/* ★命门:可信度分布(醒目) */}
            <Card title="可信度分布 / Epistemic Grade" hint="诚实窗口">
              <OEpistemicDistribution counts={d.grade_dist} height={28} showLegend />
              <p className="text-xs text-[color:var(--text-tertiary,#888)] leading-relaxed">
                共 {d.ku_count.toLocaleString()} 条 KU,其中 proven 仅 {d.grade_dist.proven ?? 0} 条、
                unverified {(d.grade_dist.unverified ?? 0).toLocaleString()} 条。
                <span className="text-[color:var(--alert-warn,#d97706)]"> 绝大多数尚未确证 —— 确证终审待批量推进。</span>
              </p>
            </Card>

            {/* ★矛盾发现(诚实亮点) */}
            <Card title="矛盾发现 / Contradictions" hint="AII 发现的知识冲突">
              <div className="flex items-end gap-2">
                <span className="text-3xl font-bold text-[color:var(--alert-error,#dc2626)] tabular-nums">
                  <AnimatedNumber value={d.relation_type_dist.contradicts ?? 0} duration={900} />
                </span>
                <span className="text-sm text-[color:var(--text-secondary)] mb-1">条 contradicts 边</span>
              </div>
              <p className="text-xs text-[color:var(--text-tertiary,#888)] leading-relaxed">
                AII 主动标注的知识冲突。发现矛盾不是缺陷,而是知识库自我审视能力的体现。
              </p>
            </Card>

            {/* 查重成效 */}
            <Card title="查重成效 / Deduplication" hint="去重析出内核">
              <div className="flex gap-6">
                <div>
                  <div className="text-2xl font-bold tabular-nums"><AnimatedNumber value={d.merge_count} /></div>
                  <div className="text-xs text-[color:var(--text-secondary)]">合并 KU 数</div>
                </div>
                <div>
                  <div className="text-2xl font-bold tabular-nums text-[color:var(--success,#16a34a)]">
                    <AnimatedNumber value={d.dedup_saved} />
                  </div>
                  <div className="text-xs text-[color:var(--text-secondary)]">节省条数</div>
                </div>
              </div>
            </Card>

            {/* 关系类型分布 */}
            <Card title="关系类型分布 / Relation Types">
              <ul className="flex flex-col gap-1.5">
                {Object.entries(d.relation_type_dist)
                  .sort((a, b) => b[1] - a[1])
                  .map(([rel, n]) => {
                    const isContra = rel === 'contradicts';
                    const max = Math.max(...Object.values(d.relation_type_dist));
                    return (
                      <li key={rel} className="flex items-center gap-2 text-xs">
                        <span className={`w-32 shrink-0 ${isContra ? 'text-[color:var(--alert-error,#dc2626)] font-medium' : ''}`}>{rel}</span>
                        <span className="flex-1 h-2 rounded-full bg-[color:var(--muted,#222)] overflow-hidden">
                          <span
                            className="block h-full rounded-full"
                            style={{
                              width: `${(n / max) * 100}%`,
                              background: isContra ? 'var(--alert-error,#dc2626)' : 'var(--accent,#2563eb)',
                            }}
                          />
                        </span>
                        <span className="w-12 text-right tabular-nums text-[color:var(--text-secondary)]">{n.toLocaleString()}</span>
                      </li>
                    );
                  })}
              </ul>
            </Card>
          </OGridFrame>

          {/* 摄取进度 */}
          <Card title="摄取进度 / Ingestion" hint="按介质">
            {ingestion.loading && <OLoadingState rows={2} />}
            {ing && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-[color:var(--text-secondary)] w-20">总文件</span>
                  <span className="flex-1 h-3 rounded-full bg-[color:var(--muted,#222)] overflow-hidden">
                    <span className="block h-full bg-[color:var(--accent,#2563eb)]" style={{ width: `${(ing.ingested / ing.total_files) * 100}%` }} />
                  </span>
                  <span className="text-sm tabular-nums">{ing.ingested}/{ing.total_files}</span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  {Object.entries(ing.by_medium).map(([m, v]) => (
                    <div key={m} className="rounded-md border border-[color:var(--border)] p-2">
                      <div className="text-xs text-[color:var(--text-secondary)] capitalize">{m}</div>
                      <div className="text-lg font-semibold tabular-nums">{v.ingested}<span className="text-xs text-[color:var(--text-tertiary,#888)]">/{v.total}</span></div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-[color:var(--text-tertiary,#888)]">
                  深度理解(BU)已生成 {ing.deep_understood} 本。
                  <span className="text-[color:var(--text-tertiary,#888)]"> 注:暂无学科字段,按介质展示(后端待加 subject)。</span>
                </p>
              </div>
            )}
          </Card>
        </>
      )}

      {!overview.loading && !overview.error && !d && (
        <OEmptyState title="暂无统计数据" description="后端 /api/stats/overview 待实现" />
      )}
    </div>
  );
}
