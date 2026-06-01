"use client";

import { ODocumentTree } from "@helios/blocks";
import { useRouter } from "next/navigation";
import { useDocumentTree } from "@/lib/adapters/documents";
import type { Substrate } from "@helios/blocks";
import { UploadButton } from "@/components/UploadButton";

export default function DocumentsPage() {
  const router = useRouter();
  const { substrates, isLoading } = useDocumentTree();

  const handleSelect = (substrate: Substrate) => {
    router.push(`/documents/${substrate.id}`);
  };

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">文档</h1>
      </div>
      <UploadButton />
      <div className="mt-6">
        <ODocumentTree
          substrates={substrates}
          onSelect={handleSelect}
          emptyText="暂无文档，点击上方上传文件"
        />
      </div>
    </div>
  );
}
