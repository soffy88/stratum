"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

interface ContentItem {
  id: string;
  title: string;
  type: string;
  author?: string;
  published_at?: string;
  tags?: string[];
  access_tier?: string;
}

interface FeedResponse {
  items: ContentItem[];
  page: number;
  has_more: boolean;
}

export default function DiscoverPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["content-feed"],
    queryFn: () => apiClient.get<FeedResponse>("/api/v1/content/feed"),
  });

  const items = data?.items ?? [];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">发现</h1>

      {isLoading && (
        <p className="text-[var(--color-muted)]">加载中...</p>
      )}

      {error && (
        <p className="text-red-500 text-sm">
          加载失败，请刷新重试
        </p>
      )}

      {!isLoading && !error && items.length === 0 && (
        <p className="text-[var(--color-muted)]">暂无内容，稍后再来。</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {items.map((item) => (
          <Link
            key={item.id}
            href={`/content/${item.id}`}
            className="p-4 border border-[var(--color-border)] rounded hover:shadow-md transition"
          >
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-semibold text-lg leading-tight">
                {item.title}
              </h2>
              <span className="text-xs text-[var(--color-muted)] shrink-0 mt-1">
                {item.type}
              </span>
            </div>
            <p className="text-sm text-[var(--color-muted)] mt-1">
              {item.author} · {item.published_at?.slice(0, 10)}
            </p>
            <div className="flex gap-1 mt-2 flex-wrap">
              {(item.tags ?? []).map((t) => (
                <span
                  key={t}
                  className="text-xs bg-[var(--color-border)] px-2 py-0.5 rounded"
                >
                  {t}
                </span>
              ))}
            </div>
            {item.access_tier && item.access_tier !== "free" && (
              <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded mt-1 inline-block">
                {item.access_tier.toUpperCase()}
              </span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
