"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

interface InboxItem {
  id: string;
  title: string;
  source?: string;
  created_at: string;
  updated_at?: string;
  parse_quality?: string;
  meta_json?: Record<string, unknown>;
}

export default function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ items: InboxItem[]; count: number }>(
        "/api/v1/inbox?limit=100"
      );
      setItems(data?.items ?? []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const handleProcess = async (id: string) => {
    setProcessingId(id);
    try {
      await apiClient.post(`/api/v1/inbox/${id}/process`);
      toast.success("处理已触发");
    } catch {
      toast.error("处理失败");
    } finally {
      setProcessingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/api/v1/inbox/${id}`);
      setItems((prev) => prev.filter((item) => item.id !== id));
      toast.success("已删除");
    } catch {
      toast.error("删除失败");
    }
    setConfirmDelete(null);
  };

  const getMedium = (item: InboxItem): string => {
    return (item.meta_json as Record<string, unknown>)?.medium as string ?? "unknown";
  };

  const MEDIUM_ICONS: Record<string, string> = {
    pdf: "📄", epub: "📗", book: "📗", text: "📝", webpage: "🌐",
    note: "📝", video: "🎬", article: "📰", paper: "📑",
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">收件箱</h1>
        <button
          onClick={() => void loadItems()}
          className="px-3 py-1.5 text-sm rounded-lg border border-[var(--color-border)] text-[var(--color-muted)] hover:bg-[var(--color-muted)]"
        >
          刷新
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--color-muted)]">加载中...</p>
      ) : items.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-4xl mb-3">📥</p>
          <p className="text-sm text-[var(--color-muted)]">
            收件箱为空。通过右上角的上传按钮或 URL 提交内容。
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.id}
              className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] flex items-start justify-between gap-3"
            >
              <div className="flex-1 min-w-0">
                <Link
                  href={`/documents/${item.id}`}
                  className="text-sm font-medium hover:text-[var(--color-primary)] transition-colors block"
                >
                  <span className="mr-1.5">{MEDIUM_ICONS[getMedium(item)] ?? "📄"}</span>
                  {item.title || "未命名"}
                </Link>
                {item.source && (
                  <p className="text-xs text-[var(--color-muted)] mt-1 truncate">
                    {item.source}
                  </p>
                )}
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-[var(--color-muted)]">
                    {new Date(item.created_at).toLocaleString("zh-CN")}
                  </span>
                  {item.parse_quality === "scanned" && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-muted)] text-[var(--color-muted-foreground)]">
                      扫描版
                    </span>
                  )}
                  {(item.parse_quality === "empty" || item.parse_quality === "garbled") && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">
                      解析失败
                    </span>
                  )}
                </div>
              </div>

              <div className="flex gap-1 shrink-0">
                <button
                  onClick={() => handleProcess(item.id)}
                  disabled={processingId === item.id}
                  className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-muted)] hover:bg-[var(--color-muted)] disabled:opacity-50"
                >
                  {processingId === item.id ? "处理中..." : "处理"}
                </button>
                {confirmDelete === item.id ? (
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="px-2 py-1 text-xs rounded bg-red-500 text-white"
                    >
                      确认
                    </button>
                    <button
                      onClick={() => setConfirmDelete(null)}
                      className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-muted)]"
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDelete(item.id)}
                    className="px-2 py-1 text-xs rounded border border-red-500/30 text-red-400 hover:bg-red-500/10"
                  >
                    删除
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
