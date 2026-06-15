'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { LayoutGrid, Plus, Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ViewEditDialog } from '@/components/ViewEditDialog';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { EmptyState } from '@/components/EmptyState';
import { GridSkeleton } from '@/components/LoadingSkeleton';
import { listViews, deleteView, type View } from '@/lib/views';

export default function ViewsPage() {
  const router = useRouter();
  const [views, setViews] = useState<View[]>([]);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<View | null>(null);
  const [deleting, setDeleting] = useState<View | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setViews(await listViews()); }
    catch { toast.error('加载视图失败'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const presets = views.filter(v => v.is_preset).sort((a, b) => a.position - b.position);
  const custom = views.filter(v => !v.is_preset).sort((a, b) => a.position - b.position);

  const openCreate = () => { setEditing(null); setEditOpen(true); };
  const openEdit = (v: View, e: React.MouseEvent) => { e.stopPropagation(); setEditing(v); setEditOpen(true); };
  const askDelete = (v: View, e: React.MouseEvent) => {
    e.stopPropagation();
    if (v.is_preset) { toast.error('预设视图不能删除'); return; }
    setDeleting(v);
  };
  const confirmDelete = async () => {
    if (!deleting) return;
    try { await deleteView(deleting.id); toast.success('视图已删除'); load(); }
    catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? '删除失败');
    } finally { setDeleting(null); }
  };

  const goView = (v: View) => router.push(`/documents?view=${v.id}`);

  const ViewCard = ({ v }: { v: View }) => (
    <button
      onClick={() => goView(v)}
      className="relative text-left border rounded-lg p-4 hover:border-primary/50 transition-colors flex flex-col gap-1 min-h-[88px]"
    >
      <div className="flex items-center gap-2">
        <span className="text-lg">{v.icon ?? '📄'}</span>
        <span className="font-semibold">{v.name}</span>
      </div>
      {v.description && <span className="text-sm text-muted-foreground">{v.description}</span>}
      {v.filter_json?.medium && (
        <span className="text-xs text-muted-foreground mt-1">{v.filter_json.medium.join(', ')}</span>
      )}
      {!v.is_preset && (
        <div className="absolute top-2 right-2 flex gap-1">
          <span role="button" tabIndex={0} onClick={(e) => openEdit(v, e)}
            className="p-1.5 rounded hover:bg-muted min-h-9 min-w-9 flex items-center justify-center" aria-label="编辑">
            <Pencil className="w-4 h-4" />
          </span>
          <span role="button" tabIndex={0} onClick={(e) => askDelete(v, e)}
            className="p-1.5 rounded hover:bg-muted text-destructive min-h-9 min-w-9 flex items-center justify-center" aria-label="删除">
            <Trash2 className="w-4 h-4" />
          </span>
        </div>
      )}
    </button>
  );

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">视图</h1>
        <Button onClick={openCreate} className="min-h-11"><Plus className="w-4 h-4 mr-1" /> 新建视图</Button>
      </div>

      {loading ? <GridSkeleton /> : (
        <>
          <h2 className="text-sm font-semibold text-muted-foreground mb-3">预设视图</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-8">
            {presets.map(v => <ViewCard key={v.id} v={v} />)}
          </div>

          <h2 className="text-sm font-semibold text-muted-foreground mb-3">我的视图 ({custom.length})</h2>
          {custom.length === 0 ? (
            <EmptyState
              icon={<LayoutGrid />}
              title="还没有自定义视图"
              description="点「+ 新建视图」创建一个专属过滤组合。"
              action={{ label: '新建视图', onClick: openCreate }}
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {custom.map(v => <ViewCard key={v.id} v={v} />)}
            </div>
          )}
        </>
      )}

      <ViewEditDialog open={editOpen} view={editing} onClose={() => setEditOpen(false)} onSaved={load} />
      <ConfirmDialog
        open={!!deleting}
        title="删除视图"
        description={`确定删除「${deleting?.name}」？此操作不可撤销。`}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
