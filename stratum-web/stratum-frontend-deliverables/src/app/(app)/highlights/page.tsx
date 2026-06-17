'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Highlighter, Trash2 } from 'lucide-react';
import { EmptyState } from '@/components/EmptyState';
import { CardSkeleton } from '@/components/LoadingSkeleton';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { listHighlights, deleteHighlight, type Highlight } from '@/lib/highlights';

const COLOR_MAP: Record<string, { dot: string; card: string }> = {
  yellow:  { dot: '🟡', card: 'bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-900/40' },
  blue:    { dot: '🔵', card: 'bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-900/40' },
  green:   { dot: '🟢', card: 'bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-900/40' },
  red:     { dot: '🔴', card: 'bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-900/40' },
  default: { dot: '⚪', card: 'bg-gray-50 border-gray-200 dark:bg-gray-900/20 dark:border-gray-800' },
};

export default function HighlightsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Highlight[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<Highlight | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listHighlights();
      // 按创建时间倒序
      data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setItems(data);
    } catch { toast.error('加载高亮失败'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const confirmDelete = async () => {
    if (!deleting) return;
    try { await deleteHighlight(deleting.id); toast.success('已删除'); load(); }
    catch { toast.error('删除失败'); }
    finally { setDeleting(null); }
  };

  return (
    <div className="p-4 sm:p-6 max-w-3xl mx-auto">
      <h1 className="text-xl font-bold mb-6">高亮</h1>

      {loading ? <CardSkeleton count={3} /> : items.length === 0 ? (
        <EmptyState
          icon={<Highlighter />}
          title="还没有高亮标记"
          description="在文档详情页选中文字后可以添加高亮。"
        />
      ) : (
        <div className="flex flex-col gap-3">
          {items.map(h => {
            const c = COLOR_MAP[h.color] ?? COLOR_MAP.default;
            return (
              <div key={h.id} className={`border rounded-lg p-4 ${c.card}`}>
                <div className="flex gap-2">
                  <span className="shrink-0">{c.dot}</span>
                  <p className="text-sm leading-relaxed flex-1">&ldquo;{h.text}&rdquo;</p>
                </div>
                {h.note && (
                  <p className="text-sm text-muted-foreground mt-3 pl-6">笔记: {h.note}</p>
                )}
                <div className="flex items-center justify-between mt-3 pl-6">
                  <button
                    onClick={() => router.push(`/documents/${h.substrate_id}`)}
                    className="text-sm text-primary hover:underline"
                  >
                    来源: {h.substrate_title ?? h.substrate_id}
                  </button>
                  <button
                    onClick={() => setDeleting(h)}
                    className="text-sm text-destructive hover:underline flex items-center gap-1 min-h-9 px-2"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> 删除
                  </button>
                </div>
                <p className="text-xs text-muted-foreground mt-1 pl-6">
                  {new Date(h.created_at).toLocaleDateString('zh-CN')}
                </p>
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        open={!!deleting}
        title="删除高亮"
        description="确定删除这条高亮？此操作不可撤销。"
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
