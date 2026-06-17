'use client';

/**
 * /documents — 真实文档列表(替换 ODocumentTree stub)
 * 图标 + 标题 + 类型/来源 + 4 衍生品状态标签 + 分页 + View Banner。
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { listDocuments, getDerivatives, type Substrate, type DerivativeKind } from '@/lib/documents';
import { listViews, type View } from '@/lib/views';
import { CardSkeleton } from '@/components/LoadingSkeleton';

const PAGE_SIZE = 50;

const MIME_ICON: Record<string, string> = {
  'application/pdf': '📄',
  'application/epub+zip': '📗',
  'text/plain': '📝',
  'text/markdown': '📝',
  'text/html': '🌐',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📃',
};

const DERIV_LABEL: Record<DerivativeKind, string> = {
  markdown: 'MD', translation: '译', audio: '音频', illustration: '插图',
};
const DERIV_ORDER: DerivativeKind[] = ['markdown', 'translation', 'audio', 'illustration'];

function fmtSize(bytes?: number): string {
  if (!bytes) return '';
  const mb = bytes / 1024 / 1024;
  return mb >= 1 ? `${mb.toFixed(0)}MB` : `${(bytes / 1024).toFixed(0)}KB`;
}

function DerivativeBadges({ substrateId }: { substrateId: string }) {
  const [kinds, setKinds] = useState<Set<DerivativeKind> | null>(null);
  useEffect(() => {
    let live = true;
    getDerivatives(substrateId)
      .then(d => { if (live) setKinds(new Set(d.map(x => x.kind))); })
      .catch(() => { if (live) setKinds(new Set()); });
    return () => { live = false; };
  }, [substrateId]);

  return (
    <div className="flex gap-1.5">
      {DERIV_ORDER.map(k => {
        const has = kinds?.has(k);
        return (
          <span key={k}
            className={`text-xs px-1.5 py-0.5 rounded ${
              has ? 'bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400'
                  : 'bg-muted text-muted-foreground'}`}>
            {DERIV_LABEL[k]} {has ? '✓' : '–'}
          </span>
        );
      })}
    </div>
  );
}

export default function DocumentsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const viewId = searchParams.get('view');
  const page = Math.max(1, Number(searchParams.get('page') ?? '1'));

  const [docs, setDocs] = useState<Substrate[]>([]);
  const [total, setTotal] = useState(0);
  const [currentView, setCurrentView] = useState<View | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');

  useEffect(() => {
    if (!viewId) { setCurrentView(null); return; }
    listViews().then(vs => setCurrentView(vs.find(v => v.id === viewId) ?? null)).catch(() => {});
  }, [viewId]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDocuments({
        view: viewId ?? undefined, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE,
        q: q || undefined,
      });
      setDocs(res.items);
      setTotal(res.total);
    } catch { toast.error('加载文档失败'); }
    finally { setLoading(false); }
  }, [viewId, page, q]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const goPage = (p: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('page', String(p));
    router.push(`/documents?${params.toString()}`);
  };

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <h1 className="text-xl font-bold">文档</h1>
        <div className="flex gap-2">
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">上传文件</button>
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">输入 URL</button>
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">订阅 RSS</button>
          <button className="text-sm px-3 min-h-11 rounded-lg border hover:bg-muted">文件夹</button>
        </div>
      </div>

      {viewId && currentView && (
        <div className="flex items-center gap-2 px-4 py-2 bg-muted rounded-lg mb-4">
          <span className="font-medium">{currentView.icon} {currentView.name}</span>
          <span className="text-muted-foreground text-sm">· {total} 篇文档</span>
          <button onClick={() => router.push('/documents')} className="ml-auto text-sm text-primary hover:underline min-h-9 px-2">
            清除视图
          </button>
        </div>
      )}

      <input
        className="w-full mb-4 px-3 py-2 rounded-lg border bg-background text-sm min-h-11"
        placeholder="搜索文档..."
        value={q}
        onChange={e => setQ(e.target.value)}
      />

      {loading ? <CardSkeleton count={6} /> : docs.length === 0 ? (
        <div className="text-center text-muted-foreground py-16">暂无文档,点右上角入库</div>
      ) : (
        <div className="flex flex-col">
          {docs.map(d => (
            <div key={d.id} className="flex items-start gap-3 py-3 border-b last:border-0">
              <span className="text-2xl shrink-0">{MIME_ICON[d.mime] ?? '📄'}</span>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{d.title}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {d.medium?.toUpperCase()}
                  {d.byte_size ? ` · ${fmtSize(d.byte_size)}` : ''}
                  {` · ${new Date(d.created_at).toLocaleDateString('zh-CN')}`}
                  {` · ${d.source}`}
                </div>
                <div className="mt-2"><DerivativeBadges substrateId={d.id} /></div>
              </div>
              <div className="flex gap-1 shrink-0">
                <button onClick={() => router.push(`/documents/${d.id}`)}
                  className="text-sm px-3 min-h-9 rounded-lg border hover:bg-muted">查看</button>
                <button className="text-sm px-2 min-h-9 rounded-lg hover:bg-muted">⋯</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && total > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-6">
          <span className="text-sm text-muted-foreground">共 {total} 篇文档</span>
          <div className="flex gap-1 items-center">
            <button disabled={page <= 1} onClick={() => goPage(page - 1)}
              className="px-3 min-h-9 rounded-lg border disabled:opacity-40 hover:bg-muted">‹</button>
            <span className="text-sm px-2">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => goPage(page + 1)}
              className="px-3 min-h-9 rounded-lg border disabled:opacity-40 hover:bg-muted">›</button>
          </div>
        </div>
      )}
    </div>
  );
}
