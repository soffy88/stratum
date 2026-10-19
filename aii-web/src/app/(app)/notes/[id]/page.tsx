"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { OBacklinkPanel } from "@helios/blocks";
import type { BacklinkItem } from "@helios/blocks";
import { useNote, useBacklinks, useOutgoingLinks } from "@/lib/adapters/notes";
import { ShareNoteButton } from "@/components/shared/ShareNoteButton";
import { WikilinkNoteBody } from "@/components/notes/WikilinkNoteBody";
import { OutgoingLinksPanel } from "@/components/notes/OutgoingLinksPanel";
import { NoteHistoryPanel } from "@/components/notes/NoteHistoryPanel";

export default function NotePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id;
  const { note, isLoading: loadingNote } = useNote(id);
  const { backlinks, isLoading: loadingLinks } = useBacklinks(id);
  // P0-4：解析正文 [[...]] 出链（id 优先，其次标题）
  const { links: outgoingLinks } = useOutgoingLinks(note?.content ?? "");

  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (note) {
      setEditTitle(note.title ?? "");
      setEditContent(note.content ?? "");
    }
  }, [note]);

  async function handleSave() {
    setSaving(true);
    await fetch(`/api/notes/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: editTitle, content: editContent }),
      credentials: "include",
    });
    setSaving(false);
    setEditing(false);
    await queryClient.invalidateQueries({ queryKey: ["note", id] });
    router.refresh();
  }

  if (loadingNote) return <p className="text-[var(--color-muted)]">加载中...</p>;
  if (!note) return <p className="text-red-600">笔记未找到</p>;

  const handleBacklinkSelect = (item: BacklinkItem) => {
    router.push(`/notes/${item.note.id}`);
  };

  const handleOutgoingSelect = (targetId: string) => {
    router.push(`/notes/${targetId}`);
  };

  if (editing) {
    return (
      <div className="max-w-3xl mx-auto p-4">
        <input
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          className="w-full text-xl font-semibold border border-[var(--color-border)] rounded px-3 py-2 mb-3"
        />
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          className="w-full h-96 font-mono text-sm border border-[var(--color-border)] rounded px-3 py-2"
        />
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 bg-[var(--color-accent)] text-white rounded text-sm"
          >
            {saving ? "保存中…" : "保存"}
          </button>
          <button
            onClick={() => setEditing(false)}
            className="px-4 py-1.5 border border-[var(--color-border)] rounded text-sm"
          >
            取消
          </button>
        </div>
      </div>
    );
  }

  const resolvedOutgoing = outgoingLinks.filter((l) => l.id !== null);

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      <div>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold">{note.title ?? "无标题笔记"}</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditing(true)}
              className="px-3 py-1 text-sm border border-[var(--color-border)] rounded hover:bg-[var(--color-border)] transition"
            >
              编辑
            </button>
            <ShareNoteButton noteId={id} />
          </div>
        </div>
        {/* P0-4：正文 [[...]] 渲染为可点击的笔记链接 */}
        <WikilinkNoteBody content={note.content ?? ""} links={outgoingLinks} />
      </div>
      <div className="flex flex-col gap-6">
        {!loadingLinks && (
          <OBacklinkPanel
            backlinks={backlinks}
            targetTitle={note.title ?? undefined}
            onSelect={handleBacklinkSelect}
            emptyText="暂无反链"
          />
        )}
        {/* P0-4：出链面板（这篇笔记链向谁） */}
        <OutgoingLinksPanel
          links={resolvedOutgoing}
          onSelect={handleOutgoingSelect}
          emptyText="暂无出链"
        />
        {/* P0-1：版本历史 */}
        <NoteHistoryPanel noteId={id} />
      </div>
    </div>
  );
}
