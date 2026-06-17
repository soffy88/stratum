'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { listDocuments, type Substrate } from '@/lib/documents';

type TabKey = 'original' | 'markdown' | 'translation' | 'audio' | 'illustration';

const TABS: { key: TabKey; label: string; emptyMsg: string }[] = [
  { key: 'original',     label: '原始文档', emptyMsg: '暂无文档，点右上角入库' },
  { key: 'markdown',     label: 'Markdown', emptyMsg: '还没有 Markdown 内容，在文档详情页点「立即生成」' },
  { key: 'translation',  label: '中文翻译', emptyMsg: '还没有翻译内容，在文档详情页点「立即生成」' },
  { key: 'audio',        label: '音频朗读', emptyMsg: '还没有音频内容，在文档详情页点「立即生成」' },
  { key: 'illustration', label: '插图',     emptyMsg: '还没有插图内容，在文档详情页点「立即生成」' },
];

const MIME_ICON: Record<string, string> = {
  'application/pdf':     '📄',
  'application/epub+zip':'📗',
  'text/plain':          '📝',
  'text/markdown':       '📝',
  'text/html':           '🌐',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📃',
};

function fmtSize(bytes?: number): string {
  if (!bytes) return '';
  const mb = bytes / 1024 / 1024;
  return mb >= 1 ? `${mb.toFixed(0)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

export default function DocumentsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>('original');
  const [docs, setDocs] = useState<Substrate[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');

  const load = useCallback(async (tab: TabKey, query: string) => {
    setLoading(true);
    try {
      const params: { limit: number; kind?: string; q?: string } = { limit: 500 };
      if (tab !== 'original') params.kind = tab;
      if (query) params.q = query;
      const res = await listDocuments(params);
      setDocs(res.items ?? []);
    } catch {
      toast.error('加载文档失败');
      setDocs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(activeTab, q); }, [load, activeTab, q]);

  const tabInfo = TABS.find(t => t.key === activeTab)!;

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      {/* 页头 */}
      <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <h1 className="text-xl font-bold">文档</h1>
        <div className="flex gap-2">
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">上传文件</button>
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">输入 URL</button>
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">订阅 RSS</button>
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">文件夹</button>
        </div>
      </div>

      {/* Tab 栏 */}
      <div className="flex border-b mb-4 overflow-x-auto">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 搜索 */}
      <input
        className="w-full mb-4 px-3 py-2 rounded-lg border bg-background text-sm min-h-11"
        placeholder="搜索文档..."
        value={q}
        onChange={e => setQ(e.target.value)}
      />

      {/* 内容 */}
      {loading ? (
        <div className="text-center text-muted-foreground py-8">加载中…</div>
      ) : docs.length === 0 ? (
        <div className="text-center text-muted-foreground py-16">{tabInfo.emptyMsg}</div>
      ) : (
        <>
          <div className="text-xs text-muted-foreground mb-3">
            {docs.length} 篇文档
          </div>
          <div className="flex flex-col">
            {docs.map(d => (
              <div key={d.id} className="flex items-center gap-3 py-3 border-b last:border-0">
                <span className="text-xl shrink-0">{MIME_ICON[d.mime] ?? '📄'}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate text-sm">{d.title}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {(d.medium || 'PDF').toUpperCase()}
                    {d.byte_size ? ` · ${fmtSize(d.byte_size)}` : ''}
                    {` · ${new Date(d.created_at).toLocaleDateString('zh-CN')}`}
                    {d.source && d.source !== 'upload' ? ` · ${d.source}` : ''}
                  </div>
                </div>
                <button
                  onClick={() => router.push(`/documents/${d.id}`)}
                  className="text-sm px-3 min-h-9 rounded-lg border hover:bg-muted shrink-0"
                >
                  查看
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
