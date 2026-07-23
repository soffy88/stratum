'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { listDocuments, type Substrate } from '@/lib/documents';
import { cleanTitle, classifySubstrate, ALL_SUBJECTS, type Subject } from '@/lib/classify';
import { UploadDialog } from '@/components/UploadDialog';
import { UrlIngestDialog } from '@/components/UrlIngestDialog';
import { FolderIngestDialog } from '@/components/FolderIngestDialog';
import { FeedSubscribeDialog } from '@/components/FeedSubscribeDialog';
import { VideoIngestDialog } from '@/components/VideoIngestDialog';
import { ChannelSubscribeDialog } from '@/components/ChannelSubscribeDialog';
import { SourceSubscribeDialog } from '@/components/SourceSubscribeDialog';
import { BackgroundTasksPanel } from '@/components/BackgroundTasksPanel';

const MIME_ICON: Record<string, string> = {
  pdf: '📄', epub: '📗', book: '📗', text: '📝', webpage: '🌐', note: '📝', video: '🎬',
};

function getAuthor(d: Substrate): string {
  return (d.meta_json as Record<string, unknown> | null | undefined)?.author as string ?? '';
}

function matchesSubject(d: Substrate, subject: Subject | 'all'): boolean {
  if (subject === 'all') return true;
  return classifySubstrate(d.title, getAuthor(d)).includes(subject);
}

function PageCount({ d }: { d: Substrate }) {
  if (d.medium === 'pdf' && d.page_count) {
    return <span className="shrink-0 text-[10px] text-muted-foreground">{d.page_count}p</span>;
  }
  return null;
}

interface SectionCardProps {
  label: string;
  action: string;
  emptyMsg: string;
  items: Substrate[];
  loading: boolean;
  showPageCount?: boolean;
  onClickItem: (id: string) => void;
}

function SectionCard({ label, action, emptyMsg, items, loading, showPageCount, onClickItem }: SectionCardProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium">{label}</span>
        {!loading && <span className="text-xs text-muted-foreground">{items.length}</span>}
      </div>
      <div className="flex-1 overflow-y-auto" style={{ maxHeight: '400px' }}>
        {loading ? (
          <div className="text-xs text-muted-foreground py-4">加载中...</div>
        ) : items.length === 0 ? (
          <div className="text-xs text-muted-foreground py-4 leading-relaxed">{emptyMsg}</div>
        ) : (
          <ul className="space-y-1">
            {items.map(d => (
              <li
                key={d.id}
                onClick={() => onClickItem(d.id)}
                className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-md hover:bg-muted cursor-pointer group"
              >
                <span className="flex items-center gap-1.5 text-xs truncate min-w-0">
                  <span className="shrink-0">{MIME_ICON[d.medium] ?? '📄'}</span>
                  <span className="truncate">{cleanTitle(d.title) || d.title}</span>
                  {d.parse_quality === 'scanned' && (
                    <span className="shrink-0 text-[10px] px-1 rounded bg-muted text-muted-foreground">扫描版</span>
                  )}
                  {(d.parse_quality === 'empty' || d.parse_quality === 'garbled') && (
                    <span className="shrink-0 text-[10px] px-1 rounded bg-destructive/10 text-destructive">解析失败</span>
                  )}
                </span>
                <span className="flex items-center gap-1.5 shrink-0">
                  {showPageCount && <PageCount d={d} />}
                  <span className="text-xs text-primary opacity-0 group-hover:opacity-100">{action}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const [originals, setOriginals] = useState<Substrate[]>([]);
  const [markdowns, setMarkdowns] = useState<Substrate[]>([]);
  const [translations, setTranslations] = useState<Substrate[]>([]);
  const [audios, setAudios] = useState<Substrate[]>([]);
  const [illustrations, setIllustrations] = useState<Substrate[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [subject, setSubject] = useState<Subject | 'all'>('all');

  const [showUpload, setShowUpload] = useState(false);
  const [showUrl, setShowUrl] = useState(false);
  const [showFolder, setShowFolder] = useState(false);
  const [showFeed, setShowFeed] = useState(false);
  const [showVideo, setShowVideo] = useState(false);
  const [showChannel, setShowChannel] = useState(false);
  const [showArxiv, setShowArxiv] = useState(false);

  const loadAll = useCallback(async (query: string) => {
    setLoading(true);
    try {
      const [orig, md, tr, au, il] = await Promise.all([
        listDocuments({ limit: 500, q: query || undefined }).then(r => r?.items ?? []).catch(() => [] as Substrate[]),
        listDocuments({ limit: 500, kind: 'markdown', q: query || undefined }).then(r => r?.items ?? []).catch(() => [] as Substrate[]),
        listDocuments({ limit: 500, kind: 'translation', q: query || undefined }).then(r => r?.items ?? []).catch(() => [] as Substrate[]),
        listDocuments({ limit: 500, kind: 'audio', q: query || undefined }).then(r => r?.items ?? []).catch(() => [] as Substrate[]),
        listDocuments({ limit: 500, kind: 'illustration', q: query || undefined }).then(r => r?.items ?? []).catch(() => [] as Substrate[]),
      ]);
      setOriginals(orig);
      setMarkdowns(md);
      setTranslations(tr);
      setAudios(au);
      setIllustrations(il);
    } catch {
      toast.error('加载文档失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(q); }, [loadAll, q]);
  const refresh = () => loadAll(q);

  const filteredOrig = originals.filter(d => matchesSubject(d, subject));
  const filteredMd   = markdowns.filter(d => matchesSubject(d, subject));
  const nav = (id: string) => router.push(`/documents/${id}`);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      {/* 标题 + 入库按钮 */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h1 className="text-2xl font-semibold">文档</h1>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setShowUpload(true)} className="px-3 py-2 text-sm bg-primary text-primary-foreground rounded-lg min-h-11 hover:opacity-90">上传文件</button>
          <button onClick={() => setShowUrl(true)}    className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">输入 URL</button>
          <button onClick={() => setShowFeed(true)}   className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">订阅 RSS</button>
          <button onClick={() => setShowFolder(true)} className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">文件夹</button>
          <button onClick={() => setShowVideo(true)}  className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">视频 URL</button>
          <button onClick={() => setShowChannel(true)}className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">订阅频道</button>
          <button onClick={() => setShowArxiv(true)}  className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">订阅资料源</button>
        </div>
      </div>

      <BackgroundTasksPanel onFolderDeleted={refresh} />

      {/* 搜索 */}
      <input
        value={q}
        onChange={e => setQ(e.target.value)}
        placeholder="搜索文档..."
        className="w-full mb-4 px-4 py-2.5 border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/40"
      />

      {/* 科目筛选标签 */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {(['all', ...ALL_SUBJECTS] as const).map(s => (
          <button
            key={s}
            onClick={() => setSubject(s)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${
              subject === s
                ? 'bg-primary text-primary-foreground border-primary'
                : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
          >
            {s === 'all' ? '全部' : s}
          </button>
        ))}
      </div>

      {/* 第一排：源文件 + Markdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <SectionCard
          label="源文件"
          action="打开"
          emptyMsg="暂无文档，点右上角入库"
          items={filteredOrig}
          loading={loading}
          showPageCount
          onClickItem={nav}
        />
        <SectionCard
          label="Markdown"
          action="阅读"
          emptyMsg="还没有 Markdown"
          items={filteredMd}
          loading={loading}
          showPageCount
          onClickItem={nav}
        />
      </div>

      {/* 第二排：翻译 + 音频 + 插图 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SectionCard
          label="中文翻译"
          action="阅读"
          emptyMsg="还没有翻译，详情页点「立即生成」"
          items={translations}
          loading={loading}
          onClickItem={nav}
        />
        <SectionCard
          label="音频朗读"
          action="收听"
          emptyMsg="还没有音频，详情页点「立即生成」"
          items={audios}
          loading={loading}
          onClickItem={nav}
        />
        <SectionCard
          label="插图"
          action="查看"
          emptyMsg="还没有插图，详情页点「立即生成」"
          items={illustrations}
          loading={loading}
          onClickItem={nav}
        />
      </div>

      {showUpload  && <UploadDialog open={showUpload} onClose={() => setShowUpload(false)} onUploaded={() => { setShowUpload(false); refresh(); }} />}
      {showUrl     && <UrlIngestDialog open={showUrl} onClose={() => setShowUrl(false)} onIngested={() => { setShowUrl(false); refresh(); }} />}
      {showFolder  && <FolderIngestDialog open={showFolder} onClose={() => setShowFolder(false)} onCreated={() => { setShowFolder(false); refresh(); }} />}
      {showFeed    && <FeedSubscribeDialog onClose={() => { setShowFeed(false); refresh(); }} />}
      {showVideo   && <VideoIngestDialog open={showVideo} onClose={() => setShowVideo(false)} onIngested={() => { setShowVideo(false); refresh(); }} />}
      {showChannel && <ChannelSubscribeDialog open={showChannel} onClose={() => { setShowChannel(false); refresh(); }} />}
      {showArxiv   && <SourceSubscribeDialog open={showArxiv} onClose={() => { setShowArxiv(false); refresh(); }} />}
    </div>
  );
}
