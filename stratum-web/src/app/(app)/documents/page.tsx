"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import type { SubstratesResponse, SubstrateItem } from "@/lib/types";

export default function DocumentsPage() {
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ["substrates"],
    queryFn: () => apiClient.get<SubstratesResponse>("/api/substrates"),
  });

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">文档</h1>
      <div className="space-y-2">
        {data?.items.map((sub: SubstrateItem) => (
          <button
            key={sub.id}
            onClick={() => router.push(`/documents/${sub.id}`)}
            className="w-full text-left p-3 border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/30"
          >
            <div className="font-medium">{sub.title || "无标题"}</div>
            <div className="text-xs text-[var(--color-muted)] mt-1">
              {sub.mime && <span>{sub.mime}</span>}
              {sub.language && <span className="ml-2">{sub.language}</span>}
              {sub.page_count && <span className="ml-2">{sub.page_count} 页</span>}
            </div>
          </button>
        ))}
        {data?.items.length === 0 && <p className="text-[var(--color-muted)]">暂无文档</p>}
      </div>
    </div>
  );
}
