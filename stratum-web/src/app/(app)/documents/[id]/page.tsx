'use client';

/**
 * /documents/[id] — 文档详情页
 * Tab:概览 / 原始文档(三栏满屏阅读器)/ Markdown / 衍生品
 *
 * 原始文档 tab: 三栏布局
 *   左栏 — ConceptsPanel: 该文档关联概念 (按 type 分组，concepts 无 chapter_id)
 *   中栏 — DocumentViewer: PDF.js / EPUB.js
 *   右栏 — NotesPanel: 新建笔记(关联文档+选中概念) + 最近笔记
 */

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import type { Substrate, Derivative } from '@/lib/documents';
import { getDerivatives } from '@/lib/documents';
import { CardSkeleton } from '@/components/LoadingSkeleton';
import { ConceptsPanel } from '@/components/reader/ConceptsPanel';
import { NotesPanel } from '@/components/reader/NotesPanel';

const DocumentViewer = dynamic(() => import('@/components/DocumentViewer'), {
  ssr: false,
  loading: () => <div className="h-full flex items-center justify-center text-muted-foreground text-sm">加载阅读器…</div>,
});

type Tab = 'overview' | 'original' | 'markdown' | 'derivatives';

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: '概览' },
  { id: 'original', label: '原始文档' },
  { id: 'markdown', label: 'Markdown' },
  { id: 'derivatives', label: '衍生品' },
];

interface SelectedConcept { id: string; name: string; }

export default function DocumentDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const [doc, setDoc] = useState<Substrate | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>('overview');
  const [derivatives, setDerivatives] = useState<Derivative[]>([]);
  const [selectedConcept, setSelectedConcept] = useState<SelectedConcept | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      apiClient.get<Substrate>(`/api/v1/documents/${id}`).then(r => r.data),
      getDerivatives(id).catch(() => [] as Derivative[]),
    ])
      .then(([substrate, derivs]) => {
        setDoc(substrate);
        setDerivatives(derivs);
      })
      .catch(() => toast.error('加载文档失败'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-4 sm:p-6 max-w-4xl mx-auto"><CardSkeleton count={1} /></div>;
  if (!doc) return <div className="p-6 text-center text-muted-foreground">文档不存在</div>;

  // 三栏满屏阅读模式
  if (tab === 'original') {
    return (
      // -m-4 md:-m-6 抵消 layout <main> 的 p-4 md:p-6，撑满可用区域
      <div className="-m-4 md:-m-6 flex flex-col" style={{ height: 'calc(100vh - 0px)' }}>
        {/* 顶部导航栏 */}
        <div className="flex items-center h-11 border-b px-3 shrink-0 gap-3 bg-background">
          <button
            onClick={() => setTab('overview')}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors shrink-0"
          >
            ← 返回
          </button>
          <h1 className="text-sm font-medium truncate flex-1 min-w-0">{doc.title}</h1>
          <div className="flex gap-1 shrink-0">
            {TABS.filter(t => t.id !== 'original').map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className="text-xs px-2 py-1 rounded text-muted-foreground hover:bg-muted transition-colors"
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* 三栏主体 */}
        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* 左栏: 概念 */}
          <div className="w-56 shrink-0 border-r overflow-y-auto bg-background">
            <div className="px-3 py-2 border-b text-xs font-semibold text-muted-foreground">本书概念</div>
            <ConceptsPanel
              documentId={id}
              selectedId={selectedConcept?.id ?? null}
              onSelect={c => setSelectedConcept(c ? { id: c.id, name: c.name } : null)}
            />
          </div>

          {/* 中栏: 阅读器 */}
          <div className="flex-1 overflow-hidden min-w-0">
            <DocumentViewer
              documentId={doc.id}
              mime={doc.mime}
              medium={doc.medium}
              title={doc.title}
              byteSize={doc.byte_size}
              fullHeight
            />
          </div>

          {/* 右栏: 笔记 */}
          <div className="w-64 shrink-0 border-l overflow-hidden flex flex-col bg-background">
            <div className="px-3 py-2 border-b text-xs font-semibold text-muted-foreground">笔记</div>
            <NotesPanel documentId={id} selectedConcept={selectedConcept} />
          </div>
        </div>
      </div>
    );
  }

  // 普通详情页
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

      {tab === 'markdown' && (() => {
        const md = derivatives.find(d => d.kind === 'markdown');
        if (!md?.content) return (
          <div className="text-sm text-muted-foreground py-8 text-center">暂无 Markdown 内容</div>
        );
        return (
          <pre className="whitespace-pre-wrap text-sm font-mono leading-relaxed overflow-auto max-h-[70vh] border rounded p-4 bg-muted/30">
            {md.content}
          </pre>
        );
      })()}

      {tab === 'derivatives' && (
        <div className="space-y-2 text-sm">
          {derivatives.length === 0
            ? <p className="text-muted-foreground py-8 text-center">暂无衍生品</p>
            : derivatives.map((d, i) => (
                <div key={i} className="border rounded p-3">
                  <span className="font-medium text-xs uppercase tracking-wide text-muted-foreground">{d.kind}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{d.content ? `${d.content.length.toLocaleString()} 字` : '无内容'}</span>
                </div>
              ))
          }
        </div>
      )}
    </div>
  );
}
