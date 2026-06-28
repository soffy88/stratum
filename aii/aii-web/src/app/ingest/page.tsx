/**
 * /ingest — 摄入 Page(REQ-001 P0 高优先级)。
 *
 * 数据流(骨架):
 *   1. 文本框输入 source + text(或后续支持 OFileUpload)
 *   2. 提交 → run(ingest({...})) → 显示 ingested_count + fragment_ids
 *   3. rejected 数组里有内容 → 列出原因
 *   4. degraded → DegradedBanner
 *
 * TODO for AII:
 *   - 加文件上传(OFileUpload 组件可直接用,见 @helios/blocks)
 *   - 加 metadata 表单(date / tags / language)
 *   - 提交成功后清空表单 / 跳转 Query Page 查刚摄入的
 *   - 红线 #5(摄入审计)— 后端会写审计日志,前端拿 fragment_ids 就够了
 */
'use client';

import { useState } from 'react';
import { OEmptyState, OErrorState, OLoadingState } from '@helios/blocks';
import { useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import { DegradedBanner } from '@/components/DegradedBanner';

export default function IngestPage() {
  const [source, setSource] = useState('');
  const [text, setText] = useState('');
  const [state, run] = useApi(api.ingest);

  const onSubmit = () => {
    if (!text.trim()) return;
    void run({ source: source || 'manual_input', text });
  };

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-3xl mx-auto">
      <header>
        <h1 className="text-xl font-semibold">摄入 / Ingest</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          往知识图谱投入新片段。每行一条候选。
        </p>
      </header>

      <label className="flex flex-col gap-1 text-sm">
        <span>来源 / Source</span>
        <input
          type="text"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="例如:cb_research_2024.pdf §3.2"
          className="px-3 py-2 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-cell)]"
        />
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span>内容 / Text</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder="每行一条候选片段…"
          className="px-3 py-2 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-cell)] font-mono text-sm"
        />
      </label>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onSubmit}
          disabled={state.loading || !text.trim()}
          className="px-4 py-2 rounded bg-[color:var(--accent,#2563eb)] text-white text-sm font-medium disabled:opacity-50"
        >
          {state.loading ? '摄入中…' : '提交 / Submit'}
        </button>
        {/* TODO: AII business logic — 加文件上传按钮,用 <OFileUpload> */}
      </div>

      {state.degraded && <DegradedBanner onRetry={onSubmit} />}

      {state.loading && <OLoadingState rows={2} />}
      {state.error && <OErrorState error={state.error} onRetry={onSubmit} />}
      {state.data && (
        <div className="flex flex-col gap-3 mt-4 p-4 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-cell)]">
          <div className="text-sm">
            <span className="font-medium">已摄入 / Ingested:</span> {state.data.ingested_count} 条
          </div>
          {state.data.fragment_ids.length > 0 && (
            <ul className="text-xs font-mono opacity-75 list-disc pl-5 max-h-32 overflow-auto">
              {state.data.fragment_ids.map((id) => (
                <li key={id}>{id}</li>
              ))}
            </ul>
          )}
          {state.data.rejected && state.data.rejected.length > 0 && (
            <div className="text-sm text-[color:var(--alert-warn,#d97706)]">
              <div className="font-medium">已拒绝 / Rejected ({state.data.rejected.length}):</div>
              <ul className="list-disc pl-5">
                {state.data.rejected.map((r, i) => (
                  <li key={i}>
                    {r.reason}
                    {r.preview && <span className="opacity-60"> — {r.preview}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {!state.loading && !state.data && !state.error && (
        <OEmptyState
          variant="minimal"
          title="尚未提交 / Nothing submitted yet"
          description="填好上面的内容点提交"
        />
      )}
    </div>
  );
}
