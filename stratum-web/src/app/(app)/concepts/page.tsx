"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

interface Concept {
  id: string;
  name: string;
  type?: string;
}

export default function ConceptsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["concepts"],
    queryFn: () => apiClient.get<Concept[]>("/api/v1/concepts"),
  });

  const concepts = data ?? [];

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">概念</h1>
      {isLoading && <p className="text-sm text-[var(--color-muted)]">加载中...</p>}
      {!isLoading && concepts.length === 0 && (
        <p className="text-sm text-[var(--color-muted)]">暂无概念。</p>
      )}
      <div className="space-y-2">
        {concepts.map((c) => (
          <Link
            key={c.id}
            href={`/concepts/${c.id}`}
            className="flex items-center justify-between p-3 border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/10 transition"
          >
            <span className="font-medium">{c.name}</span>
            {c.type && (
              <span className="text-xs text-[var(--color-muted)]">{c.type}</span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
