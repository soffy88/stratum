"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getCornell, type CornellNote } from "@/lib/adapters/cornell";
import { CornellNoteView } from "@/components/notes/CornellNoteView";

export default function CornellDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [note, setNote] = useState<CornellNote | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getCornell(id)
      .then((n) => {
        setNote(n);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, [id]);

  if (loading) return <p className="p-6 text-sm text-[var(--color-muted)]">加载康奈尔笔记…</p>;
  if (error || !note) {
    return (
      <div className="p-6">
        <p className="text-sm text-red-500 mb-3">笔记未找到</p>
        <Link href="/notes" className="text-sm text-[var(--color-primary)]">
          ← 返回笔记列表
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-2 pb-10">
      <div className="mb-3 flex items-center gap-3">
        <Link href="/notes" className="text-sm text-[var(--color-muted)] hover:text-[var(--color-primary)]">
          ← 笔记
        </Link>
        <span className="text-xs text-[var(--color-muted)]">/</span>
        <span className="text-sm font-medium truncate">{note.title}</span>
      </div>
      <CornellNoteView note={note} />
    </div>
  );
}
