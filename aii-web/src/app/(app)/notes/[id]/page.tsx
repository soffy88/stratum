"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ODocumentReader, OBacklinkPanel } from "@helios/blocks";
import type { BacklinkItem, Substrate, Derivative } from "@helios/blocks";
import { useNote, useBacklinks } from "@/lib/adapters/notes";
import { ShareNoteButton } from "@/components/shared/ShareNoteButton";

export default function NotePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const { note, isLoading: loadingNote } = useNote(id);
  const { backlinks, isLoading: loadingLinks } = useBacklinks(id);

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
    router.refresh();
  }

  if (loadingNote) return <p className="text-[var(--color-muted)]">加载中...</p>;
  if (!note) return <p className="text-red-600">笔记未找到</p>;

  // Adapt helios Note → minimal Substrate + Derivative for ODocumentReader
  const substrate: Substrate = {
    id: note.id,
    ulid: note.id,
    title: note.title,
    mime: "text/markdown",
    source_path: null,
    file_hash: null,
    byte_size: null,
    page_count: null,
    parser: null,
    language: "zh",
    has_cjk: true,
    is_scanned: false,
    is_pinned: false,
    pinned_at: null,
    created_at: note.created_at,
    updated_at: note.updated_at,
    meta_json: { medium: "markdown_note", source_type: "inbox_local", source: {} } as Substrate["meta_json"],
  };

  const derivatives: Derivative[] = note.content
    ? [
        {
          id: `${note.id}#0`,
          substrate_id: note.id,
          kind: "translation_zh-zh",
          seq: 0,
          content: note.content,
          embedding_id: null,
          embedding_dim: null,
          meta_json: {},
          created_at: note.created_at,
        },
      ]
    : [];

  const handleBacklinkSelect = (item: BacklinkItem) => {
    router.push(`/notes/${item.note.id}`);
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
        <ODocumentReader substrate={substrate} derivatives={derivatives} />
      </div>
      {!loadingLinks && (
        <OBacklinkPanel
          backlinks={backlinks}
          targetTitle={note.title ?? undefined}
          onSelect={handleBacklinkSelect}
          emptyText="暂无反链"
        />
      )}
    </div>
  );
}
