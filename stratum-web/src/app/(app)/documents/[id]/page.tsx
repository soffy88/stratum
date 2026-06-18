'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';

// ★ DocumentViewer 动态导入(PDF.js/epub.js 仅客户端)
const DocumentViewer = dynamic(() => import('@/components/DocumentViewer'), {
  ssr: false,
  loading: () => <div className="py-12 text-center text-muted-foreground">加载阅读器…</div>,
});

interface Derivative {
  kind: string;
  content?: string | null;
}

interface Substrate {
  id: string;
  title: string;
  mime: string;
  medium: string;
  source: string;
  created_at: string;
  source_path?: string | null;
  byte_size?: number | null;
  page_count?: number | null;
  language?: string;
}

const TABS = [
  { key: 'overview',     label: '概览' },
  { key: 'original',     label: '原始文档' },
  { key: 'markdown',     label: 'Markdown' },
  { key: 'translation',  label: '中文翻译' },
  { key: 'audio',        label: '音频朗读' },
  { key: 'illustration', label: '插图' },
] as const;

const EMPTY_MSG: Record<string, string> = {
  markdown:    'Markdown 未生成',
  translation: '中文翻译未生成',
  audio:       '音频朗读未生成',
  illustration: '插图未生成',
};

const GENERATE_LABEL: Record<string, string> = {
  markdown:    '立即生成 Markdown',
  translation: '立即翻译',
  audio:       '立即生成音频',
  illustration: '立即生成插图',
};

function fmtSize(bytes?: number | null): string {
  if (!bytes) return '';
  const mb = bytes / 1024 / 1024;
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [doc, setDoc] = useState<Substrate | null>(null);
  const [derivatives, setDerivatives] = useState<Derivative[]>([]);
  const [activeTab, setActiveTab] = useState<string>('markdown');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<string | null>(null);

  const loadAll = async (showLoader = false) => {
    if (!id) return;
    if (showLoader) setLoading(true);
    try {
      const [docRes, derivRes] = await Promise.all([
        apiClient.get<Substrate>(`/api/v1/documents/${id}`),
        apiClient.get<Derivative[]>(`/api/v1/documents/${id}/derivatives`),
      ]);
      setDoc(docRes.data);
      setDerivatives(derivRes.data);
    } catch {
      toast.error('加载文档失败');
    } finally {
      if (showLoader) setLoading(false);
    }
  };

  useEffect(() => {
    loadAll(true);
  }, [id]);

  const handleGenerate = async (kind: string) => {
    if (!id || generating) return;
    setGenerating(kind);
    try {
      await apiClient.post(`/api/v1/documents/${id}/generate`, { kind });
      // Poll once after 3s for updated derivatives
      setTimeout(() => {
        apiClient.get<Derivative[]>(`/api/v1/documents/${id}/derivatives`)
          .then(r => setDerivatives(r.data))
          .catch(() => {})
          .finally(() => setGenerating(null));
      }, 3000);
    } catch {
      setGenerating(null);
    }
  };

  if (loading) return <div className="p-8 text-muted-foreground">加载中...</div>;
  if (!doc) return <div className="p-8 text-red-600">文档不存在</div>;

  const getContent = (kind: string) =>
    derivatives.find(d => d.kind === kind)?.content ?? null;

  const filename = doc.source_path
    ? doc.source_path.split('/').pop()
    : doc.title;

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6">
      <button
        onClick={() => router.back()}
        className="text-sm text-muted-foreground mb-4 hover:text-foreground min-h-9 px-1"
      >
        ← 返回
      </button>

      <h1 className="text-2xl font-semibold mb-1">{doc.title}</h1>
      <p className="text-sm text-muted-foreground mb-6">
        {doc.medium?.toUpperCase() || doc.mime}
        {doc.byte_size ? ` · ${fmtSize(doc.byte_size)}` : ''}
        {doc.page_count ? ` · ${doc.page_count} 页` : ''}
        {' · '}{doc.created_at.slice(0, 10)}
      </p>

      {/* Tab 栏 */}
      <div className="flex gap-1 border-b mb-6 overflow-x-auto">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap min-h-11 ${
              activeTab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 内容区 */}
      <div className="prose dark:prose-invert max-w-none">
        {activeTab === 'overview' && (
          <div className="text-sm space-y-2 text-muted-foreground">
            <p><strong>文件名:</strong> {filename}</p>
            <p><strong>MIME 类型:</strong> {doc.mime}</p>
            <p><strong>来源:</strong> {doc.source}</p>
            {doc.language && <p><strong>语言:</strong> {doc.language}</p>}
            {doc.source_path && <p className="break-all"><strong>路径:</strong> {doc.source_path}</p>}
          </div>
        )}

        {/* ★ 原始文档 Tab:内嵌阅读器 */}
        {activeTab === 'original' && (
          <DocumentViewer
            documentId={doc.id}
            mime={doc.mime}
            medium={doc.medium}
            title={doc.title}
            byteSize={doc.byte_size}
          />
        )}
        {['markdown', 'translation', 'audio', 'illustration'].includes(activeTab) && (
          getContent(activeTab) ? (
            <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans">{getContent(activeTab)}</pre>
          ) : (
            <div className="text-center py-16">
              <p className="text-muted-foreground mb-4">
                {EMPTY_MSG[activeTab] ?? '内容未生成'}
              </p>
              <button
                onClick={() => handleGenerate(activeTab)}
                disabled={!!generating}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 disabled:opacity-50 min-h-11"
              >
                {generating === activeTab ? '生成中...' : (GENERATE_LABEL[activeTab] ?? '立即生成')}
              </button>
            </div>
          )
        )}
      </div>
    </div>
  );
}
