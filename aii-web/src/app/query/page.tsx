/**
 * /query — 查询 Page(REQ-001 P0 高优先级)。
 *
 * 数据流(starter 给的骨架,业务逻辑你填):
 *   1. 用户在 OSearchBar 输入 query → onChange (debounced)
 *   2. 点击「查询」按钮 → run(query({...})) → state.data.items
 *   3. 渲染 OEpistemicCard 列表(每条片段一个 Card)
 *   4. state.degraded → 顶部 <DegradedBanner />(红线 #6)
 *
 * TODO for AII:
 *   - 把 mock query 改成 AII 真实业务 query 流
 *   - 实现 filters UI(date / source / grade 过滤)
 *   - 点击 Card 跳详情 / 高亮 fragment
 *   - 红线 #4(措辞)在后端 prompt 层做;前端这里不用管
 */
'use client';

import { useState } from 'react';
import {
  OSearchBar,
  OEpistemicCard,
  OEmptyState,
  OLoadingState,
  OErrorState,
} from '@helios/blocks';
import { useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import { DegradedBanner } from '@/components/DegradedBanner';
import type { QueryResultItem } from '@/types/api';

export default function QueryPage() {
  const [q, setQ] = useState('');
  const [state, run] = useApi(api.query);

  const onSubmit = () => {
    if (!q.trim()) return;
    void run({ query: q, k: 10 });
  };

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-4xl mx-auto">
      <header className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold">查询 / Query</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          基于认识论可信度的知识检索。Mock 模式提示:输入含 &quot;degraded&quot; 的 query 会触发降级 banner。
        </p>
      </header>

      <div className="flex gap-2 items-stretch">
        <div className="flex-1">
          <OSearchBar
            value={q}
            onChange={setQ}
            placeholder="输入查询内容…"
            debounceMs={0}
          />
        </div>
        <button
          type="button"
          onClick={onSubmit}
          disabled={state.loading || !q.trim()}
          className="px-4 py-2 rounded bg-[color:var(--accent,#2563eb)] text-white text-sm font-medium disabled:opacity-50"
        >
          {state.loading ? '查询中…' : '查询 / Query'}
        </button>
      </div>

      {/* 红线 #6:降级时醒目提示,不静默 */}
      {state.degraded && <DegradedBanner onRetry={onSubmit} />}

      {/* 结果区:loading / error / empty / data 四态 */}
      {state.loading && <OLoadingState rows={3} />}
      {state.error && <OErrorState error={state.error} onRetry={onSubmit} />}
      {!state.loading && !state.error && state.data && state.data.items.length === 0 && (
        <OEmptyState title="没有匹配的片段" description="尝试调整关键词或过滤条件" />
      )}
      {!state.loading && state.data && state.data.items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {state.data.items.map((item: QueryResultItem) => (
            <li key={item.id}>
              <OEpistemicCard
                title={item.title}
                body={item.body}
                grade={item.grade}
                defeaters={item.defeaters}
                source={item.source}
                metadata={item.metadata}
                // emphasize="auto" — 默认行为,unverified/contradicted 自动加警示边框
                // TODO: AII business logic — 点击跳详情
                onClick={() => {
                  // eslint-disable-next-line no-console
                  console.log('[query] clicked', item.id);
                }}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
