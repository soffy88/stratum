"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";

type NoteItem = { id: string; title: string; updated_at: string };

export default function NotesPage() {
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient.get<NoteItem[]>("/api/v1/notes")
      .then((d) => { setNotes(d ?? []); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, []);

  if (loading) return <p className="p-6 text-[var(--color-muted)] text-sm">加载中...</p>;
  if (error) return <p className="p-6 text-red-500 text-sm">加载失败</p>;

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">笔记</h1>

      {notes.length === 0 ? (
        <p className="text-sm text-[var(--color-muted)]">
          还没有笔记。在文档阅读页可以添加笔记。
        </p>
      ) : (
        <div className="space-y-2">
          {notes.map((note) => (
            <Link
              key={note.id}
              href={`/notes/${note.id}`}
              className="block p-3 border border-[var(--color-border)] rounded bg-[var(--color-surface)] hover:bg-[var(--color-border)]/30 transition"
            >
              <p className="text-sm font-medium truncate">{note.title || "(无标题)"}</p>
              <p className="text-xs text-[var(--color-muted)] mt-0.5">
                {note.updated_at?.slice(0, 19).replace("T", " ") ?? "—"}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
