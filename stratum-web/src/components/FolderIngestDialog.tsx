'use client';

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';

type Phase = 'input' | 'submitting' | 'error';

interface Watch {
  id: string;
  path: string;
  description?: string | null;
  status: string;
  last_scan_at?: string | null;
  file_count: number;
}

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
  const [watches, setWatches] = useState<Watch[]>([]);

  const loadWatches = useCallback(async () => {
    try {
      const rows = await apiClient.get<Watch[]>('/api/v1/folder-watch');
      setWatches(rows);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => { void loadWatches(); }, [loadWatches]);

  async function handleSubmit() {
    if (!path.trim()) return;
    setPhase('submitting');
    setErrorMsg('');
    try {
      await apiClient.post('/api/v1/folder-watch', {
        path: path.trim(),
        description: description.trim() || undefined,
      });
      setPath('');
      setDescription('');
      setPhase('input');
      toast.success('已开始监听，系统将自动扫描入库');
      onSuccess?.();
      await loadWatches();
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setPhase('error');
    }
  }

  async function handleDelete(id: string) {
    try {
      await apiClient.delete(`/api/v1/folder-watch/${id}`);
      await loadWatches();
    } catch {
      toast.error('删除失败');
    }
  }

  async function handleToggle(w: Watch) {
    const endpoint = w.status === 'active' ? 'pause' : 'resume';
    try {
      await apiClient.patch(`/api/v1/folder-watch/${w.id}/${endpoint}`, {});
      await loadWatches();
    } catch {
      toast.error('操作失败');
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-lg p-6 w-full max-w-lg shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold">监听文件夹</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-foreground)] text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Path hint */}
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800 space-y-1">
          <p className="font-medium">路径填写说明</p>
          <p>· 填写容器内可访问路径，不是 Windows 路径</p>
          <p>· Windows <code className="font-mono">D:\books</code> → WSL2 <code className="font-mono">/mnt/d/books</code> → 容器 <code className="font-mono">/mnt/user/books</code></p>
          <p>· Linux/WSL2 <code className="font-mono">/home/soffy/papers</code> → 容器 <code className="font-mono">/mnt/user/papers</code></p>
        </div>

        {/* Input form */}
        <div className="space-y-3 mb-6">
          <div>
            <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
              容器内路径
            </label>
            <input
              type="text"
              placeholder="/mnt/user/papers 或 /mnt/user/books/数学"
              value={path}
              onChange={e => setPath(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && void handleSubmit()}
              autoFocus
              disabled={phase === 'submitting'}
              className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)] disabled:opacity-50"
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
              rows={2}
              disabled={phase === 'submitting'}
              className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)] resize-none disabled:opacity-50"
            />
          </div>

          {phase === 'error' && (
            <p className="text-xs text-red-600">{errorMsg}</p>
          )}

          <button
            onClick={() => void handleSubmit()}
            disabled={!path.trim() || phase === 'submitting'}
            className="w-full py-2 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {phase === 'submitting' && (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
            )}
            开始监听
          </button>
        </div>

        {/* Watch list */}
        {watches.length > 0 && (
          <div>
            <p className="text-xs font-medium text-[var(--color-muted)] mb-2">
              监听中 ({watches.length})
            </p>
            <ul className="space-y-2">
              {watches.map(w => (
                <li key={w.id} className="border border-[var(--color-border)] rounded p-3 text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs truncate">{w.path}</p>
                      {w.description && (
                        <p className="text-[var(--color-muted)] text-xs mt-0.5">{w.description}</p>
                      )}
                      <p className="text-xs text-[var(--color-muted)] mt-1">
                        {w.file_count} 个文件
                        {w.last_scan_at
                          ? ` · 上次扫描 ${new Date(w.last_scan_at).toLocaleString('zh-CN')}`
                          : ' · 等待首次扫描'}
                      </p>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <button
                        onClick={() => void handleToggle(w)}
                        className="text-xs px-2 py-1 border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)] transition"
                      >
                        {w.status === 'active' ? '暂停' : '恢复'}
                      </button>
                      <button
                        onClick={() => void handleDelete(w.id)}
                        className="text-xs px-2 py-1 border border-red-200 text-red-600 rounded hover:bg-red-50 transition"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                  <span className={`inline-block mt-1 text-xs px-1.5 py-0.5 rounded ${
                    w.status === 'active'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}>
                    {w.status === 'active' ? '监听中' : '已暂停'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
