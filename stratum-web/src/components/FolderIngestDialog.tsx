'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';

type Phase = 'input' | 'submitting' | 'done' | 'error';

export function FolderIngestDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess?: () => void;
}) {
  const [path, setPath] = useState('');
  const [description, setDescription] = useState('');
  const [phase, setPhase] = useState<Phase>('input');
  const [errorMsg, setErrorMsg] = useState('');

  async function handleSubmit() {
    if (!path.trim()) return;
    setPhase('submitting');
    setErrorMsg('');
    try {
      await apiClient.post('/api/v1/folder-watch', {
        path: path.trim(),
        description: description.trim() || undefined,
      });
      setPhase('done');
      toast.success('已开始监听，系统自动扫描入库');
      onSuccess?.();
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setPhase('error');
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-lg p-6 w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold">监听文件夹</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-foreground)] text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Input */}
        {phase === 'input' && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                本地路径或网盘链接
              </label>
              <input
                type="text"
                placeholder="/home/soffy/papers/ 或网盘链接"
                value={path}
                onChange={e => setPath(e.target.value)}
                autoFocus
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)]"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                告知要找什么（可选）
              </label>
              <textarea
                placeholder="例：量化金融论文、BTC 技术分析、Python 教程"
                value={description}
                onChange={e => setDescription(e.target.value)}
                rows={3}
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)] resize-none"
              />
            </div>
            <button
              onClick={handleSubmit}
              disabled={!path.trim()}
              className="w-full py-2 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50"
            >
              开始监听
            </button>
          </div>
        )}

        {/* Submitting */}
        {phase === 'submitting' && (
          <div className="flex items-center gap-3 py-6 justify-center">
            <div className="w-5 h-5 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-[var(--color-muted)]">正在提交...</p>
          </div>
        )}

        {/* Done */}
        {phase === 'done' && (
          <div className="space-y-3">
            <div className="p-4 bg-green-50 border border-green-200 rounded">
              <p className="text-sm font-semibold text-green-800">✓ 已开始监听</p>
              <p className="text-xs text-green-700 mt-1">系统将自动扫描该路径并将文件入库</p>
            </div>
            <button
              onClick={onClose}
              className="w-full py-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)]"
            >
              关闭
            </button>
          </div>
        )}

        {/* Error */}
        {phase === 'error' && (
          <div className="space-y-3">
            <div className="p-4 bg-red-50 border border-red-200 rounded">
              <p className="text-sm font-medium text-red-800">提交失败</p>
              <p className="text-xs text-red-700 mt-1">{errorMsg}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPhase('input')}
                className="flex-1 py-2 bg-[var(--color-primary)] text-white rounded text-sm"
              >
                重试
              </button>
              <button
                onClick={onClose}
                className="flex-1 py-2 border border-[var(--color-border)] rounded text-sm"
              >
                关闭
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
