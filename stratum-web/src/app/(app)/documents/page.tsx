"use client";

import { useState } from "react";
import { ODocumentTree } from "@helios/blocks";
import { useRouter } from "next/navigation";
import { useDocumentTree } from "@/lib/adapters/documents";
import type { Substrate } from "@helios/blocks";
import { UploadButton } from "@/components/UploadButton";
import { UrlIngestDialog } from "@/components/UrlIngestDialog";
import { FeedSubscribeDialog } from "@/components/FeedSubscribeDialog";

export default function DocumentsPage() {
  const router = useRouter();
  const { substrates, isLoading, refetch } = useDocumentTree();
  const [showUrlDialog, setShowUrlDialog] = useState(false);
  const [showFeedDialog, setShowFeedDialog] = useState(false);

  const handleSelect = (substrate: Substrate) => {
    router.push(`/documents/${substrate.id}`);
  };

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      {showUrlDialog && (
        <UrlIngestDialog
          onClose={() => setShowUrlDialog(false)}
          onSuccess={() => void refetch?.()}
        />
      )}
      {showFeedDialog && (
        <FeedSubscribeDialog
          onClose={() => setShowFeedDialog(false)}
          onSuccess={() => void refetch?.()}
        />
      )}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">文档</h1>
      </div>
      <div className="flex items-center gap-3">
        <UploadButton onSuccess={() => void refetch?.()} />
        <button
          onClick={() => setShowUrlDialog(true)}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)] transition"
        >
          输入 URL
        </button>
        <button
          onClick={() => setShowFeedDialog(true)}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)] transition"
        >
          订阅 RSS
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
