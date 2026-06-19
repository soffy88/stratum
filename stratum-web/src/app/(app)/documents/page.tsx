'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { listDocuments, type Substrate } from '@/lib/documents';
import { UploadDialog } from '@/components/UploadDialog';
import { UrlIngestDialog } from '@/components/UrlIngestDialog';
import { FolderIngestDialog } from '@/components/FolderIngestDialog';
import { FeedSubscribeDialog } from '@/components/FeedSubscribeDialog';
import { VideoIngestDialog } from '@/components/VideoIngestDialog';
import { ChannelSubscribeDialog } from '@/components/ChannelSubscribeDialog';

type SectionKey = 'original' | 'markdown' | 'translation' | 'audio' | 'illustration';

interface SectionDef {
  key: SectionKey;
  label: string;
  kind?: string;
  action: string;
  emptyMsg: string;
}

const SECTIONS: SectionDef[] = [
  { key: 'original',     label: '原始文档', kind: undefined,     action: '打开', emptyMsg: '暂无文档，点右上角入库' },
  { key: 'markdown',     label: 'Markdown', kind: 'markdown',    action: '阅读', emptyMsg: '还没有 Markdown' },
  { key: 'translation',  label: '中文翻译', kind: 'translation', action: '阅读', emptyMsg: '还没有翻译，详情页点「立即生成」' },
  { key: 'audio',        label: '音频朗读', kind: 'audio',       action: '收听', emptyMsg: '还没有音频，详情页点「立即生成」' },
  { key: 'illustration', label: '插图',     kind: 'illustration',action: '查看', emptyMsg: '还没有插图，详情页点「立即生成」' },
];

const MIME_ICON: Record<string, string> = {
  pdf: '📄', epub: '📗', book: '📗', text: '📝', webpage: '🌐', note: '📝', video: '🎬',
};

export default function DocumentsPage() {
  const router = useRouter();
  const [sections, setSections] = useState<Record<SectionKey, Substrate[]>>({
    original: [], markdown: [], translation: [], audio: [], illustration: [],
  });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [showUrl, setShowUrl] = useState(false);
  const [showFolder, setShowFolder] = useState(false);
  const [showFeed, setShowFeed] = useState(false);
  const [showVideo, setShowVideo] = useState(false);
  const [showChannel, setShowChannel] = useState(false);

  const loadAll = useCallback(async (query: string) => {
    setLoading(true);
    try {
      const results: Substrate[][] = await Promise.all(
        SECTIONS.map(s =>
          listDocuments({ limit: 500, kind: s.kind, q: query || undefined })
            .then((r): Substrate[] => r?.items || [])
            .catch((): Substrate[] => [])
        )
      );
      const next = {} as Record<SectionKey, Substrate[]>;
      SECTIONS.forEach((s, i) => { next[s.key] = results[i] ?? []; });
      setSections(next);
    } catch {
      toast.error('加载文档失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(q); }, [loadAll, q]);

  const refresh = () => loadAll(q);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h1 className="text-2xl font-semibold">文档</h1>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setShowUpload(true)} className="px-3 py-2 text-sm bg-primary text-primary-foreground rounded-lg min-h-11 hover:opacity-90">上传文件</button>
          <button onClick={() => setShowUrl(true)} className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">输入 URL</button>
          <button onClick={() => setShowFeed(true)} className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">订阅 RSS</button>
          <button onClick={() => setShowFolder(true)} className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">文件夹</button>
          <button onClick={() => setShowVideo(true)} className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">视频 URL</button>
          <button onClick={() => setShowChannel(true)} className="px-3 py-2 text-sm border border-border rounded-lg min-h-11 hover:bg-muted">订阅频道</button>
        </div>
      </div>

      <input value={q} onChange={e => setQ(e.target.value)} placeholder="搜索文档..." className="w-full mb-6 px-4 py-2.5 border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/40" />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {SECTIONS.map(section => {
          const items = sections[section.key];
          return (
            <div key={section.key} className="bg-card border border-border rounded-xl p-4 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium">{section.label}</span>
                <span className="text-xs text-muted-foreground">{items.length}</span>
              </div>
              <div className="flex-1 overflow-y-auto" style={{ maxHeight: '420px' }}>
                {loading ? (
                  <div className="text-xs text-muted-foreground py-4">加载中...</div>
                ) : items.length === 0 ? (
                  <div className="text-xs text-muted-foreground py-4 leading-relaxed">{section.emptyMsg}</div>
                ) : (
                  <ul className="space-y-1">
                    {items.map(d => (
                      <li key={d.id} onClick={() => router.push(`/documents/${d.id}`)} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-md hover:bg-muted cursor-pointer group">
                        <span className="flex items-center gap-1.5 text-xs truncate min-w-0">
                          <span className="shrink-0">{MIME_ICON[d.medium] || '📄'}</span>
                          <span className="truncate">{d.title}</span>
                          {d.parse_quality === 'scanned' && <span className="shrink-0 text-[10px] px-1 py-0 rounded bg-muted text-muted-foreground">扫描版</span>}
                          {(d.parse_quality === 'empty' || d.parse_quality === 'garbled') && <span className="shrink-0 text-[10px] px-1 py-0 rounded bg-destructive/10 text-destructive">解析失败</span>}
                        </span>
                        <span className="text-xs text-primary shrink-0 opacity-0 group-hover:opacity-100">{section.action}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {section.key === 'original' && items.length > 0 && (
                <div className="text-xs text-muted-foreground mt-2 pt-2 border-t border-border">共 {items.length} 篇</div>
              )}
            </div>
          );
        })}
      </div>

      {showUpload && <UploadDialog open={showUpload} onClose={() => setShowUpload(false)} onUploaded={() => { setShowUpload(false); refresh(); }} />}
      {showUrl && <UrlIngestDialog open={showUrl} onClose={() => setShowUrl(false)} onIngested={() => { setShowUrl(false); refresh(); }} />}
      {showFolder && <FolderIngestDialog open={showFolder} onClose={() => setShowFolder(false)} onCreated={() => { setShowFolder(false); refresh(); }} />}
      {showFeed && <FeedSubscribeDialog onClose={() => { setShowFeed(false); refresh(); }} />}
      {showVideo && <VideoIngestDialog open={showVideo} onClose={() => setShowVideo(false)} onIngested={() => { setShowVideo(false); refresh(); }} />}
      {showChannel && <ChannelSubscribeDialog open={showChannel} onClose={() => { setShowChannel(false); refresh(); }} />}
    </div>
  );
}
