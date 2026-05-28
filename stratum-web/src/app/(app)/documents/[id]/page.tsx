"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { SubstrateItem, DerivativeItem } from "@/lib/types";

export default function DocumentReaderPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const { data: substrate, isLoading: loadingSub } = useQuery({
    queryKey: ["substrate", id],
    queryFn: () => apiClient.get<SubstrateItem>(`/api/substrates/${id}`),
    enabled: !!id,
  });

  const { data: derivatives } = useQuery({
    queryKey: ["derivatives", id],
    queryFn: () => apiClient.get<{ items: DerivativeItem[] }>(`/api/substrates/${id}/derivatives`),
    enabled: !!id,
  });

  if (loadingSub) return <p className="text-[var(--color-muted)]">加载中...</p>;
  if (!substrate) return <p className="text-red-600">文档未找到</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-2">{substrate.title}</h1>
      <div className="text-sm text-[var(--color-muted)] mb-6">
        {substrate.mime && <span>{substrate.mime}</span>}
        {substrate.language && <span className="ml-2">{substrate.language}</span>}
        {substrate.page_count && <span className="ml-2">{substrate.page_count} 页</span>}
      </div>

      <h2 className="text-lg font-medium mb-3">内容片段</h2>
      <div className="space-y-3">
        {derivatives?.items.map((d: DerivativeItem) => (
          <div key={d.id} className="p-3 border border-[var(--color-border)] rounded">
            <div className="text-xs text-[var(--color-muted)] mb-1">{d.kind} #{d.seq}</div>
            <p className="text-sm whitespace-pre-wrap">{d.content}</p>
          </div>
        ))}
        {derivatives?.items.length === 0 && <p className="text-[var(--color-muted)]">暂无片段</p>}
      </div>
    </div>
  );
}
