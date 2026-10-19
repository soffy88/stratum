"use client";

import { useState } from "react";
import { useTrash, restoreNoteFromTrash } from "@/lib/adapters/notes";

interface NoteTrashViewProps {
  onBack: () => void;
  /** 恢复成功后回调（用于刷新列表页） */
  onRestored?: () => void;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("zh-CN", { hour12: false });
}

/** 回收站：GET /api/v1/notes/trash 列表展示，每条可恢复。 */
export function NoteTrashView({ onBack, onRestored }: NoteTrashViewProps) {
  const { items, isLoading, refetch } = useTrash();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRestore = async (id: string) => {
    setBusyId(id);
    setError(null);
    try {
      const ok = await restoreNoteFromTrash(id);
      if (!ok) {
        setError("恢复失败，请稍后重试");
        return;
      }
      await refetch();
      onRestored?.();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-5">
        <button
          type="button"
          onClick={onBack}
          className="shrink-0 px-3 py-1.5 text-xs rounded-lg border border-[var(--color-border)] text-[var(--color-muted)] hover:text-[var(--color-foreground)] transition-colors"
        >
          ← 返回
        </button>
        <div>
          <h1 className="text-xl font-semibold">回收站</h1>
          <p className="text-xs text-[var(--color-muted)] mt-1">
            删除的笔记会先进入回收站，可随时恢复
          </p>
        </div>
      </div>

      {error && <p className="text-xs text-red-500 mb-3">{error}</p>}

      {isLoading ? (
        <p className="text-sm text-[var(--color-muted)]">加载中…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--color-muted)]">回收站是空的。</p>
      ) : (
        <div className="space-y-2">
          {items.map((note) => (
            <div
              key={note.id}
              className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] flex items-start justify-between gap-3"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{note.title || "无标题笔记"}</p>
                <p className="text-xs text-[var(--color-muted)] mt-1">
                  删除于 {formatDate(note.deleted_at ?? note.updated_at)}
                </p>
              </div>
              <button
                type="button"
                disabled={busyId === note.id}
                onClick={() => handleRestore(note.id)}
                className="shrink-0 px-3 py-1.5 text-xs rounded-lg bg-[var(--color-primary)] text-white disabled:opacity-50 transition-opacity"
              >
                {busyId === note.id ? "恢复中…" : "恢复"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
