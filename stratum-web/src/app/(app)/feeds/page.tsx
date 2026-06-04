"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api-client";
import { FeedSubscribeDialog } from "@/components/FeedSubscribeDialog";

interface FeedSub {
  id: string;
  feed_url: string;
  feed_title: string | null;
  frequency_hours: number;
  last_check_at: string | null;
  last_entries_count: number;
  status: string;
  error_message: string | null;
  created_at: string;
}

function statusBadge(status: string) {
  if (status === "active")
    return <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">运行中</span>;
  if (status === "paused")
    return <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">已暂停</span>;
  if (status === "error")
    return <span className="text-xs px-1.5 py-0.5 bg-red-100 text-red-700 rounded">错误</span>;
  return null;
}

export default function FeedsPage() {
  const [showDialog, setShowDialog] = useState(false);
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["feeds"],
    queryFn: () => apiClient.get<{ items: FeedSub[] }>("/api/v1/feeds"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiClient.delete<{ status: string }>(`/api/v1/feeds/${id}`),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["feeds"] }); },
    onError: () => toast.error("删除失败"),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiClient.put(`/api/v1/feeds/${id}`, { status }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["feeds"] }); },
  });

  const checkMut = useMutation({
    mutationFn: (id: string) => apiClient.post<{ ingested: number }>(`/api/v1/feeds/${id}/check`),
    onSuccess: (data) => toast.success(`立即抓取完成，入库 ${data.ingested} 篇`),
    onError: () => toast.error("抓取失败"),
  });

  const feeds = data?.items ?? [];

  return (
    <div className="max-w-3xl mx-auto">
      {showDialog && (
        <FeedSubscribeDialog
          onClose={() => setShowDialog(false)}
          onSuccess={() => {
            void qc.invalidateQueries({ queryKey: ["feeds"] });
            setShowDialog(false);
          }}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">订阅源</h1>
        <button
          onClick={() => setShowDialog(true)}
          className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm"
        >
          + 添加订阅
        </button>
      </div>

      {isLoading && <p className="text-sm text-[var(--color-muted)]">加载中...</p>}

      {!isLoading && feeds.length === 0 && (
        <div className="text-center py-16 text-[var(--color-muted)]">
          <p className="text-sm">还没有订阅源</p>
          <button
            onClick={() => setShowDialog(true)}
            className="mt-3 text-sm text-[var(--color-primary)] hover:underline"
          >
            添加第一个 RSS 订阅
          </button>
        </div>
      )}

      <ul className="space-y-3">
        {feeds.map((f) => (
          <li
            key={f.id}
            className="border border-[var(--color-border)] rounded-lg p-4"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm truncate">
                    {f.feed_title || f.feed_url}
                  </span>
                  {statusBadge(f.status)}
                </div>
                <p className="text-xs text-[var(--color-muted)] truncate mt-0.5">
                  {f.feed_url}
                </p>
                <div className="flex gap-3 mt-1 text-xs text-[var(--color-muted)]">
                  <span>每 {f.frequency_hours} 小时</span>
                  {f.last_check_at && (
                    <span>上次: {new Date(f.last_check_at).toLocaleString("zh-CN")}</span>
                  )}
                  {f.last_entries_count > 0 && (
                    <span>{f.last_entries_count} 条</span>
                  )}
                </div>
                {f.error_message && (
                  <p className="text-xs text-red-600 mt-1">{f.error_message}</p>
                )}
              </div>
              <div className="flex gap-1 shrink-0">
                <button
                  onClick={() => checkMut.mutate(f.id)}
                  disabled={checkMut.isPending}
                  className="px-2 py-1 text-xs border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)] disabled:opacity-50"
                >
                  立即拉取
                </button>
                <button
                  onClick={() =>
                    toggleMut.mutate({
                      id: f.id,
                      status: f.status === "paused" ? "active" : "paused",
                    })
                  }
                  disabled={toggleMut.isPending}
                  className="px-2 py-1 text-xs border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)] disabled:opacity-50"
                >
                  {f.status === "paused" ? "恢复" : "暂停"}
                </button>
                <button
                  onClick={() => deleteMut.mutate(f.id)}
                  disabled={deleteMut.isPending}
                  className="px-2 py-1 text-xs border border-red-200 text-red-500 rounded hover:bg-red-50 disabled:opacity-50"
                >
                  删除
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
