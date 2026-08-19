"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";

interface Notification {
  id: string;
  title: string;
  body: string;
  created_at: string;
}

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get<{ items: Notification[]; count: number }>("/api/v1/notifications?limit=100")
      .then((data) => setItems(data?.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">通知</h1>

      {loading ? (
        <p className="text-sm text-[var(--color-muted)]">加载中...</p>
      ) : items.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-4xl mb-3">🔔</p>
          <p className="text-sm text-[var(--color-muted)]">
            暂无通知。系统事件和处理结果会在这里显示。
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((n) => (
            <div
              key={n.id}
              className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{n.title}</p>
                  <p className="text-xs text-[var(--color-muted)] mt-1">{n.body}</p>
                </div>
                <span className="text-xs text-[var(--color-muted)] shrink-0 tabular-nums">
                  {new Date(n.created_at).toLocaleString("zh-CN")}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
