"use client";

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

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      <div>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold">{note.title ?? "无标题笔记"}</h1>
          <ShareNoteButton noteId={id} />
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
