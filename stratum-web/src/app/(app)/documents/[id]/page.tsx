'use client';

/**
 * /documents/[id] — 文档详情页
 * Tab:概览 / 原始文档(DocumentViewer 内嵌 PDF/EPUB)/ Markdown / 衍生品
 *
 * 注:这是详情页骨架 + original tab 接入 DocumentViewer。
 * 若 stratum-web 已有详情页,把 original tab 的 DocumentViewer 接入合并即可(★ 标记)。
 * DocumentViewer 动态导入(ssr:false)避免 PDF.js/epub.js 在服务端报错。
 */

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import type { Substrate } from '@/lib/documents';
import { CardSkeleton } from '@/components/LoadingSkeleton';

// ★ DocumentViewer 动态导入(PDF.js/epub.js 仅客户端)
const DocumentViewer = dynamic(() => import('@/components/DocumentViewer'), {
  ssr: false,
  loading: () => <div className="py-12 text-center text-muted-foreground">加载阅读器…</div>,
});

type Tab = 'overview' | 'original' | 'markdown' | 'derivatives';

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: '概览' },
  { id: 'original', label: '原始文档' },
  { id: 'markdown', label: 'Markdown' },
  { id: 'derivatives', label: '衍生品' },
];

export default function DocumentDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const [doc, setDoc] = useState<Substrate | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>('overview');

  useEffect(() => {
    setLoading(true);
    apiClient.get<Substrate>(`/api/v1/documents/${id}`)
      .then(r => setDoc(r.data))
      .catch(() => toast.error('加载文档失败'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-4 sm:p-6 max-w-4xl mx-auto"><CardSkeleton count={1} /></div>;
  if (!doc) return <div className="p-6 text-center text-muted-foreground">文档不存在</div>;

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold mb-1">{doc.title}</h1>
      <div className="text-xs text-muted-foreground mb-4">
        {doc.medium?.toUpperCase()} · {doc.language} · {new Date(doc.created_at).toLocaleDateString('zh-CN')}
      </div>

      {/* Tab 切换 */}
      <div className="flex gap-1 border-b mb-4 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id}
            className={`px-4 py-2 text-sm border-b-2 min-h-11 whitespace-nowrap ${
              tab === t.id ? 'border-primary text-primary font-medium' : 'border-transparent text-muted-foreground'}`}
            onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="text-sm text-muted-foreground">
          <p>类型:{doc.mime}</p>
          <p>来源:{doc.source}</p>
          {doc.page_count != null && <p>页数:{doc.page_count}</p>}
        </div>
      )}

      {/* ★ 原始文档 Tab:内嵌阅读器 */}
      {tab === 'original' && (
        <DocumentViewer
          documentId={doc.id}
          mime={doc.mime}
          medium={doc.medium}
          title={doc.title}
          byteSize={doc.byte_size}
        />
      )}

      {tab === 'markdown' && (
        <div className="text-sm text-muted-foreground">Markdown 内容(由现有页面提供)</div>
      )}
      {tab === 'derivatives' && (
        <div className="text-sm text-muted-foreground">衍生品列表(由现有页面提供)</div>
      )}
    </div>
  );
}
