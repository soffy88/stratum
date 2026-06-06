"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { use } from "react";

interface ConceptNode {
  id: string;
  type: string;
  label?: string;
  title?: string;
}

interface ConceptDetail {
  id: string;
  name: string;
  type?: string;
  aliases?: string[];
  wikilink?: string;
  platform_view?: Record<string, unknown> | null;
  related_substrates?: { id: string; title: string }[];
}

interface ConceptGraph {
  nodes: ConceptNode[];
  edges: unknown[];
}

export default function ConceptDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: concept, isLoading } = useQuery({
    queryKey: ["concept", id],
    queryFn: () => apiClient.get<ConceptDetail>(`/api/v1/concepts/${id}`),
    enabled: !!id,
  });

  const { data: graph } = useQuery({
    queryKey: ["concept-graph", id],
    queryFn: () => apiClient.get<ConceptGraph>(`/api/v1/concepts/graph/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <p className="p-6 text-sm text-[var(--color-muted)]">加载中...</p>;
  if (!concept) return <p className="p-6 text-sm text-[var(--color-muted)]">概念未找到。</p>;

  const relatedConcepts = graph?.nodes.filter((n) => n.type === "concept" && n.id !== id);
  const relatedSubstrates = graph?.nodes.filter((n) => n.type === "substrate");

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <div className="flex items-start justify-between gap-2">
          <h1 className="text-xl font-semibold">{concept.name}</h1>
          <Link href={`/concepts/${id}/graph`}
            className="shrink-0 px-3 py-1.5 text-xs border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)]">
            查看图谱 →
          </Link>
        </div>
        {concept.type && (
          <span className="text-xs text-[var(--color-muted)] bg-[var(--color-border)] px-2 py-0.5 rounded mt-1 inline-block">
            {concept.type}
          </span>
        )}
        {(concept.aliases?.length ?? 0) > 0 && (
          <p className="text-sm text-[var(--color-muted)] mt-2">别名：{concept.aliases!.join(" · ")}</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {(concept.related_substrates?.length ?? 0) > 0 && (
          <section>
            <h2 className="font-medium text-sm mb-2">相关资料</h2>
            <div className="space-y-1">
              {concept.related_substrates!.map((s) => (
                <Link key={s.id} href={`/documents/${s.id}`}
                  className="block p-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)]">
                  {s.title}
                </Link>
              ))}
            </div>
          </section>
        )}
        {(relatedConcepts?.length ?? 0) > 0 && (
          <section>
            <h2 className="font-medium text-sm mb-2">相关概念</h2>
            <div className="space-y-1">
              {relatedConcepts!.map((n) => (
                <Link key={n.id} href={`/concepts/${n.id}`}
                  className="block p-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)]">
                  {n.label}
                </Link>
              ))}
            </div>
          </section>
        )}
        {(relatedSubstrates?.length ?? 0) > 0 && (
          <section>
            <h2 className="font-medium text-sm mb-2">引用此概念的文档</h2>
            <div className="space-y-1">
              {relatedSubstrates!.map((n) => (
                <div key={n.id} className="p-2 border border-[var(--color-border)] rounded text-sm">
                  {n.title}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
