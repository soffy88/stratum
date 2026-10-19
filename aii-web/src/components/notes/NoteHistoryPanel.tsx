"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { OEventTimeline } from "@helios/blocks";
import type { TimelineEvent } from "@helios/blocks";
import { useRevisions, restoreRevision } from "@/lib/adapters/notes";
import type { NoteRevision } from "@/lib/types";

interface NoteHistoryPanelProps {
  noteId: string;
  /** 恢复成功、笔记已刷新后回调 */
  onRestored?: () => void;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("zh-CN", { hour12: false });
}

/** 单个版本的预览：标题 / 原因 / 作者 / 时间 + 正文快照（若有） */
function RevisionPreview({ revision }: { revision: NoteRevision }) {
  const body = revision.content_markdown ?? revision.content ?? "";
  const rows: [string, string][] = [
    ["标题", revision.title || "（无标题）"],
    ["原因", revision.cause || "编辑"],
    ["作者", revision.author ?? revision.author_user_id ?? "—"],
    ["时间", formatDateTime(revision.created_at)],
  ];
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        {rows.map(([k, v]) => (
          <span key={k} className="contents">
            <span className="text-[var(--color-muted)]">{k}</span>
            <span className="text-[var(--color-foreground)] break-words">{v}</span>
          </span>
        ))}
      </div>
      {body && (
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-relaxed rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] p-2 text-[var(--color-muted)]">
          {body.slice(0, 2000)}
        </pre>
      )}
    </div>
  );
}

/**
 * 版本历史面板：GET /api/v1/notes/{id}/revisions（version DESC），
 * 每版可展开预览，可一键恢复（恢复=写新版本，不覆写历史）。
 */
export function NoteHistoryPanel({ noteId, onRestored }: NoteHistoryPanelProps) {
  const { revisions, isLoading } = useRevisions(noteId);
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<number | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRestore = async (version: number) => {
    setBusy(true);
    setError(null);
    try {
      const ok = await restoreRevision(noteId, version);
      if (!ok) {
        setError("恢复失败，请稍后重试");
        return;
      }
      setConfirming(null);
      setExpanded(null);
      await queryClient.invalidateQueries({ queryKey: ["note-revisions", noteId] });
      await queryClient.invalidateQueries({ queryKey: ["note", noteId] });
      onRestored?.();
    } finally {
      setBusy(false);
    }
  };

  const events: TimelineEvent[] = revisions.map((r) => ({
    id: `v${r.version}`,
    title: `第 ${r.version} 版`,
    time: r.created_at,
    subtitle: [r.title, r.cause, r.author ?? r.author_user_id].filter(Boolean).join(" · ") || undefined,
    defaultExpanded: expanded === r.version,
    detail: (
      // 阻止冒泡：面板内的按钮点击不应触发时间线的展开/收起
      <div onClick={(e) => e.stopPropagation()}>
        <RevisionPreview revision={r} />
        <div className="mt-2 flex justify-end">
          {confirming === r.version ? (
            <div className="flex gap-2 items-center">
              <span className="text-xs text-[var(--color-muted)]">恢复到这一版？</span>
              <button
                type="button"
                disabled={busy}
                onClick={() => handleRestore(r.version)}
                className="px-2.5 py-1 text-xs rounded bg-[var(--color-primary)] text-white disabled:opacity-50"
              >
                {busy ? "恢复中…" : "确认恢复"}
              </button>
              <button
                type="button"
                onClick={() => setConfirming(null)}
                className="px-2.5 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-muted)]"
              >
                取消
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirming(r.version)}
              className="px-2.5 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-primary)] hover:bg-[var(--color-muted)]/15"
            >
              恢复到这一版
            </button>
          )}
        </div>
      </div>
    ),
  }));

  const toggle = (event: TimelineEvent) => {
    const v = Number(String(event.id).replace(/^v/, ""));
    if (!Number.isFinite(v)) return;
    setConfirming(null);
    setExpanded((prev) => (prev === v ? null : v));
  };

  return (
    <section className="flex flex-col gap-2 w-full" aria-label="版本历史">
      <header className="flex items-center gap-2">
        <svg
          aria-hidden="true"
          width="1em"
          height="1em"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
          <path d="M3 3v5h5" />
          <path d="M12 7v5l4 2" />
        </svg>
        <h3 className="text-sm font-bold text-[var(--color-foreground)] tracking-[-0.01em]">
          版本历史
        </h3>
        <span className="text-xs text-[var(--color-muted)] font-mono">({revisions.length})</span>
      </header>
      {isLoading ? (
        <p className="text-xs text-[var(--color-muted)]">加载中…</p>
      ) : (
        <OEventTimeline
          events={events}
          variant="ghost"
          groupByDate={false}
          emptyMessage="暂无历史版本"
          onEventClick={toggle}
        />
      )}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </section>
  );
}
