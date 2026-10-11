'use client';

/**
 * 生成 PPT — pick scope (whole book / one chapter), one of the 14 luobo-ppt
 * styles and a page count; the backend writes a lecture deck (结论式标题 +
 * 口播备注) from the book's stored understanding and returns an editable .pptx.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  PPT_STAGE_LABELS,
  createPptExport,
  downloadPptExport,
  fetchPptBlob,
  getPptBookChapters,
  getPptExport,
  getPptStyles,
  listPptExports,
  type PptChapter,
  type PptExportJob,
  type PptStyle,
} from '@/lib/ppt-export';

export interface PptExportDialogProps {
  open: boolean;
  onClose: () => void;
  /** The book (substrate) id. Either this or runId is required. */
  substrateId?: string;
  /** A BU2 run id, used by the chapter page which only knows the run. */
  runId?: string;
  /** Preselect a chapter (chapter page entry). */
  chapterId?: string;
  bookTitle?: string;
}

const POLL_MS = 3000;
const BOOK_SCOPE = '__book__';

function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function PptExportDialog({ open, onClose, substrateId, runId, chapterId, bookTitle }: PptExportDialogProps) {
  const [styles, setStyles] = useState<PptStyle[]>([]);
  const [style, setStyle] = useState('');
  const [pages, setPages] = useState(12);
  const [limits, setLimits] = useState({ min: 5, max: 30 });
  const [chapters, setChapters] = useState<PptChapter[]>([]);
  const [notReady, setNotReady] = useState<string | null>(null);
  const [scope, setScope] = useState<string>(chapterId ?? BOOK_SCOPE);
  const [audience, setAudience] = useState('');
  const [job, setJob] = useState<PptExportJob | null>(null);
  const [recent, setRecent] = useState<PptExportJob[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) return;
    setScope(chapterId ?? BOOK_SCOPE);
    getPptStyles()
      .then(r => {
        setStyles(r.styles);
        setStyle(s => s || r.default);
        setPages(r.pages.default);
        setLimits({ min: r.pages.min, max: r.pages.max });
      })
      .catch(e => toast.error(`加载风格失败：${errorText(e)}`));
    if (substrateId) {
      getPptBookChapters(substrateId)
        .then(r => {
          setChapters(r.chapters);
          setNotReady(r.ready ? null : r.reason || '这本书还没有完成书级理解');
        })
        .catch(() => setChapters([]));
      listPptExports(substrateId).then(setRecent).catch(() => setRecent([]));
    }
  }, [open, substrateId, chapterId]);

  const stopPolling = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  // Preview thumbnails are auth-protected: fetch as blobs.
  useEffect(() => {
    let cancelled = false;
    const urls: string[] = [];
    if (job?.status === 'succeeded' && job.preview_urls.length) {
      Promise.all(job.preview_urls.slice(0, 3).map(u => fetchPptBlob(u).then(b => URL.createObjectURL(b))))
        .then(list => {
          urls.push(...list);
          if (!cancelled) setPreviews(list);
        })
        .catch(() => setPreviews([]));
    } else {
      setPreviews([]);
    }
    return () => {
      cancelled = true;
      urls.forEach(u => URL.revokeObjectURL(u));
    };
  }, [job?.job_id, job?.status, job?.preview_urls]);

  const poll = useCallback(
    (id: string) => {
      stopPolling();
      timer.current = setTimeout(async () => {
        try {
          const j = await getPptExport(id);
          setJob(j);
          if (j.status === 'queued' || j.status === 'running') poll(id);
          else if (j.status === 'succeeded') toast.success('PPT 已生成');
          else toast.error(`生成失败：${j.error ?? '未知错误'}`);
        } catch (e) {
          toast.error(`查询进度失败：${errorText(e)}`);
        }
      }, POLL_MS);
    },
    [stopPolling],
  );

  const start = async () => {
    if (!style) return;
    setSubmitting(true);
    try {
      const j = await createPptExport({
        substrate_id: substrateId,
        run_id: substrateId ? undefined : runId,
        chapter_id: scope === BOOK_SCOPE ? null : scope,
        style,
        pages: Math.min(limits.max, Math.max(limits.min, pages)),
        audience: audience.trim() || undefined,
      });
      setJob(j);
      poll(j.job_id);
    } catch (e) {
      toast.error(`无法开始生成：${errorText(e)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const close = () => {
    stopPolling();
    setJob(null);
    onClose();
  };

  const running = job?.status === 'queued' || job?.status === 'running';
  const chapterOptions: PptChapter[] =
    chapters.length > 0
      ? chapters
      : chapterId
        ? [{ chapter_id: chapterId, title: `本章（${chapterId}）`, question: '' }]
        : [];

  return (
    <Dialog open={open} onOpenChange={o => { if (!o) close(); }}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>生成 PPT</DialogTitle>
          <p className="text-xs text-muted-foreground mt-1">
            {bookTitle ? `《${bookTitle}》· ` : ''}讲解型课件：结论式标题、屏幕要点、口播备注，导出可编辑的 .pptx。
            内容只取自 AII 对这本书的理解与原文。
          </p>
        </DialogHeader>

        {notReady && (
          <div className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            {notReady}
          </div>
        )}

        {!job && (
          <div className="flex flex-col gap-4 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-muted-foreground">范围</span>
              <select
                aria-label="范围"
                value={scope}
                onChange={e => setScope(e.target.value)}
                className="h-9 rounded-md border border-[var(--color-border)] bg-background px-2"
              >
                <option value={BOOK_SCOPE}>整本书</option>
                {chapterOptions.map(c => (
                  <option key={c.chapter_id} value={c.chapter_id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium text-muted-foreground">风格</span>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2" role="radiogroup" aria-label="风格">
                {styles.map(s => (
                  <button
                    key={s.id}
                    type="button"
                    role="radio"
                    aria-checked={style === s.id}
                    title={`适合：${s.best_for}${s.avoid_for ? `\n不适合：${s.avoid_for}` : ''}`}
                    onClick={() => setStyle(s.id)}
                    className={`flex items-center gap-2 rounded-md border px-2.5 py-2 text-left transition-colors ${
                      style === s.id
                        ? 'border-primary bg-primary/10'
                        : 'border-[var(--color-border)] hover:bg-[var(--color-muted)]'
                    }`}
                  >
                    <span
                      aria-hidden
                      className={`h-4 w-4 shrink-0 rounded-sm border ${s.scheme === 'dark' ? 'bg-neutral-800' : 'bg-white'}`}
                    />
                    <span className="flex flex-col min-w-0">
                      <span className="font-medium leading-tight">{s.name}</span>
                      <span className="text-[11px] text-muted-foreground truncate">{s.best_for}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-4">
              <label className="flex flex-col gap-1 w-32">
                <span className="text-xs font-medium text-muted-foreground">
                  页数（{limits.min}–{limits.max}）
                </span>
                <input
                  type="number"
                  aria-label="页数"
                  min={limits.min}
                  max={limits.max}
                  value={pages}
                  onChange={e => setPages(Number(e.target.value) || limits.min)}
                  className="h-9 rounded-md border border-[var(--color-border)] bg-background px-2"
                />
              </label>
              <label className="flex flex-col gap-1 flex-1">
                <span className="text-xs font-medium text-muted-foreground">受众（可选）</span>
                <input
                  type="text"
                  aria-label="受众"
                  maxLength={40}
                  placeholder="例如：大一新生"
                  value={audience}
                  onChange={e => setAudience(e.target.value)}
                  className="h-9 rounded-md border border-[var(--color-border)] bg-background px-2"
                />
              </label>
            </div>

            {recent.filter(r => r.status === 'succeeded').length > 0 && (
              <div className="flex flex-col gap-1 border-t border-[var(--color-border)] pt-3">
                <span className="text-xs font-medium text-muted-foreground">最近生成</span>
                {recent
                  .filter(r => r.status === 'succeeded')
                  .slice(0, 3)
                  .map(r => (
                    <div key={r.job_id} className="flex items-center justify-between gap-2 text-xs">
                      <span className="truncate">
                        {r.title || '未命名'} · {r.slide_count ?? r.pages} 页 · {styles.find(s => s.id === r.style)?.name ?? r.style}
                      </span>
                      <Button size="sm" variant="outline" onClick={() => void downloadPptExport(r)}>
                        下载
                      </Button>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {job && (
          <div className="flex flex-col gap-3 text-sm" aria-live="polite">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{PPT_STAGE_LABELS[job.stage ?? job.status] ?? job.stage ?? job.status}</span>
              <span>{job.progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--color-muted)]">
              <div
                role="progressbar"
                aria-valuenow={job.progress}
                aria-valuemin={0}
                aria-valuemax={100}
                className={`h-full transition-all ${job.status === 'failed' ? 'bg-red-500' : 'bg-primary'}`}
                style={{ width: `${Math.max(3, job.progress)}%` }}
              />
            </div>
            {running && (
              <p className="text-xs text-muted-foreground">
                正在按章节撰写讲解内容并排版，通常需要几分钟；可以关闭窗口，稍后在这里下载。
              </p>
            )}
            {job.status === 'failed' && (
              <p className="text-xs text-red-500">生成失败：{job.error ?? '未知错误'}</p>
            )}
            {job.status === 'succeeded' && (
              <>
                <p className="font-medium">{job.title}</p>
                <p className="text-xs text-muted-foreground">
                  {job.slide_count} 页 · {styles.find(s => s.id === job.style)?.name ?? job.style}
                  {job.qa?.counts ? ` · 自检：错误 ${job.qa.counts.ERROR ?? 0}，提醒 ${job.qa.counts.WARN ?? 0}` : ''}
                  {job.file_size ? ` · ${(job.file_size / 1024 / 1024).toFixed(1)} MB` : ''}
                </p>
                {previews.length > 0 && (
                  <div className="grid grid-cols-3 gap-2">
                    {previews.map((src, i) => (
                      <img key={i} src={src} alt={`第 ${i + 1} 页预览`} className="w-full rounded border border-[var(--color-border)]" />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            {running ? '后台生成' : '关闭'}
          </Button>
          {!job && (
            <Button onClick={() => void start()} disabled={!style || submitting || !!notReady}>
              {submitting ? '提交中…' : '生成 PPT'}
            </Button>
          )}
          {job?.status === 'failed' && <Button onClick={() => setJob(null)}>重新设置</Button>}
          {job?.status === 'succeeded' && (
            <Button onClick={() => void downloadPptExport(job).catch(e => toast.error(`下载失败：${errorText(e)}`))}>
              下载 PPT
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default PptExportDialog;
