"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { listBookmarks, removeBookmark, type Bookmark } from "@/lib/adapters/bookmarks";

export default function BookmarksPage() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const items = await listBookmarks();
    setBookmarks(items);
    setLoading(false);
  };

  useEffect(() => { void load(); }, []);

  const handleRemove = async (id: string) => {
    const ok = await removeBookmark(id);
    if (ok) setBookmarks((prev) => prev.filter((b) => b.id !== id));
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">书签</h1>

      {loading ? (
        <p className="text-sm text-[var(--color-muted)]">加载中...</p>
      ) : bookmarks.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-4xl mb-3">🔖</p>
          <p className="text-sm text-[var(--color-muted)]">
            还没有书签。在文档详情页可以添加书签。
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {bookmarks.map((bm) => (
            <div
              key={bm.id}
              className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] flex items-center justify-between gap-3"
            >
              <div className="flex-1 min-w-0">
                <Link
                  href={`/documents/${bm.content_id}`}
                  className="text-sm font-medium hover:text-[var(--color-primary)] transition-colors"
                >
                  {bm.content_title || bm.content_id}
                </Link>
                <p className="text-xs text-[var(--color-muted)] mt-1">
                  {new Date(bm.created_at).toLocaleString("zh-CN")}
                </p>
              </div>
              <button
                onClick={() => handleRemove(bm.id)}
                className="px-2 py-1 text-xs rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 shrink-0"
              >
                移除
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
