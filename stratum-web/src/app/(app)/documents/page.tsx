"use client";

import { ODocumentTree } from "@helios/blocks";
import { useRouter } from "next/navigation";
import { useDocumentTree } from "@/lib/adapters/documents";
import type { Substrate } from "@helios/blocks";

export default function DocumentsPage() {
  const router = useRouter();
  const { substrates, isLoading } = useDocumentTree();

  const handleSelect = (substrate: Substrate) => {
    router.push(`/documents/${substrate.id}`);
  };

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">文档</h1>
      <ODocumentTree
        substrates={substrates}
        onSelect={handleSelect}
        emptyText="暂无文档，请通过 CLI 导入文件"
      />
    </div>
  );
}
