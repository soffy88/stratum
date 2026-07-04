'use client';

/**
 * /documents 页改造 — 增加 View Banner 支持。
 *
 * 注:这是在现有 documents 页基础上加 View Banner 的参考实现。
 * 若现有页已有文档列表/上传逻辑,把 View Banner 部分(标 ★)合并进去即可。
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { listViews, type View } from '@/lib/views';
import { CardSkeleton } from '@/components/LoadingSkeleton';

interface Substrate {
  id: string;
  title: string;
  medium?: string;
  created_at?: string;
}

export default function DocumentsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const viewId = searchParams.get('view');

  const [docs, setDocs] = useState<Substrate[]>([]);
  const [total, setTotal] = useState(0);
  const [currentView, setCurrentView] = useState<View | null>(null);
  const [loading, setLoading] = useState(true);

  // ★ 解析当前 view 元信息(用于 Banner)
  useEffect(() => {
    if (!viewId) { setCurrentView(null); return; }
    listViews().then(vs => setCurrentView(vs.find(v => v.id === viewId) ?? null)).catch(() => {});
  }, [viewId]);

  // 拉文档(带 view filter)
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get<{ items: Substrate[]; total: number }>('/api/v1/documents', {
        params: { view: viewId, limit: 50, offset: 0 },
      });
      setDocs(res.data.items);
      setTotal(res.data.total);
    } catch { toast.error('加载文档失败'); }
    finally { setLoading(false); }
  }, [viewId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <h1 className="text-xl font-bold mb-4">文档</h1>

      {/* ★ View Banner */}
      {viewId && currentView && (
        <div className="flex items-center gap-2 px-4 py-2 bg-muted rounded-lg mb-4">
          <span className="font-medium">{currentView.icon} {currentView.name}</span>
          <span className="text-muted-foreground text-sm">· {total} 篇文档</span>
          <button
            onClick={() => router.push('/documents')}
            className="ml-auto text-sm text-primary hover:underline min-h-9 px-2"
          >
            清除视图
          </button>
        </div>
      )}

      {loading ? <CardSkeleton count={5} /> : (
        <div className="flex flex-col gap-2">
          {docs.map(d => (
            <button key={d.id} onClick={() => router.push(`/documents/${d.id}`)}
              className="text-left border rounded-lg p-3 hover:border-primary/50 transition-colors min-h-11">
              <div className="font-medium">{d.title}</div>
              {d.medium && <span className="text-xs text-muted-foreground">{d.medium}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
