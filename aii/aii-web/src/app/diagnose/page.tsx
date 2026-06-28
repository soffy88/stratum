/**
 * /diagnose — 诊断 Page(REQ-001 P2)。
 *
 * 数据流(骨架):
 *   1. 用户输入 fragment_id 或选 scope(全局/聚簇/单片段)
 *   2. 提交 → run(diagnose({...}))
 *   3. 渲染 ORadarChart(多维诊断,红线 #3:无目标线/达标线)
 *
 * TODO for AII:
 *   - 加 OSearchableSelect 选 fragment
 *   - 多 series 对比(当前片段 vs 同 grade 中位数)
 *   - 加诊断 notes 区(state.data.notes)
 *   - 加点击 axis 跳详情
 *
 * 红线 #3 注意:
 *   ORadarChart 在 prop 层就不允许 referenceLine/targetZone(API 硬护栏)。
 *   组件 footer 永远显示 "不含目标线/达标线" disclaimer。
 */
'use client';

import { useState } from 'react';
import {
  ORadarChart,
  OEmptyState,
  OErrorState,
  OLoadingState,
} from '@helios/blocks';
import { useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import { DegradedBanner } from '@/components/DegradedBanner';

export default function DiagnosePage() {
  const [fragmentId, setFragmentId] = useState('');
  const [state, run] = useApi(api.diagnose);

  const onSubmit = () => {
    void run({
      fragment_id: fragmentId || undefined,
      scope: fragmentId ? 'fragment' : 'global',
    });
  };

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-4xl mx-auto">
      <header>
        <h1 className="text-xl font-semibold">诊断 / Diagnose</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          多维度认识论评估。不给目标线 — 只显客观度量(红线 #3)。
        </p>
      </header>

      <div className="flex gap-2 items-stretch">
        <input
          type="text"
          value={fragmentId}
          onChange={(e) => setFragmentId(e.target.value)}
          placeholder="fragment_id(留空诊断全局)"
          className="flex-1 px-3 py-2 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-cell)] font-mono text-sm"
        />
        <button
          type="button"
          onClick={onSubmit}
          disabled={state.loading}
          className="px-4 py-2 rounded bg-[color:var(--accent,#2563eb)] text-white text-sm font-medium disabled:opacity-50"
        >
          {state.loading ? '诊断中…' : '诊断 / Run'}
        </button>
      </div>

      {state.degraded && <DegradedBanner onRetry={onSubmit} />}

      {state.loading && <OLoadingState rows={3} />}
      {state.error && <OErrorState error={state.error} onRetry={onSubmit} />}
      {!state.loading && !state.data && !state.error && (
        <OEmptyState title="尚未诊断" description="选 fragment 或诊断全局" />
      )}

      {state.data && (
        <div className="flex flex-col gap-4">
          <ORadarChart
            axes={state.data.axes.map((a) => ({ label: a.axis }))}
            series={state.data.series.map((s) => ({
              name: s.name,
              values: s.values,
            }))}
            maxValue={1.0}
            showValueLabels
            // 注意:ORadarChart 不接受 referenceLine / targetZone / thresholdBand prop
            // (API 硬护栏,红线 #3)。组件自带 footer disclaimer
            //   "仅显示客观数值,不含目标线/达标线"
          />
          {state.data.notes && state.data.notes.length > 0 && (
            <ul className="text-xs text-[color:var(--text-secondary)] list-disc pl-5">
              {state.data.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
