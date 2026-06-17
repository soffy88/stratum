/**
 * /governance — 治理 Page(REQ-001 P3)。
 *
 * 数据流(骨架):
 *   1. 用户选 action(quarantine / promote / rollback / delete)+ target_id + reason
 *   2. 点提交 → OConfirmDialog 二次确认(danger 风格)
 *   3. 确认后 → run(governanceAction({...})) → 显示 audit_log_id
 *
 * TODO for AII:
 *   - 联动 Health / Evolution 跳过来时自动填 target_id
 *   - reason 文本框加 validator(必填 + 长度)
 *   - audit_log 列表预留(可能后端再加一个 /governance/audit-log GET)
 *   - rollback 之前显示影响范围(联动 diagnose)
 */
'use client';

import { useState } from 'react';
import {
  OConfirmDialog,
  OEmptyState,
  OErrorState,
  OLoadingState,
} from '@helios/blocks';
import { useApi } from '@/hooks/useApi';
import * as api from '@/lib/api-client';
import { DegradedBanner } from '@/components/DegradedBanner';
import type { GovernanceActionRequest } from '@/types/api';

const ACTIONS: Array<{ value: GovernanceActionRequest['action']; label: string; danger: boolean }> = [
  { value: 'promote', label: '提升 / Promote', danger: false },
  { value: 'quarantine', label: '隔离 / Quarantine', danger: false },
  { value: 'rollback', label: '回滚 / Rollback', danger: true },
  { value: 'delete', label: '删除 / Delete', danger: true },
];

export default function GovernancePage() {
  const [action, setAction] = useState<GovernanceActionRequest['action']>('quarantine');
  const [targetId, setTargetId] = useState('');
  const [reason, setReason] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [state, run] = useApi(api.governanceAction);

  const selected = ACTIONS.find((a) => a.value === action)!;
  const valid = targetId.trim().length > 0 && reason.trim().length > 0;

  const onSubmit = () => {
    if (!valid) return;
    setConfirmOpen(true);
  };

  const onConfirm = async () => {
    setConfirmOpen(false);
    await run({ action, target_id: targetId, reason });
  };

  return (
    <div className="aii-page-content flex flex-col gap-4 max-w-3xl mx-auto">
      <header>
        <h1 className="text-xl font-semibold">治理 / Governance</h1>
        <p className="text-sm text-[color:var(--text-secondary)]">
          对图的人工干预。所有操作都会写审计日志(红线 #5)。
        </p>
      </header>

      <div className="flex flex-col gap-3 p-4 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-cell)]">
        <label className="flex flex-col gap-1 text-sm">
          <span>操作 / Action</span>
          <select
            value={action}
            onChange={(e) => setAction(e.target.value as GovernanceActionRequest['action'])}
            className="px-3 py-2 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-base)]"
          >
            {ACTIONS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span>目标 ID / Target ID</span>
          <input
            type="text"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            placeholder="例如:frag-002"
            className="px-3 py-2 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-base)] font-mono text-sm"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span>原因 / Reason *</span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="必填 — 审计日志会记录此原因"
            className="px-3 py-2 rounded border border-[color:var(--border-strong)] bg-[color:var(--bg-base)] text-sm"
          />
        </label>

        <button
          type="button"
          onClick={onSubmit}
          disabled={!valid || state.loading}
          className={[
            'px-4 py-2 rounded text-sm font-medium text-white disabled:opacity-50',
            selected.danger
              ? 'bg-[color:var(--alert-error,#dc2626)]'
              : 'bg-[color:var(--accent,#2563eb)]',
          ].join(' ')}
        >
          {state.loading ? '处理中…' : `执行 ${selected.label}`}
        </button>
      </div>

      {state.degraded && <DegradedBanner />}

      {state.loading && <OLoadingState variant="spinner" />}
      {state.error && <OErrorState error={state.error} />}
      {state.data && (
        <div className="p-3 rounded border border-[color:var(--alert-success,#16a34a)] bg-[color:var(--bg-cell)] text-sm">
          <div className="font-medium">已执行 / Applied: {String(state.data.applied)}</div>
          <div className="text-xs font-mono opacity-75 mt-1">
            审计 ID: {state.data.audit_log_id}
          </div>
        </div>
      )}

      {!state.loading && !state.data && !state.error && (
        <OEmptyState
          variant="minimal"
          title="尚未执行任何操作"
          description="选择 action / 填 target / 写原因 → 执行"
        />
      )}

      {/* 红线 #5:所有治理操作前都要二次确认 + 写原因 */}
      <OConfirmDialog
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={onConfirm}
        title={`确认 ${selected.label}?`}
        description={`目标:${targetId}\n原因:${reason}\n\n此操作会写入审计日志,且部分操作(rollback/delete)不可逆。`}
        danger={selected.danger}
      />
    </div>
  );
}
