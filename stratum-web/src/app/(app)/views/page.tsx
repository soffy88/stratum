"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listViews, deleteView, type View } from "@/lib/views";
import { ViewEditDialog } from "@/components/ViewEditDialog";

export default function ViewsPage() {
  const [views, setViews] = useState<View[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingView, setEditingView] = useState<View | null>(null);
  const [creating, setCreating] = useState(false);
  const router = useRouter();

  const load = () => {
    setLoading(true);
    listViews().then((d) => { setViews(d); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(load, []);

  const handleApply = (v: View) => router.push(`/documents?view=${v.id}`);

  const handleDelete = async (v: View) => {
    if (!confirm(`删除"${v.name}"?`)) return;
    await deleteView(v.id);
    load();
  };

  const presets = views.filter((v) => v.is_preset);
  const custom = views.filter((v) => !v.is_preset);

  if (loading) return <p className="p-6 text-[var(--color-muted)] text-sm">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">视图</h1>
        <button onClick={() => setCreating(true)}
          className="text-sm px-3 py-1.5 bg-[var(--color-primary)] text-white rounded hover:opacity-90">
          + 新建视图
        </button>
      </div>

      <section className="mb-8">
        <h2 className="text-sm font-medium text-[var(--color-muted)] mb-3">预设视图</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {presets.map((v) => <ViewCard key={v.id} view={v} onApply={handleApply} />)}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-[var(--color-muted)] mb-3">
          我的视图{custom.length > 0 && ` (${custom.length})`}
        </h2>
        {custom.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">还没有自定义视图。</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {custom.map((v) => (
              <ViewCard key={v.id} view={v} onApply={handleApply}
                onEdit={() => setEditingView(v)}
                onDelete={() => void handleDelete(v)} />
            ))}
          </div>
        )}
      </section>

      {(creating || editingView) && (
        <ViewEditDialog
          view={editingView}
          onClose={() => { setCreating(false); setEditingView(null); }}
          onSaved={() => { setCreating(false); setEditingView(null); load(); }}
        />
      )}
    </div>
  );
}

function ViewCard({ view, onApply, onEdit, onDelete }: {
  view: View;
  onApply: (v: View) => void;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  const filterTags = view.filter_json?.tags as string[] | undefined;
  const filterMediums = view.filter_json?.medium as string[] | undefined;
  return (
    <div onClick={() => onApply(view)}
      className="p-4 border border-[var(--color-border)] rounded bg-[var(--color-surface)] cursor-pointer hover:shadow-md transition group">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          {view.icon && <span className="text-xl">{view.icon}</span>}
          <h3 className="font-medium text-sm">{view.name}</h3>
        </div>
        {(onEdit || onDelete) && (
          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition"
            onClick={(e) => e.stopPropagation()}>
            {onEdit && <button onClick={onEdit} className="text-xs text-[var(--color-muted)] hover:text-[var(--color-primary)]">编辑</button>}
            {onDelete && <button onClick={onDelete} className="text-xs text-[var(--color-muted)] hover:text-red-500">删除</button>}
          </div>
        )}
      </div>
      {view.description && <p className="text-xs text-[var(--color-muted)] mt-1">{view.description}</p>}
      <div className="flex flex-wrap gap-1 mt-2">
        {filterMediums?.map((m) => (
          <span key={m} className="text-xs bg-[var(--color-border)] px-1.5 py-0.5 rounded">{m}</span>
        ))}
        {filterTags?.slice(0, 3).map((t) => (
          <span key={t} className="text-xs bg-[var(--color-border)]/60 px-1.5 py-0.5 rounded">{t}</span>
        ))}
      </div>
    </div>
  );
}
