"use client";

import { useState } from "react";
import { ODocumentTree } from "@helios/blocks";
import { useRouter } from "next/navigation";
import { useDocumentTree } from "@/lib/adapters/documents";
import type { Substrate } from "@helios/blocks";
import { UploadButton } from "@/components/UploadButton";
import { UrlIngestDialog } from "@/components/UrlIngestDialog";

export default function DocumentsPage() {
  const router = useRouter();
  const { substrates, isLoading } = useDocumentTree();
  const [showUrlDialog, setShowUrlDialog] = useState(false);

  const handleSelect = (substrate: Substrate) => {
    router.push(`/documents/${substrate.id}`);
  };

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      {showUrlDialog && <UrlIngestDialog onClose={() => setShowUrlDialog(false)} />}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">文档</h1>
      </div>
      <div className="flex items-center gap-3">
        <UploadButton />
        <button
          onClick={() => setShowUrlDialog(true)}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)] transition"
        >
          输入 URL
        </button>
      </div>
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
