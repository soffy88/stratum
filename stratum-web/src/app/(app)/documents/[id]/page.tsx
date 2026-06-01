"use client";

import { useParams } from "next/navigation";
import { ODocumentReader, OAnnotationLayer, OCitationCard } from "@helios/blocks";
import type { Citation } from "@helios/blocks";
import { useDocument } from "@/lib/adapters/documents";
import { TranslationToggle } from "@/components/TranslationToggle";

/**
 * TECHNICAL_DEBT: OAnnotationLayer rendered in display-only mode (fragments=[]).
 * No /api/annotations endpoint exists in Phase 14. See Wave 10A spec §3.3.5.
 * When annotation endpoint is added (Phase 15+), populate fragments from API.
 */

export default function DocumentReaderPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { substrate, derivatives, isLoading } = useDocument(id);

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;
  if (!substrate) return <p className="text-red-600">文档未找到</p>;

  // Self-citation card: lets users copy a citation reference for this document
  const selfCitation: Citation = {
    substrate_id: substrate.id,
    title: substrate.title ?? undefined,
    fragment_id: null,
    anchor: null,
    deep_link: null,
  };

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold truncate">{substrate.title ?? "文档详情"}</h1>
        <TranslationToggle substrateId={id} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
        <ODocumentReader
          substrate={substrate}
          derivatives={derivatives}
        />
        {/* Annotation sidebar — display-only until /api/annotations is implemented */}
        <OAnnotationLayer fragments={[]} emptyText="暂无标注" />
      </div>
      {/* Source citation — allows copying a structured reference for this document */}
      <div className="pt-2 border-t border-[var(--color-border)]">
        <p className="text-xs text-[var(--color-muted)] mb-2">引用此文档</p>
        <OCitationCard citation={selfCitation} compact />
      </div>
    </div>
  );
}
