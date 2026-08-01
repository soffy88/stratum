"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { updateNote, deleteNote } from "@/lib/adapters/notes";
import { listCornell, type CornellNote } from "@/lib/adapters/cornell";

type NoteItem = { id: string; title: string; content?: string; updated_at: string };

type Tab = "all" | "human" | "machine";

export default function NotesPage() {
  const [tab, setTab] = useState<Tab>("all");
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [cornell, setCornell] = useState<CornellNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(false);
    Promise.all([
      apiClient.get<NoteItem[]>("/api/v1/notes").catch(() => [] as NoteItem[]),
      listCornell({ limit: 100 }).catch(() => [] as CornellNote[]),
    ])
      .then(([human, machine]) => {
        setNotes(human ?? []);
        setCornell(machine ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (id: string) => {
    const ok = await updateNote(id, editContent);
    if (ok) {
      setEditingId(null);
      load();
    }
  };

  const handleDelete = async (id: string) => {
    const ok = await deleteNote(id);
    if (ok) {
      setConfirmDelete(null);
      setNotes((prev) => prev.filter((n) => n.id !== id));
    }
  };

  const startEdit = (note: NoteItem) => {
    setEditingId(note.id);
    setEditContent(note.content ?? note.title ?? "");
  };

  if (loading) return <p className="p-6 text-[var(--color-muted)] text-sm">加载中...</p>;
  if (error) return <p className="p-6 text-red-500 text-sm">加载失败</p>;

  const showHuman = tab === "all" || tab === "human";
  const showMachine = tab === "all" || tab === "machine";
  const empty =
    (!showHuman || notes.length === 0) && (!showMachine || cornell.length === 0);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-end justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-semibold">笔记</h1>
          <p className="text-xs text-[var(--color-muted)] mt-1">
            人类主动笔记与机器康奈尔笔记（B仓去重 KU）共存
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 p-1 rounded-xl bg-[var(--color-muted)]/15 w-fit">
        {(
          [
            ["all", "全部"],
            ["human", "人类笔记"],
            ["machine", "机器康奈尔"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => setTab(k)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              tab === k
                ? "bg-[var(--color-card)] shadow-sm font-medium"
                : "text-[var(--color-muted)] hover:text-[var(--color-foreground)]"
            }`}
          >
            {label}
            <span className="ml-1 opacity-60">
              {k === "human"
                ? notes.length
                : k === "machine"
                  ? cornell.length
                  : notes.length + cornell.length}
            </span>
          </button>
        ))}
      </div>

      {empty ? (
        <p className="text-sm text-[var(--color-muted)]">
          {tab === "machine"
            ? "还没有机器康奈尔笔记。运行 generate_cornell_notes.py 或 POST /api/v1/cornell/generate。"
            : "还没有笔记。在文档阅读页可添加人类笔记；机器笔记由 B仓核心 KU 自动汇编。"}
        </p>
      ) : (
        <div className="space-y-4">
          {/* 机器康奈尔 */}
          {showMachine && cornell.length > 0 && (
            <section>
              {tab === "all" && (
                <h2 className="text-xs font-semibold text-[var(--color-muted)] mb-2 uppercase tracking-wide">
                  机器康奈尔 · 来自 B仓
                </h2>
              )}
              <div className="space-y-2">
                {cornell.map((n) => (
                  <Link
                    key={n.id}
                    href={`/notes/cornell/${n.id}`}
                    className="block p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[var(--color-primary)]/40 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium">{n.title}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
                            康奈尔
                          </span>
                          {n.subject && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200">
                              {n.subject}
                            </span>
                          )}
                        </div>
                        {n.content_preview && (
                          <p className="text-xs text-[var(--color-muted)] mt-1 line-clamp-2">
                            {n.content_preview}
                          </p>
                        )}
                        <p className="text-[10px] text-[var(--color-muted)] mt-1">
                          {(n.cue_count ?? n.content?.cues?.length ?? 0)} 问 ·{" "}
                          {(n.module_count ?? n.content?.modules?.length ?? 0)} 模块 ·{" "}
                          {new Date(n.updated_at).toLocaleDateString("zh-CN")}
                        </p>
                      </div>
                      <span className="text-xs text-[var(--color-primary)] shrink-0">学习 →</span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* 人类笔记 */}
          {showHuman && notes.length > 0 && (
            <section>
              {tab === "all" && (
                <h2 className="text-xs font-semibold text-[var(--color-muted)] mb-2 uppercase tracking-wide">
                  人类笔记
                </h2>
              )}
              <div className="space-y-2">
                {notes.map((note) => (
                  <div
                    key={note.id}
                    className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]"
                  >
                    {editingId === note.id ? (
                      <div className="space-y-2">
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          rows={4}
                          className="w-full p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-foreground)] text-sm"
                          autoFocus
                        />
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => setEditingId(null)}
                            className="px-3 py-1.5 text-sm rounded-lg border border-[var(--color-border)] text-[var(--color-muted)]"
                          >
                            取消
                          </button>
                          <button
                            onClick={() => handleSave(note.id)}
                            className="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-primary)] text-white"
                          >
                            保存
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <Link
                            href={`/notes/${note.id}`}
                            className="text-sm font-medium hover:text-[var(--color-primary)] transition-colors block"
                          >
                            {note.title || "无标题笔记"}
                          </Link>
                          {note.content && note.content !== note.title && (
                            <p className="text-xs text-[var(--color-muted)] mt-1 line-clamp-2">
                              {note.content}
                            </p>
                          )}
                          <p className="text-xs text-[var(--color-muted)] mt-1">
                            {new Date(note.updated_at).toLocaleDateString("zh-CN")}
                          </p>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <button
                            onClick={() => startEdit(note)}
                            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-muted)]"
                          >
                            编辑
                          </button>
                          {confirmDelete === note.id ? (
                            <div className="flex gap-1">
                              <button
                                onClick={() => handleDelete(note.id)}
                                className="px-2 py-1 text-xs rounded bg-red-500 text-white"
                              >
                                确认
                              </button>
                              <button
                                onClick={() => setConfirmDelete(null)}
                                className="px-2 py-1 text-xs rounded border text-[var(--color-muted)]"
                              >
                                取消
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setConfirmDelete(note.id)}
                              className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-red-500"
                            >
                              删除
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
