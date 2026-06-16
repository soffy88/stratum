'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { ODocumentTree } from '@helios/blocks';
import { useDocumentTree } from '@/lib/adapters/documents';
import type { Substrate } from '@helios/blocks';
import { UploadDialog } from '@/components/UploadDialog';
import { UrlIngestDialog } from '@/components/UrlIngestDialog';
import { FeedSubscribeDialog } from '@/components/FeedSubscribeDialog';
import { FolderIngestDialog } from '@/components/FolderIngestDialog';
import { listViews, type View } from '@/lib/views';

export default function DocumentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const viewId = searchParams.get('view');

  const { substrates, isLoading, refetch } = useDocumentTree();

  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [showUrlDialog, setShowUrlDialog] = useState(false);
  const [showFeedDialog, setShowFeedDialog] = useState(false);
  const [showFolderDialog, setShowFolderDialog] = useState(false);
  const [currentView, setCurrentView] = useState<View | null>(null);

  useEffect(() => {
    if (!viewId) { setCurrentView(null); return; }
    listViews()
      .then(vs => setCurrentView(vs.find(v => v.id === viewId) ?? null))
      .catch(() => {});
  }, [viewId]);

  const handleSelect = (substrate: Substrate) => {
    router.push(`/documents/${substrate.id}`);
  };

  if (isLoading) return <p className="text-[var(--color-muted)]">加载中...</p>;

  return (
    <div className="max-w-4xl mx-auto p-4">
      {showUploadDialog && (
        <UploadDialog
          onClose={() => setShowUploadDialog(false)}
          onSuccess={() => void refetch?.()}
        />
      )}
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
      {showFolderDialog && (
        <FolderIngestDialog
          onClose={() => setShowFolderDialog(false)}
          onSuccess={() => void refetch?.()}
        />
      )}

      {/* View Banner */}
      {viewId && currentView && (
        <div className="flex items-center gap-2 px-4 py-2 bg-muted rounded-lg mb-4">
          <span className="font-medium">{currentView.icon} {currentView.name}</span>
          <span className="text-muted-foreground text-sm">· {substrates.length} 篇</span>
          <button
            onClick={() => router.push('/documents')}
            className="ml-auto text-sm text-muted-foreground hover:text-foreground"
          >
            清除视图 ×
          </button>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">文档</h1>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => setShowUploadDialog(true)}
          className="px-3 py-1.5 bg-[var(--color-primary)] text-white rounded text-sm hover:opacity-90 transition"
        >
          上传文件
        </button>
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
        <button
          onClick={() => setShowFolderDialog(true)}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)] transition"
        >
          文件夹
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
