'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { apiClient } from '@/lib/apiClient';

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
}

const TABS = [
  { key: 'original',     label: '原始文档' },
  { key: 'markdown',     label: 'Markdown' },
  { key: 'translation',  label: '中文翻译' },
  { key: 'audio',        label: '音频朗读' },
  { key: 'illustration', label: '插图' },
] as const;

const EMPTY_MSG: Record<string, string> = {
  markdown:    'Markdown 未生成。入库时勾选对应 AI 处理选项后自动生成。',
  translation: '中文翻译未生成。',
  audio:       '音频朗读未生成。',
  illustration:'插图未生成。',
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [doc, setDoc] = useState<Substrate | null>(null);
  const [derivatives, setDerivatives] = useState<Derivative[]>([]);
  const [activeTab, setActiveTab] = useState<string>('markdown');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      apiClient.get<Substrate>(`/api/v1/documents/${id}`),
      apiClient.get<Derivative[]>(`/api/v1/documents/${id}/derivatives`),
    ])
      .then(([docRes, derivRes]) => {
        setDoc(docRes.data);
        setDerivatives(derivRes.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-8 text-muted-foreground">加载中...</div>;
  if (!doc) return <div className="p-8 text-red-600">文档不存在</div>;

  const getContent = (kind: string) =>
    derivatives.find(d => d.kind === kind)?.content ?? null;

  return (
    <div className="max-w-4xl mx-auto p-6">
      <button
        onClick={() => router.back()}
        className="text-sm text-muted-foreground mb-4 hover:text-foreground min-h-9 px-1"
      >
        ← 返回
      </button>

      <h1 className="text-2xl font-semibold mb-1">{doc.title}</h1>
      <p className="text-sm text-muted-foreground mb-6">
        {doc.medium?.toUpperCase() || doc.mime}
        {' · '}{doc.source}
        {' · '}{doc.created_at.slice(0, 10)}
      </p>

      {/* Tab 栏 */}
      <div className="flex gap-1 border-b mb-6">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
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
        {activeTab === 'original' ? (
          <p className="text-muted-foreground">原始文件预览暂不支持，请下载查看。</p>
        ) : getContent(activeTab) ? (
          <pre className="whitespace-pre-wrap text-sm leading-relaxed">{getContent(activeTab)}</pre>
        ) : (
          <p className="text-muted-foreground">
            {EMPTY_MSG[activeTab] ?? '内容未生成。'}
          </p>
        )}
      </div>
    </div>
  );
}
