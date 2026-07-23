'use client';

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';

interface FolderWatch {
  id: string;
  path: string;
  description: string | null;
  status: 'active' | 'paused';
  scan_status: 'idle' | 'scanning' | 'completed' | 'error';
  last_scan_at: string | null;
  file_count: number;
  scanned_count: number;
  ingested_count: number;
  current_file: string;
}

interface ChannelSub {
  id: string;
  channel_url: string;
  channel_title: string | null;
  status: 'active' | 'paused';
  scan_status: 'idle' | 'scanning' | 'completed' | 'error';
  last_check: string | null;
  found_count: number;
  ingested_count: number;
  current_video: string | null;
}

interface SourceSub {
  id: string;
  source_type: 'arxiv' | 'gutenberg' | 'oapen' | 'openstax' | 'mit_ocw';
  name: string;
  query: Record<string, unknown>;
  status: 'active' | 'paused';
  scan_status: 'idle' | 'scanning' | 'completed' | 'error';
  last_check: string | null;
  found_count: number;
  ingested_count: number;
  current_item: string | null;
}

function relativeTime(ts: string | null): string {
  if (!ts) return '从未';
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'scanning') {
    return (
      <span className="flex items-center gap-1 text-primary text-[11px] font-medium">
        <span className="w-2.5 h-2.5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        扫描中
      </span>
    );
  }
  if (status === 'completed') return <span className="text-[11px] text-green-600 font-medium">✓ 完成</span>;
  if (status === 'error') return <span className="text-[11px] text-destructive font-medium">✗ 错误</span>;
  if (status === 'idle') return <span className="text-[11px] text-muted-foreground">待扫描</span>;
  return null;
}

export function BackgroundTasksPanel({ onFolderDeleted }: { onFolderDeleted?: () => void }) {
  const [folders, setFolders] = useState<FolderWatch[]>([]);
  const [channels, setChannels] = useState<ChannelSub[]>([]);
  const [sources, setSources] = useState<SourceSub[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  const fetchAll = useCallback(async () => {
    const [fw, ch, src] = await Promise.all([
      apiClient.get<FolderWatch[]>('/api/v1/folder-watch').then(r => r.data ?? []).catch(() => []),
      apiClient.get<ChannelSub[]>('/api/v1/channels').then(r => r.data ?? []).catch(() => []),
      apiClient.get<SourceSub[]>('/api/v1/sources').then(r => r.data ?? []).catch(() => []),
    ]);
    setFolders(fw);
    setChannels(ch);
    setSources(src);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // 有扫描中的任务时每 4s 轮询
  useEffect(() => {
    const hasActive = [...folders, ...channels, ...sources].some(
      t => t.scan_status === 'scanning'
    );
    if (!hasActive) return;
    const timer = setInterval(fetchAll, 4000);
    return () => clearInterval(timer);
  }, [folders, channels, sources, fetchAll]);

  const pauseFolder = async (id: string) => {
    try {
      await apiClient.patch(`/api/v1/folder-watch/${id}/pause`, {});
      toast.success('已暂停监听');
      fetchAll();
    } catch { toast.error('操作失败'); }
  };

  const resumeFolder = async (id: string) => {
    try {
      await apiClient.patch(`/api/v1/folder-watch/${id}/resume`, {});
      toast.success('已恢复监听');
      fetchAll();
    } catch { toast.error('操作失败'); }
  };

  const deleteFolder = async (id: string, path: string) => {
    if (!confirm(`删除监听「${path}」？`)) return;
    try {
      await apiClient.delete(`/api/v1/folder-watch/${id}`);
      toast.success('已删除');
      fetchAll();
      onFolderDeleted?.();
    } catch { toast.error('删除失败'); }
  };

  const toggleChannel = async (sub: ChannelSub) => {
    const next = sub.status === 'active' ? 'paused' : 'active';
    try {
      await apiClient.patch(`/api/v1/channels/${sub.id}`, { status: next });
      toast.success(next === 'active' ? '已恢复订阅' : '已暂停订阅');
      fetchAll();
    } catch { toast.error('操作失败'); }
  };

  const deleteChannel = async (id: string) => {
    if (!confirm('删除该频道订阅？')) return;
    try {
      await apiClient.delete(`/api/v1/channels/${id}`);
      toast.success('已删除');
      fetchAll();
    } catch { toast.error('删除失败'); }
  };

  const toggleSource = async (sub: SourceSub) => {
    const next = sub.status === 'active' ? 'paused' : 'active';
    try {
      await apiClient.patch(`/api/v1/sources/${sub.id}`, { status: next });
      toast.success(next === 'active' ? '已恢复订阅' : '已暂停订阅');
      fetchAll();
    } catch { toast.error('操作失败'); }
  };

  const deleteSource = async (sub: SourceSub) => {
    const label = sub.name || sub.source_type;
    if (!confirm(`删除订阅「${label}」？`)) return;
    try {
      await apiClient.delete(`/api/v1/sources/${sub.id}`);
      toast.success('已删除');
      fetchAll();
    } catch { toast.error('删除失败'); }
  };

  const total = folders.length + channels.length + sources.length;
  if (total === 0) return null;

  const anyScanning = [...folders, ...channels, ...sources].some(t => t.scan_status === 'scanning');

  return (
    <div className="mb-5 border border-border rounded-xl overflow-hidden bg-card">
      {/* 标题栏 */}
      <button
        onClick={() => setCollapsed(c => !c)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">后台任务</span>
          {anyScanning && (
            <span className="flex items-center gap-1 text-[11px] text-primary font-medium">
              <span className="w-2 h-2 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              运行中
            </span>
          )}
          <span className="text-[11px] text-muted-foreground">
            {folders.length > 0 && `${folders.length} 个文件夹`}
            {folders.length > 0 && channels.length > 0 && ' · '}
            {channels.length > 0 && `${channels.length} 个频道`}
            {(folders.length > 0 || channels.length > 0) && sources.length > 0 && ' · '}
            {sources.length > 0 && `${sources.length} 个资料源`}
          </span>
        </div>
        <span className="text-muted-foreground text-xs">{collapsed ? '▼' : '▲'}</span>
      </button>

      {!collapsed && (
        <div className="divide-y divide-border/60">
          {/* 文件夹监听 */}
          {folders.map(fw => (
            <div key={fw.id} className="px-4 py-3 flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm">📁</span>
                  <span className="text-sm font-medium truncate max-w-[260px]" title={fw.path}>
                    {fw.path.split('/').pop() || fw.path}
                  </span>
                  {fw.status === 'paused' && (
                    <span className="text-[10px] px-1.5 rounded bg-muted text-muted-foreground">已暂停</span>
                  )}
                  <StatusBadge status={fw.scan_status} />
                </div>
                <div className="text-[11px] text-muted-foreground pl-5 space-y-0.5">
                  {fw.scan_status === 'scanning' && fw.current_file ? (
                    <div className="truncate max-w-xs" title={fw.current_file}>
                      处理: {fw.current_file.split('/').pop()}
                      {fw.scanned_count > 0 && ` (${fw.scanned_count}/${fw.file_count || '?'})`}
                    </div>
                  ) : (
                    <div>
                      {fw.file_count > 0 && `共 ${fw.file_count} 个文件`}
                      {fw.scanned_count > 0 && ` · 已扫描 ${fw.scanned_count}`}
                      {fw.ingested_count > 0 && ` · 已入库 ${fw.ingested_count}`}
                      {fw.last_scan_at && ` · ${relativeTime(fw.last_scan_at)}`}
                    </div>
                  )}
                  <div className="text-[10px] text-muted-foreground/70 truncate">{fw.path}</div>
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                <button
                  onClick={() => fw.status === 'active' ? pauseFolder(fw.id) : resumeFolder(fw.id)}
                  className="text-[11px] px-2 py-1 rounded border border-border hover:bg-muted transition-colors"
                >
                  {fw.status === 'active' ? '暂停' : '恢复'}
                </button>
                <button
                  onClick={() => deleteFolder(fw.id, fw.path)}
                  className="text-[11px] px-2 py-1 rounded border border-border text-destructive hover:bg-destructive/10 transition-colors"
                >
                  删除
                </button>
              </div>
            </div>
          ))}

          {/* 频道订阅 */}
          {channels.map(ch => (
            <div key={ch.id} className="px-4 py-3 flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm">📺</span>
                  <span className="text-sm font-medium truncate max-w-[260px]" title={ch.channel_title || ch.channel_url}>
                    {ch.channel_title || ch.channel_url.replace('https://www.youtube.com/', 'YT/')}
                  </span>
                  {ch.status === 'paused' && (
                    <span className="text-[10px] px-1.5 rounded bg-muted text-muted-foreground">已暂停</span>
                  )}
                  <StatusBadge status={ch.scan_status} />
                </div>
                <div className="text-[11px] text-muted-foreground pl-5 space-y-0.5">
                  {ch.scan_status === 'scanning' && ch.current_video ? (
                    <div className="truncate max-w-xs" title={ch.current_video}>
                      处理: {ch.current_video}
                    </div>
                  ) : (
                    <div>
                      {ch.found_count > 0 && `已找到 ${ch.found_count} 个视频`}
                      {ch.ingested_count > 0 && ` · 已入库 ${ch.ingested_count}`}
                      {ch.last_check && ` · ${relativeTime(ch.last_check)}`}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                <button
                  onClick={() => toggleChannel(ch)}
                  className="text-[11px] px-2 py-1 rounded border border-border hover:bg-muted transition-colors"
                >
                  {ch.status === 'active' ? '暂停' : '恢复'}
                </button>
                <button
                  onClick={() => deleteChannel(ch.id)}
                  className="text-[11px] px-2 py-1 rounded border border-border text-destructive hover:bg-destructive/10 transition-colors"
                >
                  删除
                </button>
              </div>
            </div>
          ))}

          {/* 资料源订阅（arXiv / Gutenberg / OAPEN / OpenStax / MIT OCW）*/}
          {sources.map(src => {
            const icon = src.source_type === 'arxiv' ? '📰'
              : src.source_type === 'gutenberg' ? '📚'
              : src.source_type === 'openstax'  ? '🔬'
              : src.source_type === 'mit_ocw'   ? '🎓'
              : '📖';
            const q = src.query || {};
            const queryDesc = src.source_type === 'arxiv'
              ? [
                  ...((q.categories as string[] | undefined) || []).slice(0, 3),
                  ...(q.keywords ? [`"${q.keywords}"`] : []),
                ].join(' · ')
              : src.source_type === 'gutenberg'
              ? [q.topic, q.keywords, q.author].filter(Boolean).join(' · ')
              : src.source_type === 'openstax'
              ? [(q.subjects as string[] | undefined)?.join(','), q.keywords].filter(Boolean).join(' · ')
              : src.source_type === 'mit_ocw'
              ? [(q.departments as string[] | undefined)?.map((d: string) => `dept${d}`).join(','), q.keywords].filter(Boolean).join(' · ')
              : String(q.query || '');
            const itemUnit = src.source_type === 'arxiv' ? '篇'
              : src.source_type === 'mit_ocw' ? '讲义'
              : '本';
            return (
              <div key={src.id} className="px-4 py-3 flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm">{icon}</span>
                    <span className="text-sm font-medium truncate max-w-[260px]" title={src.name}>
                      {src.name}
                    </span>
                    <span className="text-[10px] px-1.5 rounded bg-muted/60 text-muted-foreground">{src.source_type}</span>
                    {src.status === 'paused' && (
                      <span className="text-[10px] px-1.5 rounded bg-muted text-muted-foreground">已暂停</span>
                    )}
                    <StatusBadge status={src.scan_status} />
                  </div>
                  <div className="text-[11px] text-muted-foreground pl-5 space-y-0.5">
                    {src.scan_status === 'scanning' && src.current_item ? (
                      <div className="truncate max-w-xs" title={src.current_item}>
                        处理: {src.current_item}
                      </div>
                    ) : (
                      <div>
                        {queryDesc && <span>{queryDesc}</span>}
                        {src.found_count > 0 && ` · 找到 ${src.found_count} ${itemUnit}`}
                        {src.ingested_count > 0 && ` · 已入库 ${src.ingested_count}`}
                        {src.last_check && ` · ${relativeTime(src.last_check)}`}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                  <button
                    onClick={() => toggleSource(src)}
                    className="text-[11px] px-2 py-1 rounded border border-border hover:bg-muted transition-colors"
                  >
                    {src.status === 'active' ? '暂停' : '恢复'}
                  </button>
                  <button
                    onClick={() => deleteSource(src)}
                    className="text-[11px] px-2 py-1 rounded border border-border text-destructive hover:bg-destructive/10 transition-colors"
                  >
                    删除
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
