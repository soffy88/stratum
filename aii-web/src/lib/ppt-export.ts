/**
 * Book → editable PPT export (backend: /api/v1/ppt, luobo-ppt engine).
 */
import { apiClient } from '@/lib/apiClient';

export interface PptStyle {
  id: string;
  name: string;
  scheme: 'light' | 'dark' | string;
  mood: string;
  best_for: string;
  avoid_for: string;
}

export interface PptStylesResponse {
  styles: PptStyle[];
  default: string;
  pages: { min: number; max: number; default: number };
}

export interface PptChapter {
  chapter_id: string;
  title: string;
  question: string;
}

export interface PptBookChapters {
  substrate_id: string;
  title?: string;
  ready: boolean;
  reason?: string;
  run_id?: string;
  bu_status?: string;
  language?: string;
  chapters: PptChapter[];
}

export type PptJobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface PptQaSummary {
  counts?: { ERROR?: number; WARN?: number; INFO?: number };
  renderer?: string;
  fallback_slides?: number;
}

export interface PptExportJob {
  job_id: string;
  substrate_id: string;
  run_id: string | null;
  chapter_id: string | null;
  style: string;
  pages: number;
  status: PptJobStatus;
  stage: string | null;
  progress: number;
  title: string | null;
  language: string | null;
  slide_count: number | null;
  file_size: number | null;
  qa: PptQaSummary;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  download_url: string | null;
  preview_urls: string[];
}

export interface CreatePptExport {
  substrate_id?: string;
  run_id?: string;
  chapter_id?: string | null;
  style: string;
  pages: number;
  audience?: string;
  notes?: boolean;
}

/** Stage keys from the backend, in Chinese for the progress line. */
export const PPT_STAGE_LABELS: Record<string, string> = {
  queued: '排队中',
  collecting: '读取书的理解',
  writing: '撰写讲解内容',
  checking: '检查大纲',
  designing: '排版与自检',
  finishing: '打包文件',
  done: '已完成',
  failed: '失败',
};

export async function getPptStyles(): Promise<PptStylesResponse> {
  return (await apiClient.get<PptStylesResponse>('/api/v1/ppt/styles')).data;
}

export async function getPptBookChapters(substrateId: string): Promise<PptBookChapters> {
  return (
    await apiClient.get<PptBookChapters>(
      `/api/v1/ppt/books/${encodeURIComponent(substrateId)}/chapters`,
    )
  ).data;
}

export async function createPptExport(body: CreatePptExport): Promise<PptExportJob> {
  return (await apiClient.post<PptExportJob>('/api/v1/ppt/exports', body)).data;
}

export async function getPptExport(jobId: string): Promise<PptExportJob> {
  return (await apiClient.get<PptExportJob>(`/api/v1/ppt/exports/${encodeURIComponent(jobId)}`)).data;
}

export async function listPptExports(substrateId?: string): Promise<PptExportJob[]> {
  const res = await apiClient.get<{ exports: PptExportJob[] }>('/api/v1/ppt/exports', {
    params: { substrate_id: substrateId, limit: 10 },
  });
  return res.data.exports ?? [];
}

/** Fetch an authenticated file (download or preview) as a Blob. */
export async function fetchPptBlob(path: string): Promise<Blob> {
  return (await apiClient.get<Blob>(path, { responseType: 'blob' })).data;
}

export async function downloadPptExport(job: PptExportJob): Promise<void> {
  if (!job.download_url) return;
  const blob = await fetchPptBlob(job.download_url);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${(job.title || 'deck').replace(/[\\/:*?"<>|]/g, '-')}.pptx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
