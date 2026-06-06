"use client";

import { Suspense, useState } from "react";
import { ODocumentTree } from "@helios/blocks";
import { useRouter, useSearchParams } from "next/navigation";
import { useDocumentTree } from "@/lib/adapters/documents";
import { useQuery } from "@tanstack/react-query";
import type { Substrate } from "@helios/blocks";
import { UploadDialog } from "@/components/UploadDialog";
import { UrlIngestDialog } from "@/components/UrlIngestDialog";
import { FeedSubscribeDialog } from "@/components/FeedSubscribeDialog";
import { listViews, type View } from "@/lib/views";

function DocumentsInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const viewId = searchParams.get("view");

  const { substrates, isLoading, refetch } = useDocumentTree(viewId);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [showUrlDialog, setShowUrlDialog] = useState(false);
  const [showFeedDialog, setShowFeedDialog] = useState(false);

  // Load view info for the banner
  const { data: views } = useQuery({
    queryKey: ["views"],
    queryFn: listViews,
    enabled: !!viewId,
  });
  const activeView: View | undefined = views?.find((v) => v.id === viewId);

  const handleSelect = (substrate: Substrate) => router.push(`/documents/${substrate.id}`);

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto">
      {showUploadDialog && <UploadDialog onClose={() => setShowUploadDialog(false)} onSuccess={() => void refetch?.()} />}
      {showUrlDialog && <UrlIngestDialog onClose={() => setShowUrlDialog(false)} onSuccess={() => void refetch?.()} />}
      {showFeedDialog && <FeedSubscribeDialog onClose={() => setShowFeedDialog(false)} onSuccess={() => void refetch?.()} />}

      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">文档</h1>
      </div>

      {activeView && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-sm">
          {activeView.icon && <span>{activeView.icon}</span>}
          <span className="font-medium">{activeView.name}</span>
          <span className="text-[var(--color-muted)]">· {substrates.length} 个文档</span>
          <button onClick={() => router.push("/documents")}
            className="ml-auto text-xs text-[var(--color-muted)] hover:text-[var(--color-primary)]">
            清除视图 ×
          </button>
        </div>
      )}

      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => setShowUploadDialog(true)}
          className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm hover:opacity-90 transition">
          上传文件
        </button>
        <button onClick={() => setShowUrlDialog(true)}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)] transition">
          输入 URL
        </button>
        <button onClick={() => setShowFeedDialog(true)}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)] transition">
          订阅 RSS
        </button>
      </div>

      <ODocumentTree
        substrates={substrates}
        onSelect={handleSelect}
        emptyText={activeView ? `该视图下暂无文档 (${activeView.name})` : "暂无文档，点击上方上传文件"}
      />
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<p className="text-[var(--color-muted)]">加载中...</p>}>
      <DocumentsInner />
    </Suspense>
  );
}
