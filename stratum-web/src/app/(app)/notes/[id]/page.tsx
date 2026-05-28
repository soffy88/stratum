"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { BacklinksResponse, BacklinkItem } from "@/lib/types";

export default function NoteViewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const { data, isLoading } = useQuery({
    queryKey: ["backlinks", id],
    queryFn: () => apiClient.get<BacklinksResponse>(`/api/notes/${id}/backlinks`),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">笔记反链</h1>

      <div className="space-y-2">
        {data?.items.map((bl: BacklinkItem) => (
          <button
            key={bl.id}
            onClick={() => router.push(`/notes/${bl.id}`)}
            className="w-full text-left p-3 border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/30"
          >
            <div className="font-medium">{bl.title}</div>
            {bl.snippet && <p className="text-sm text-[var(--color-muted)] mt-1">{bl.snippet}</p>}
          </button>
        ))}
        {data?.items.length === 0 && <p className="text-[var(--color-muted)]">暂无反链</p>}
      </div>
    </div>
  );
}
